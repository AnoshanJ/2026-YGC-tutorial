"""Mocked customer lookup client."""

from __future__ import annotations

from typing import Any

from . import orders as orders_client
from ._data import load


class CustomerNotFound(Exception):
    pass


def lookup_by_email(email: str) -> dict[str, Any]:
    rows = load("customers.json")
    for c in rows:
        if c["email"].lower() == email.lower():
            return c
    raise CustomerNotFound(f"No customer with email {email!r}")


def get_by_id(customer_id: str) -> dict[str, Any]:
    rows = load("customers.json")
    for c in rows:
        if c["id"] == customer_id:
            return c
    raise CustomerNotFound(f"No customer with id {customer_id!r}")


def list_orders(customer_id: str, limit: int = 10) -> list[dict[str, Any]]:
    return orders_client.list_for_customer(customer_id, limit=limit)
