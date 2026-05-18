"""FastAPI entrypoint for cs_agent_v1 — the first-cut, unscoped agent.

Run:  uvicorn main:app --reload --port 8001

Endpoints:
    POST /api/run    SSE stream of agent events for one prompt.
    POST /api/reset  Wipe this agent's mock data.
    GET  /health     Liveness probe.

A single Agent instance is built once at startup and reused across every
request — `agent.messages` accumulates in-process, so the agent has
short-term memory between turns. The catch: there's no per-customer
isolation, so the same conversation history is visible to every caller
(Alice's chat shows up in Bob's session). Process restart wipes it.
That's the v1 footgun the lab demonstrates — v2 fixes it with a
per-customer agent cache.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

# The shared mocks/ package lives at the lab root, next to cs_agent_v1/
# and cs_agent_v2/. Put it on sys.path before anything that imports it.
_LAB_ROOT = Path(__file__).parent.parent
if str(_LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(_LAB_ROOT))

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

# OPENAI_API_KEY (and any other agent config) lives in a single `.env` at
# the lab root (`Lab-01/.env`) — one file to edit, both services read it.
# The per-agent `.env` is supported as an optional override.
load_dotenv(_LAB_ROOT / ".env")
load_dotenv(Path(__file__).parent / ".env", override=False)

from agent import AGENT_ID, build_agent, frame_prompt
from config import MODEL_ID
from strands import Agent
from strands.models.openai import OpenAIModel
from tools import reset_state

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("cs_agent_v1")


# Single shared agent across all requests (and all customers). `agent.messages`
# is the conversation memory — survives across requests but leaks across
# users. Rebuilt on /api/reset (and lazily on first request).
_V1_AGENT: Agent | None = None


def _get_v1_agent() -> Agent:
    global _V1_AGENT
    if _V1_AGENT is None:
        _V1_AGENT = build_agent()
    return _V1_AGENT


# ---------------------------------------------------------------------------
# SSE event extraction from Strands' stream_async()
# ---------------------------------------------------------------------------


def _truncate(value: Any, n: int = 60) -> str:
    s = "" if value is None else str(value)
    return s if len(s) <= n else s[: n - 1] + "…"


def _summarize_args(name: str, args: dict | None) -> str:
    if not isinstance(args, dict):
        return _truncate(args)
    if name == "search_kb":
        return f'"{_truncate(args.get("query", ""), 50)}"'
    if name == "get_order":
        return args.get("order_id", "?")
    if name in {
        "get_customer_name",
        "get_customer_email",
        "get_customer_tier",
        "get_customer_verified",
        "get_customer_orders",
        "get_refund_history",
        "get_open_tickets",
    }:
        return args.get("customer_id", "?")
    if name == "modify_order":
        order = args.get("order_id", "?")
        # flat optional params — only show the ones the agent actually set
        actionable = {
            k: v
            for k, v in args.items()
            if k != "order_id" and v is not None
        }
        summary = ", ".join(
            f"{k}={_truncate(v, 25)}" for k, v in actionable.items()
        )
        return f"{order}, {summary}" if summary else order
    if name == "escalate":
        return f'"{_truncate(args.get("reason", ""), 50)}"'
    return ", ".join(f"{k}={_truncate(v, 25)}" for k, v in args.items())


_STR_ERROR_SENTINELS = (
    "not found",
    "couldn't",
    "couldnt",
    "unknown",
    "missing",
    "nope",
    "no results",
    "specify",
)


def _summarize_result(name: str, result: Any) -> tuple[str, bool]:
    # AP4: every tool signals errors differently. Cover each shape.
    if isinstance(result, dict):
        # modify_order: {"status": "ok"|"failed", ...}. Scoped to modify_order
        # because get_order also has a `status` key (the order's shipping
        # status, e.g. "in_transit_delayed") — without scoping, every order
        # lookup would render as a tool error.
        if name == "modify_order" and "status" in result:
            if result["status"] == "ok":
                return f"ok {result.get('ref', '')}", False
            return f"failed: {_truncate(result.get('message', '?'), 60)}", True
        # get_order: {"error": "..."}
        if "error" in result:
            return f"err: {_truncate(result['error'], 60)}", True

    if name == "get_order" and isinstance(result, dict):
        status = result.get("status", "?")
        total = result.get("total_usd", "?")
        late = result.get("delivery_days_late", 0)
        late_str = f", {late}d late" if late else ""
        return f"{status}, ${total}{late_str}", False

    # AP3 SOAP-style envelopes — peek into the nested structure to show
    # a useful one-liner instead of dumping the noise.
    if name == "get_refund_history" and isinstance(result, dict):
        env = result.get("RefundEnvelope") or {}
        return f"[{env.get('@count', '?')} refunds]", False
    if name == "get_open_tickets" and isinstance(result, dict):
        tlist = (result.get("TicketEnvelope") or {}).get("OpenTicketList") or {}
        return f"[{tlist.get('@itemCount', '?')} tickets]", False

    if isinstance(result, list):
        return f"[{len(result)} items]", False

    if isinstance(result, str):
        lowered = result.lower()
        is_err = any(sig in lowered for sig in _STR_ERROR_SENTINELS)
        return _truncate(result, 70), is_err

    if isinstance(result, bool):
        return "yes" if result else "no", False

    return _truncate(result, 70), False


def _extract_tool_result_body(block: dict) -> Any:
    tr = block.get("toolResult") or block.get("tool_result")
    if not isinstance(tr, dict):
        return None
    body = tr.get("content")
    if isinstance(body, list) and body:
        head = body[0]
        if isinstance(head, dict):
            body = head.get("text") or head.get("json") or head
    if isinstance(body, str):
        try:
            return json.loads(body)
        except (ValueError, TypeError):
            return body
    return body


async def _run_agent_stream(agent: Agent, prompt: str):
    """Yield SSE events for one agent turn."""
    yield {
        "event": "system_prompt",
        "data": json.dumps({"content": agent.system_prompt or ""}),
    }
    # Echo back the exact message we're about to hand the LLM — including
    # the framed session note. The audience needs to see what the agent
    # actually received, not just what the user typed.
    yield {
        "event": "user_message",
        "data": json.dumps({"content": prompt}),
    }

    pending: dict[str, dict] = {}

    async for event in agent.stream_async(prompt):
        if not isinstance(event, dict):
            continue

        delta = event.get("data")
        if isinstance(delta, str):
            yield {"event": "text_delta", "data": json.dumps({"delta": delta})}

        msg = event.get("message")
        if not isinstance(msg, dict):
            continue
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        role = msg.get("role")

        for block in content:
            if not isinstance(block, dict):
                continue

            if role == "assistant":
                tu = block.get("toolUse") or block.get("tool_use")
                if isinstance(tu, dict):
                    tu_id = tu.get("toolUseId") or tu.get("id")
                    name = tu.get("name")
                    if not tu_id or not name:
                        continue
                    args = tu.get("input") or {}
                    pending[tu_id] = {"name": name, "args": args}
                    yield {
                        "event": "tool_call",
                        "data": json.dumps(
                            {
                                "tool_use_id": tu_id,
                                "name": name,
                                "args": args,
                                "args_summary": _summarize_args(name, args),
                            }
                        ),
                    }
            elif role == "user":
                tr = block.get("toolResult") or block.get("tool_result")
                if not isinstance(tr, dict):
                    continue
                tu_id = tr.get("toolUseId") or tr.get("tool_use_id") or tr.get("id")
                slot = pending.get(tu_id)
                if not slot:
                    continue
                body = _extract_tool_result_body(block)
                summary, is_err = _summarize_result(slot["name"], body)
                yield {
                    "event": "tool_result",
                    "data": json.dumps(
                        {
                            "tool_use_id": tu_id,
                            "result": body,
                            "result_summary": summary,
                            "is_error": is_err,
                        }
                    ),
                }

    # Final reply — pull the last assistant message
    messages = getattr(agent, "messages", []) or []
    final_reply = ""
    for m in reversed(messages):
        if not isinstance(m, dict) or m.get("role") != "assistant":
            continue
        c = m.get("content")
        if isinstance(c, str):
            final_reply = c
            break
        if isinstance(c, list):
            for blk in c:
                if isinstance(blk, dict) and blk.get("text"):
                    final_reply = blk["text"]
                    break
            if final_reply:
                break

    yield {"event": "done", "data": json.dumps({"final_reply": final_reply})}


# ---------------------------------------------------------------------------
# HTTP API
# ---------------------------------------------------------------------------


class RunRequest(BaseModel):
    prompt: str
    customer_id: str  # Accepted for parity with v2's API; v1 does not bind
    #                 — the LLM picks whatever ID the user mentions in the
    #                 prompt. customer_id here is unused server-side, so a
    #                 prompt-injection attack on tenancy actually works.
    model: str | None = None  # Per-request override; falls back to MODEL_ID.


app = FastAPI(title="cs_agent_v1", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    # Vite dev server walks up the port range when its default is taken
    # (5173 → 5174 → 5175). Allow the typical span so the lab doesn't
    # silently fail with CORS errors when another dev server is up.
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):51(7[0-9]|8[0-9])",
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "agent": "cs_agent_v1", "agent_id": AGENT_ID}


@app.get("/api/tools")
def tools_catalog() -> dict[str, Any]:
    """List the tools this agent has, with descriptions and input schemas.
    Tools don't change between requests, so the UI fetches this once per
    panel and renders a drawer next to the conversation."""
    agent = _get_v1_agent()
    return {"tools": agent.tool_registry.get_all_tool_specs()}


@app.post("/api/run")
async def run(req: RunRequest):
    # Shared agent across all requests — `agent.messages` is conversation
    # memory. Mutating `agent.model` applies the per-request model choice
    # without rebuilding (which would wipe the message list). The shared
    # instance is what makes memory leak across customers — the lab's point.
    agent = _get_v1_agent()
    agent.model = OpenAIModel(model_id=req.model or MODEL_ID)

    # The prompt-framing step is in agent.py so the audience can grep
    # one file to see how customer_id ends up in the LLM-visible message.
    framed_prompt = frame_prompt(req.customer_id, req.prompt)

    async def generator():
        try:
            async for ev in _run_agent_stream(agent, framed_prompt):
                yield ev
        except Exception as exc:  # noqa: BLE001
            log.exception("agent stream failed")
            yield {"event": "error", "data": json.dumps({"message": str(exc)})}

    return EventSourceResponse(generator())


@app.post("/api/reset")
def reset() -> dict[str, Any]:
    """Reset this agent's mock data and drop the shared agent instance so
    its `agent.messages` (conversation memory) is wiped on next request."""
    global _V1_AGENT
    _V1_AGENT = None
    reset_state()
    return {"ok": True, "agent": "cs_agent_v1"}


class EndSessionRequest(BaseModel):
    customer_id: str | None = None


@app.post("/api/end_session")
def end_session(req: EndSessionRequest) -> dict[str, Any]:
    """Simulate 'time has passed' for the §5 episodic-memory demo. v1 has a
    single shared Agent across all callers (the leaky-memory footgun), so
    dropping it wipes conversation memory for EVERY customer in one shot —
    which is itself a hint that the "scope" of memory was wrong. v1 also
    has no episodic memory layer, so the next request starts genuinely
    cold. Mock backend state is untouched. The `customer_id` field is
    accepted for parity with v2's API but ignored — there's only one
    shared agent here, not a per-customer cache."""
    global _V1_AGENT
    _V1_AGENT = None
    _ = req.customer_id  # accepted for parity; v1's shared agent ignores it
    return {"ok": True, "agent": "cs_agent_v1", "ended": "all"}
