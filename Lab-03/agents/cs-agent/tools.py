"""Tool definitions exposed to the LangGraph CS agent.

Each tool wraps a call into ``clients/`` and serializes results as plain strings
suitable for the LLM. Errors from the clients are returned as readable strings,
not raised, so the agent can decide what to do (typically: escalate).
"""

from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import tool

from clients import customers as customers_client
from clients import escalations as escalations_client
from clients import orders as orders_client
from clients import policies as policies_client
from clients import refunds as refunds_client
from config import Config


def build_tools(cfg: Config) -> list[Any]:
    """Build the tool set bound to the given instance config.

    The tools close over ``cfg`` so the LLM cannot influence the cap, region,
    queue, etc. — these are kind-enforced and instance-fixed.
    """

    @tool
    def lookup_customer(email: str) -> str:
        """Look up a customer by their email address.

        Returns the customer record (id, name, tier, signup date, region) as JSON,
        or an error message if the email is unknown.
        """
        try:
            customer = customers_client.lookup_by_email(email)
            return json.dumps(customer)
        except customers_client.CustomerNotFound as e:
            return f"ERROR: {e}"

    @tool
    def get_order(order_id: str) -> str:
        """Fetch a single order by ID.

        Returns full order details (items, status, shipping address, total, currency).
        """
        try:
            order = orders_client.get(order_id)
            return json.dumps(order)
        except orders_client.OrderNotFound as e:
            return f"ERROR: {e}"

    @tool
    def get_customer_orders(customer_id: str, limit: int = 10) -> str:
        """List the most recent orders for a customer, newest first."""
        rows = customers_client.list_orders(customer_id, limit=limit)
        return json.dumps(rows)

    @tool
    def search_policy_kb(query: str) -> str:
        """Search the region's policy knowledge base for relevant policy snippets."""
        docs = policies_client.search(region=cfg.region, query=query, limit=5)
        return json.dumps(docs)

    @tool
    def update_shipping_address(order_id: str, address: str) -> str:
        """Update the shipping address on an order.

        Only succeeds if the order is still in 'processing' status.
        """
        try:
            order = orders_client.update_shipping_address(order_id, address)
            return json.dumps(order)
        except (orders_client.OrderNotFound, orders_client.OrderImmutable) as e:
            return f"ERROR: {e}"

    @tool
    def cancel_order(order_id: str, reason: str) -> str:
        """Cancel an order if it has not yet shipped."""
        try:
            order = orders_client.cancel(order_id, reason)
            return json.dumps(order)
        except (orders_client.OrderNotFound, orders_client.OrderImmutable) as e:
            return f"ERROR: {e}"

    @tool
    def issue_refund(order_id: str, amount: float, reason: str) -> str:
        """Issue a refund against an order.

        Refuses any amount above the configured REFUND_CAP — the agent should
        call escalate_to_human in that case.
        """
        try:
            receipt = refunds_client.issue(
                order_id=order_id,
                amount=amount,
                reason=reason,
                cap=cfg.refund_cap,
                currency=cfg.currency,
            )
            return json.dumps(receipt)
        except refunds_client.RefundOverCap as e:
            return (
                f"ERROR: {e} Use escalate_to_human to forward this request to a person."
            )

    @tool
    def escalate_to_human(
        customer_id: str, summary: str, priority: str = "normal"
    ) -> str:
        """Hand the case to a human agent on the configured escalation queue.

        Use this for over-cap refunds, unclear policy questions, abusive prompts,
        or anything the agent cannot resolve safely.
        """
        ticket = escalations_client.create(
            customer_id=customer_id,
            summary=summary,
            priority=priority,
            queue=cfg.escalation_queue,
        )
        return json.dumps(ticket)

    return [
        lookup_customer,
        get_order,
        get_customer_orders,
        search_policy_kb,
        update_shipping_address,
        cancel_order,
        issue_refund,
        escalate_to_human,
    ]
