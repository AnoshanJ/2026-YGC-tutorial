"""Mocked customer lookup client."""

from __future__ import annotations

from typing import Any

from ._data import load


class CustomerNotFound(Exception):
    pass


def lookup_by_email(email: str) -> dict[str, Any]:
    rows = load("customers.json")
    for c in rows:
        if c["email"].lower() == email.lower():
            return c
    raise CustomerNotFound(f"No customer with email {email!r}")


def list_orders(customer_id: str, limit: int = 10) -> list[dict[str, Any]]:
    orders = load("orders.json")
    matched = [o for o in orders if o["customer_id"] == customer_id]
    matched.sort(key=lambda o: o["created_at"], reverse=True)
    return matched[:limit]
