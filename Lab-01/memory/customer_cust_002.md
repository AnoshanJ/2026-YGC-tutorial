# Customer memory — cust_002 (Bob Martinez)

Episodic memory for Bob. The agent reads this when `memory.episodic: true`
in agent-profile.yaml. It's what makes Bob a returning customer instead of
a stranger on every interaction.

## 2026-05-01 — Damaged french press (order #2210)

- Customer reported the glass french press (order #2210, $58) arrived
  cracked. Photo confirmed.
- Issued **$58 refund** via `issue_refund` (ref `refund_0001`).
- Promised a **replacement shipment within 5 business days**.
- Opened **TICKET-1001** (priority: normal) with the warehouse team to
  investigate batch QC — Bob mentioned this is his SECOND damaged delivery
  to the same address (Lindenstrasse, Munich) in the last 6 months.
- Customer tone was understanding but pointed. The repeat-damage pattern
  is a fulfillment problem, not a customer problem.

## Outstanding obligations

- Replacement for order #2210 owed to Bob — should have shipped by ~2026-05-06.
  As of today (2026-05-15), no replacement has been received per Bob's last
  message. This is a missed commitment.
- TICKET-1001 hasn't progressed visibly. The warehouse owes us an update.

## Notes for any agent interacting with Bob

- He's not a new customer with a new complaint. Treat as a follow-up.
- Use his name. He's tier `standard` but has been with us since 2022 — a
  long-tenured account that's hit a quality issue twice.
- If the conversation is about #2210 still not arriving, escalate with
  priority `high` and reference TICKET-1001 directly. Do NOT ask Bob to
  repeat the original complaint details.
- Don't double-refund the $58 — that's already been issued.
