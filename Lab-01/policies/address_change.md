---
id: address_change
title: Address change
keywords: [address, shipping address, wrong address, change address, redirect, my office]
---

# Address change

Shipping addresses may be updated **only** on orders that have not yet shipped
(status: `placed` or `preparing`). After shipment, the carrier owns the package
and the customer must use the carrier's redirect service directly.

## Agent action

1. Call `get_order` — check the `status` field.
2. **If status is `placed` or `preparing`:** call `update_shipping_address`
   with the new address. Confirm the new address in the reply.
3. **If status is anything else** (`in_transit_delayed`, `in_transit`,
   `delivered`, `delivered_damaged`): do NOT call `update_shipping_address`.
   The tool will return `{"error": "order_already_shipped",
   "remediation": "redirect_to_carrier"}`. Instead, politely explain the
   constraint and direct the customer to the carrier's redirect service
   (typically a link on the tracking page).

## Anti-pattern

Calling `update_shipping_address` blindly without first checking status. The
tool will reject, you'll waste a turn, and the customer sees you fumble.
Always `get_order` first.

## Exceptions

- Customer claims package is being delivered to wrong address by mistake
  (their old address from a previous order): escalate with priority `high` —
  this may need carrier intercept.
- Address update for international shipping in transit: escalate to human;
  carrier rules vary by region.
