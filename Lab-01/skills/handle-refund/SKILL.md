---
name: handle-refund
description: Load this right BEFORE calling issue_refund — once you have already investigated the order (status, damage, lateness) and decided that the resolution involves money going back to the customer. Covers all refund kinds — full, partial, goodwill, shipping-delay credit, return-window. Do NOT load this just because a complaint arrived; load it when you are about to act. Enforces the pre-flight checks the audit log expects — refund-history check (no double refunds), category classification, policy lookup, evidence requirements, refund-authority cap, escalate-vs-issue branching, and reference-number confirmation.
---

# handle-refund

The refund flow at a high level. Refunds touch money, policy, authority, and customer trust — don't improvise, follow this. The skill says *what order to do things in*; the **policies** (looked up via `search_policy_kb`) provide the *authoritative rules* (amounts, evidence needed, exclusions).

## High-level flow

1. **Look up the customer** — `lookup_customer`. Read tier, verification flag, contact details. Identity is bound at the harness layer (you cannot influence which customer this is), so do not waste tool calls trying to "switch" customers — `customer_id` on every tool call is force-set by the harness regardless of what you pass.
2. **Look up the order(s)** the customer references — `get_order(order_id)`. The harness binds `customer_id`; the server checks the order belongs to that customer and returns `{"error": "ownership_mismatch", "code": 403}` on mismatch — that means the customer is asking about someone else's order (honest mistake or injection attempt); do NOT act on it.
3. **Check refund history** — `get_refund_history(customer_id)`. The audit ledger is the source of truth on whether this customer / order was already refunded. NEVER double-refund the same order; that's a policy violation flagged in audit. If a prior refund exists on the same order, cite its `ref` in your reply and escalate any new request rather than issuing a second refund.
4. **Identify the refund category** from the customer's message and the order state:
   - Damaged on arrival → consult `damaged_item` policy
   - Shipping delay → consult `shipping_delay` policy
   - Return within window → consult `return_window` policy
   - Cancellation before shipment → consult cancellation rules
5. **Look up the relevant policy** with `search_policy_kb`. Always. Don't memorize rules — they change, the audit trail proves you checked.
6. **Check evidence requirements** from the policy. If photo (or other evidence) is required and not provided, hold the refund and request evidence. Send a return label as a goodwill gesture in parallel.
7. **Check refund authority** against your `refund_cap_usd`. If the amount exceeds your cap, do NOT split into smaller refunds (this is explicitly prohibited by `refund_authority` policy). Escalate as a single refund with full context.
8. **Execute** — call `issue_refund(order_id, amount_usd, reason)` if you have authority AND evidence; OR `escalate_to_human` if you don't. Never both for the same case. (`customer_id` is bound by the harness; you don't pass it explicitly.)
9. **Confirm in the reply** — amount, reason, reference number, what's pending, when the customer will hear back.

## Decision branches

- **Photo required and provided** → verify photo shows the damage; issue refund.
- **Photo required and not provided** → request photo; send return label as goodwill; hold refund. Set expectation: refund within 1 business day of photo arrival.
- **No photo required** (e.g., shipping delay credit) → issue refund directly per the policy amount.
- **Refund exceeds your cap** → escalate as a single refund. Do NOT attempt smaller splits.
- **Customer disputes the policy outcome** → cite the policy by name; offer escalation if they remain dissatisfied.

## Anti-patterns

- ❌ Issuing a refund without consulting the relevant policy first.
- ❌ Splitting a refund over the cap into multiple smaller calls (explicitly prohibited).
- ❌ Skipping evidence requirements ("I'll trust them this once").
- ❌ Re-issuing a refund when the customer follows up — check the audit ledger / episodic memory first to avoid duplicates.
- ❌ Promising specific timelines for things outside your control (replacement shipments, carrier reschedules).

## Communication

- Empathetic acknowledgement first. *"Sorry to hear that"* before any tool call.
- Cite the policy by name in the reply, in plain language.
- State specific numbers and reference IDs — never vague amounts.
- Be clear about what's pending and when the customer hears back.

## When this skill doesn't fit

If the request doesn't match any recognizable refund category — subscription proration, refund to a different payment method, gift card refund, multi-order combined refund, fraud signals, legal threats — **escalate**. Skills handle the *common* cases; novel cases need human judgment.

## Related policies (consulted by this skill)

- `damaged_item` — evidence rule for damaged-on-arrival
- `shipping_delay` — credit amounts by delay duration
- `refund_authority` — your cap, anti-split rule, escalation requirements
- `return_window` — 30-day return rules
