---
name: handle-cancellation
description: Load this right BEFORE calling cancel_order — once you have already confirmed the order has not yet shipped and the customer wants to abandon the order (not just modify it or refund it post-delivery). cancel_order only works for orders in placed or preparing status; shipped orders need a return flow instead, and address-only changes belong with handle-address-change. The skill orchestrates the status branch, refund coordination if the customer was already charged, and audit confirmation with a reference number.
---

# handle-cancellation

Cancellation flips the order status to `cancelled` and stops fulfillment. It is a one-way write — get the diagnosis right BEFORE loading this skill. Only call `cancel_order` when the customer explicitly wants to abandon the order, not when they want it modified (`handle-address-change`), delayed (no action), or refunded post-delivery (`handle-refund` after a return).

## High-level flow

1. **Look up the order** — `get_order(order_id)`. The harness binds the customer; the server returns `ownership_mismatch` (code 403) if the order belongs to someone else — do NOT retry.
2. **Branch on order status:**
   - `placed` or `preparing` → cancellation is allowed; continue to step 3.
   - `shipped` / `in_transit_delayed` / `delivered` / `delivered_damaged` → cancellation is NOT allowed. The tool will return `order_already_shipped`. Redirect — for shipped-but-undelivered, the carrier may accept a redirect or refusal; for delivered, this is a return (consult `return_window` policy via `search_policy_kb`).
3. **Check whether the customer was already charged** — for unshipped orders that are `preparing`, this is usually yes. If yes, a refund will be needed alongside the cancellation.
4. **Execute the cancellation** — `cancel_order(order_id, reason)`. Use a specific reason (e.g. `customer_request`, `duplicate_order`, `wrong_item_ordered`) — it is audit-logged.
5. **Issue the refund if step 3 said yes** — load `handle-refund` and follow it. The refund follows the cancel in the ledger.
6. **Confirm in the reply** — cancel reference (`cancel_xxxx`); refund reference (`refund_xxxx`) if applicable; expected timing for any payment reversal.

## Decision branches

- **Order shipped + customer wants to cancel** → cannot. Explain carrier-redirect / return-on-arrival path. Do NOT attempt `cancel_order` — the status check is server-side.
- **Order preparing + customer was charged** → `cancel_order` first, then `handle-refund`. Cite both refs.
- **Order placed + not yet charged** → `cancel_order` alone, no refund needed.
- **Customer wants to cancel just to fix the address** → suggest `handle-address-change` instead; it's faster than cancel + re-order.

## Anti-patterns

- ❌ Calling `cancel_order` before checking status — you'll get `order_already_shipped` and waste a turn.
- ❌ Retrying `cancel_order` on a shipped order with a different reason — the check is status-based, not reason-based.
- ❌ Issuing a refund before the cancel for an unshipped order — out of order; cancel first, then refund.
- ❌ Forgetting to confirm the cancel ref in the reply — the customer needs it for their records.

## Related skills and tools

- `cancel_order(order_id, reason)` — the write.
- `handle-refund` — load this AFTER `cancel_order` if the customer was already charged.
- `handle-address-change` — if the cancel was really a modification request, redirect there instead.
- `return_window` policy — for delivered orders the customer wants to "cancel" (it is a return, not a cancel).
