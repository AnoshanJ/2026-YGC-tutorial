"""Shared in-memory mock backend used by both cs_agent_v1 and cs_agent_v2.

CustomerSupportClient loads from mocks/seeds/*.json at __init__ time and
keeps all mutations in-process. Each agent runs in its own Python process,
so v1 and v2 hold independent state — side-by-side demos can't stomp on
each other. Reset by calling `client.reset()` or re-instantiating.
"""

from mocks.client import CustomerSupportClient
from mocks.models import Customer, LedgerEntry, Order

__all__ = ["CustomerSupportClient", "Customer", "LedgerEntry", "Order"]
