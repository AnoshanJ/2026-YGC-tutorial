"""CustomerSupportClient — JSON-backed mock backend.

Reads / writes flat JSON under `mocks/data/`. On first run, the JSON files
are auto-seeded from `mocks/seeds/`. Every write (refund, cancel, ticket,
address update) is persisted to `mocks/data/ledger.json` and visible to
the audience as a real file change.

To reset the lab between demos: `python reset.py` — restores customers /
orders from seeds and truncates ledger to empty.

In production this class would wrap your real order / customer / audit
APIs. The point of the client abstraction is that tool code never knows
the difference.
"""

import json
from datetime import datetime
from pathlib import Path

from mocks.models import Customer, Order

ROOT = Path(__file__).parent
SEEDS_DIR = ROOT / "seeds"
DATA_DIR = ROOT / "data"

CUSTOMERS_FILE = "customers.json"
ORDERS_FILE = "orders.json"
LEDGER_FILE = "ledger.json"


def _seed_if_missing() -> None:
    """First-run setup: copy seeds → data if data files are missing.

    The ledger is seeded from `seeds/ledger.json` (which carries a couple of
    pre-existing entries used by §3's episodic-memory demo — e.g. Bob's
    refund_0001 + TICKET-1001). If the seed file is absent we fall back to
    an empty ledger.
    """
    DATA_DIR.mkdir(exist_ok=True)
    for name in (CUSTOMERS_FILE, ORDERS_FILE, LEDGER_FILE):
        target = DATA_DIR / name
        if target.exists():
            continue
        seed = SEEDS_DIR / name
        target.write_text(seed.read_text() if seed.exists() else "[]\n")


def _read(name: str):
    return json.loads((DATA_DIR / name).read_text())


def _write(name: str, payload) -> None:
    (DATA_DIR / name).write_text(json.dumps(payload, indent=2, default=str) + "\n")


class CustomerSupportClient:
    """Reads/writes JSON under mocks/data/. Stateless instance — every call
    re-reads from disk so the audience can edit files mid-demo and see the
    change on the next agent step."""

    def __init__(self) -> None:
        _seed_if_missing()

    # ----- Reads -------------------------------------------------------------

    def get_customer(self, customer_id: str) -> Customer | None:
        record = _read(CUSTOMERS_FILE).get(customer_id)
        return Customer(**record) if record else None

    def get_customer_record(self, customer_id: str) -> dict | None:
        """Full backend record — what `SELECT *` from the CRM would return.

        Includes the customer-facing fields a tool would normally project,
        plus the kind of internal metadata a real CRM exposes by default:
        DB id, shard key, audit pointer, lifecycle / segment flags,
        replica lag, etag, legacy duplicate fields, opt-in history.

        Tools that surface this raw (e.g. v1's `get_customer_full`) hand
        the agent ~15 noise fields it has to scan past. Tools that project
        (v2's `lookup_customer`) only return what the agent needs.
        """
        raw = _read(CUSTOMERS_FILE).get(customer_id)
        if raw is None:
            return None
        return {
            **raw,
            "_db_id": f"u-{customer_id}-pg-shard-04",
            "_account_tag": f"RET-2024-{customer_id.upper()}",
            "_lifecycle_state": (
                "active_engaged" if raw.get("verified") else "passive_unverified"
            ),
            "_segment_cohort": (
                "Q4-2024-EAR" if raw.get("tier") == "premium" else "Q4-2024-STD"
            ),
            "_created_at_unix_ms": 1714521600000,
            "_updated_at_unix_ms": 1738224000000,
            "_last_login_unix_ms": 1738137600000,
            "_schema_version": 7,
            "_replica_lag_ms": 42,
            "_audit_pointer": f"audit://customers/{customer_id}/v7",
            "_etag": f'W/"{customer_id}-v7-abc123"',
            "_marketing_opt_in_history": ["v1", "v2", "v3"],
            "_legacy_email_field": raw.get("email"),
            "_payment_methods_count": 2,
            "_pii_redaction_token": None,
        }

    def get_order(self, order_id: str) -> Order | None:
        record = _read(ORDERS_FILE).get(order_id)
        return Order(**record) if record else None

    def get_customer_orders(self, customer_id: str) -> list[Order]:
        return [
            Order(**o)
            for o in _read(ORDERS_FILE).values()
            if o["customer_id"] == customer_id
        ]

    # ----- Writes ------------------------------------------------------------

    def _append_ledger(
        self,
        kind: str,
        order_id: str | None,
        customer_id: str | None,
        amount_usd: float | None,
        reason: str,
        agent_id: str,
        extra: dict | None = None,
    ) -> int:
        """Append an entry to the ledger, return its 1-based position.

        `extra` carries write-kind-specific fields (e.g. `ticket_id` + `status`
        for tickets, `ref` for refunds) so the read tools have something
        durable to filter on.
        """
        ledger = _read(LEDGER_FILE)
        entry = {
            "kind": kind,
            "order_id": order_id,
            "customer_id": customer_id,
            "amount_usd": amount_usd,
            "reason": reason,
            "actor_agent_id": agent_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        if extra:
            entry.update(extra)
        ledger.append(entry)
        _write(LEDGER_FILE, ledger)
        return len(ledger)

    def update_shipping_address(
        self, order_id: str, new_address: str, agent_id: str
    ) -> str:
        # Mutate the order itself so the change is visible to the audience.
        orders = _read(ORDERS_FILE)
        if order_id in orders:
            orders[order_id]["shipping_address"] = new_address
            _write(ORDERS_FILE, orders)
        pos = self._append_ledger(
            "address_update", order_id, None, None, new_address, agent_id
        )
        return f"addr_{pos:04d}"

    def cancel_order(self, order_id: str, reason: str, agent_id: str) -> str:
        # Mutate the order status to 'cancelled' so the change is visible.
        orders = _read(ORDERS_FILE)
        if order_id in orders:
            orders[order_id]["status"] = "cancelled"
            _write(ORDERS_FILE, orders)
        pos = self._append_ledger("cancel", order_id, None, None, reason, agent_id)
        return f"cancel_{pos:04d}"

    def issue_refund(
        self,
        order_id: str,
        customer_id: str,
        amount_usd: float,
        reason: str,
        agent_id: str,
    ) -> str:
        # Refund refs count refunds only — keeps them stable when the ledger
        # has tickets / cancels / address-updates interleaved.
        ledger = _read(LEDGER_FILE)
        existing_refunds = sum(1 for e in ledger if e.get("kind") == "refund")
        ref = f"refund_{1 + existing_refunds:04d}"
        self._append_ledger(
            "refund",
            order_id,
            customer_id,
            amount_usd,
            reason,
            agent_id,
            extra={"ref": ref},
        )
        return ref

    def open_ticket(
        self,
        reason: str,
        priority: str,
        agent_id: str,
        customer_id: str | None = None,
    ) -> str:
        # Ticket IDs count tickets only and persist in the ledger entry so
        # `get_open_tickets` can return them later.
        ledger = _read(LEDGER_FILE)
        existing_tickets = sum(
            1 for e in ledger if e.get("kind", "").startswith("ticket_")
        )
        ticket_id = f"TICKET-{1001 + existing_tickets}"
        self._append_ledger(
            f"ticket_{priority}",
            None,
            customer_id,
            None,
            reason,
            agent_id,
            extra={"ticket_id": ticket_id, "status": "open"},
        )
        return ticket_id

    # ----- Audit-ledger reads (memory-driven verification) -------------------

    def get_open_tickets(self, customer_id: str) -> list[dict]:
        """Tickets opened for this customer that are still `status: open`.

        Read counterpart to `open_ticket`. Episodic memory hands the agent
        pointers like "look up TICKET-1001"; this is how the agent confirms
        whether the ticket has progressed (it hasn't, if it's still in here).
        """
        out: list[dict] = []
        for e in _read(LEDGER_FILE):
            kind = e.get("kind", "")
            if not kind.startswith("ticket_"):
                continue
            if e.get("customer_id") != customer_id:
                continue
            if e.get("status", "open") != "open":
                continue
            out.append(
                {
                    "ticket_id": e.get("ticket_id"),
                    "priority": kind.removeprefix("ticket_"),
                    "status": e.get("status", "open"),
                    "reason": e.get("reason"),
                    "opened_at": e.get("timestamp"),
                    "agent_id": e.get("actor_agent_id"),
                }
            )
        return out

    def get_refund_history(self, customer_id: str) -> list[dict]:
        """All refunds previously issued to this customer.

        Read counterpart to `issue_refund`. The "did we already refund?"
        check episodic memory tells the agent to do — backed by the ledger
        so memory can't drift from reality.
        """
        out: list[dict] = []
        for e in _read(LEDGER_FILE):
            if e.get("kind") != "refund":
                continue
            if e.get("customer_id") != customer_id:
                continue
            out.append(
                {
                    "ref": e.get("ref"),
                    "order_id": e.get("order_id"),
                    "amount_usd": e.get("amount_usd"),
                    "reason": e.get("reason"),
                    "issued_at": e.get("timestamp"),
                    "agent_id": e.get("actor_agent_id"),
                }
            )
        return out

    # ----- Convenience for the CLI banner ------------------------------------

    def all_customers(self) -> dict[str, Customer]:
        return {cid: Customer(**c) for cid, c in _read(CUSTOMERS_FILE).items()}
