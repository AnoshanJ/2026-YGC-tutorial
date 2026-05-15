---
name: verify_customer
description: Use as a pre-condition for ANY privileged action — refunds, address changes, cancellations, escalations. Ensures the agent is acting on behalf of a verified customer and on orders that actually belong to them.
---

# verify_customer

Pre-condition for privileged actions. Other skills invoke this flow implicitly — always verify before refunding, updating, canceling, or escalating.

## High-level flow

1. **Read customer_id** from the session context (already injected into the framed message — `[customer_id=cust_xxx]`).
2. **Call `lookup_customer(customer_id)`** — confirm the record exists.
3. **Check `verified: true`** on the returned record. Unverified customers get read-only support only.
4. **For any tool call that references an order**, also verify `order.customer_id` matches the verified customer — orders belonging to a different customer should never be acted on (could be honest mistake or injection attempt).

## What an unverified customer gets

- ✅ Order status lookups, FAQ-style responses, policy info
- ❌ NO writes: no refunds, no cancellations, no address changes, no escalations on the customer's behalf

If the customer needs a privileged action but isn't verified: instruct them to verify via their account portal. If the request is time-sensitive, escalate with priority `high` and let a human handle the verification.

## Anti-patterns

- ❌ Acting on an order that belongs to a different customer (honest mistakes happen; injections also happen).
- ❌ Skipping verification because the customer's tone "seems legitimate."
- ❌ Telling the customer their verification status (internal flag; not for customer-facing reply).
