"""Mocked order-status lookup."""

from __future__ import annotations

from typing import Any

from ._data import load


def status_for(order_id: str) -> dict[str, Any]:
    rows = load("orders.json")
    for o in rows:
        if o["id"] == order_id:
            return dict(o)
    return {
        "id": order_id,
        "status": "not_found",
        "carrier": "",
        "tracking": "",
        "eta": "",
    }
