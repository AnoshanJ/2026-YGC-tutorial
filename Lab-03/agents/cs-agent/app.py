"""FastAPI entrypoint for the CS agent.

Implements the AM chat-agent contract: ``POST /chat`` on port 8000 accepting
``{session_id, message, context}`` and returning ``{response, session_id}``.

Customer identity is supplied **inside the request body** as
``context.customer_id`` — the AM chat-agent spec's official mechanism for
client-supplied request metadata. The full customer profile is loaded
server-side and injected into the per-request system message; the agent
never asks for or looks up the user. Customer attributes are also attached
to the current OTEL root span so traces are filterable by customer / tier /
region in the AM console.

If the client omits ``context.customer_id`` (e.g. AM console's Try-it-out
panel, which sends bare ``{message}`` payloads), the request falls back to
``DEFAULT_CUSTOMER_ID`` so the agent stays usable for quick smoke tests.

A simple in-memory message store keyed by ``session_id`` keeps conversation
history across turns — sufficient for demo prep; not durable across restarts.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from pydantic import BaseModel

# OpenTelemetry is injected at deploy time by AM's auto-instrumentation;
# in local dev (running main.py outside AM) the package may not be installed,
# so the import is optional. Span attributes are skipped when unavailable.
try:
    from opentelemetry import trace as _otel_trace
except ImportError:  # pragma: no cover
    _otel_trace = None  # type: ignore[assignment]

from agent import build_agent, system_message_for
from clients import customers as customers_client
from config import Config

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("cs-agent")

# Fallback for clients that don't supply context.customer_id (notably AM's
# Try-it-out panel). Must match an id present in data/customers.json.
DEFAULT_CUSTOMER_ID = "C-1001"

CONFIG = Config.from_env()
AGENT = build_agent(CONFIG)
log.info(
    "CS agent ready (region=%s, refund_cap=%s %s, escalation_queue=%s)",
    CONFIG.region,
    CONFIG.refund_cap,
    CONFIG.currency,
    CONFIG.escalation_queue,
)

# session_id -> list of LangChain messages (excluding the system message, which
# is rebuilt per turn from the authenticated customer profile).
SESSIONS: dict[str, list[BaseMessage]] = {}


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    context: dict[str, Any] | None = None


class ChatResponse(BaseModel):
    response: str
    session_id: str | None = None


app = FastAPI(title="CS Agent", version="0.1.0")

# CORS for the mock-login chat frontend. Override with CHAT_UI_ORIGINS
# (comma-separated) when the UI is served from a non-default origin.
_default_origins = "http://localhost:5173,http://127.0.0.1:5173"
_origins = [
    o.strip()
    for o in os.environ.get("CHAT_UI_ORIGINS", _default_origins).split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["x-api-key", "Content-Type", "Authorization"],
)


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "region": CONFIG.region,
        "currency": CONFIG.currency,
    }


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    # AM chat-agent spec: client-supplied identity travels in the request
    # body's `context` field (see ChatRequest), not as a custom header. The
    # AM console's Try-it-out panel sends no context, so we fall back to a
    # known seed customer rather than 400-ing.
    customer_id = (req.context or {}).get("customer_id") if req.context else None
    if not customer_id:
        log.warning(
            "no context.customer_id in request; falling back to default %s",
            DEFAULT_CUSTOMER_ID,
        )
        customer_id = DEFAULT_CUSTOMER_ID

    try:
        customer = customers_client.get_by_id(customer_id)
    except customers_client.CustomerNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if _otel_trace is not None:
        span = _otel_trace.get_current_span()
        span.set_attribute("customer.id", customer["id"])
        span.set_attribute("customer.tier", customer.get("tier", ""))
        span.set_attribute("customer.region", customer.get("region", ""))
        if req.session_id:
            span.set_attribute("session.id", req.session_id)

    history = (
        SESSIONS.setdefault(req.session_id or "anon", []) if req.session_id else []
    )
    sys_msg = system_message_for(CONFIG, customer)
    user_msg = HumanMessage(content=req.message)
    messages: list[BaseMessage] = [sys_msg, *history, user_msg]

    try:
        result = AGENT.invoke({"messages": messages})
    except Exception as exc:  # noqa: BLE001
        log.exception("agent invocation failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    out_messages = result.get("messages", [])
    final_ai: AIMessage | None = None
    for m in reversed(out_messages):
        if isinstance(m, AIMessage):
            final_ai = m
            break

    final_text: Any = final_ai.content if final_ai is not None else "(no response)"
    if isinstance(final_text, list):
        final_text = "\n".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in final_text
        )

    # Persist this turn's user + final AI message so subsequent turns have context.
    # Skip the system message (rebuilt per turn) and intermediate tool messages —
    # the LLM has those embedded in tool_calls on the AI message already.
    if req.session_id:
        history.append(user_msg)
        if final_ai is not None:
            history.append(final_ai)

    return ChatResponse(response=str(final_text), session_id=req.session_id)
