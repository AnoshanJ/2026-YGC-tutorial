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
    """First-run setup: copy seeds → data if data files are missing."""
    DATA_DIR.mkdir(exist_ok=True)
    for name in (CUSTOMERS_FILE, ORDERS_FILE):
        target = DATA_DIR / name
        if not target.exists():
            target.write_text((SEEDS_DIR / name).read_text())
    ledger_path = DATA_DIR / LEDGER_FILE
    if not ledger_path.exists():
        ledger_path.write_text("[]\n")


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
    ) -> int:
        """Append an entry to the ledger, return its 1-based position."""
        ledger = _read(LEDGER_FILE)
        ledger.append({
            "kind": kind,
            "order_id": order_id,
            "customer_id": customer_id,
            "amount_usd": amount_usd,
            "reason": reason,
            "actor_agent_id": agent_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        })
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
        pos = self._append_ledger("address_update", order_id, None, None, new_address, agent_id)
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
        pos = self._append_ledger(
            "refund", order_id, customer_id, amount_usd, reason, agent_id
        )
        return f"refund_{pos:04d}"

    def open_ticket(
        self,
        reason: str,
        priority: str,
        agent_id: str,
        customer_id: str | None = None,
    ) -> str:
        # Ticket IDs are derived from existing ledger contents so they
        # stay stable across REPL restarts within the same data state.
        ledger = _read(LEDGER_FILE)
        existing_tickets = sum(1 for e in ledger if e.get("kind", "").startswith("ticket_"))
        ticket_id = f"TICKET-{1001 + existing_tickets}"
        self._append_ledger(
            f"ticket_{priority}", None, customer_id, None, reason, agent_id
        )
        return ticket_id

    # ----- Convenience for the CLI banner ------------------------------------

    def all_customers(self) -> dict[str, Customer]:
        return {cid: Customer(**c) for cid, c in _read(CUSTOMERS_FILE).items()}
