"""FastAPI entrypoint for cs_agent_v2 — the hardened, production-shaped agent.

Run:  uvicorn main:app --reload --port 8002

Endpoints:
    POST /api/run    SSE stream of agent events for one prompt.
    POST /api/reset  Wipe this agent's mock data + episodic memory.
    GET  /health     Liveness probe.

The browser fans out the same prompt to v1's port (8001) and this port
(8002) in parallel, then renders the two SSE streams side by side. No
dispatcher service is needed — the merge happens in the frontend.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

# The shared mocks/ package lives at the lab root, next to cs_agent_v2/.
# Put it on sys.path before anything imports it (including MCP subprocesses,
# which inherit our environment).
_LAB_ROOT = Path(__file__).parent.parent
if str(_LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(_LAB_ROOT))

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

# Load .env BEFORE importing the agent — OPENAI_API_KEY must be visible
# to the OpenAI client and to MCP subprocesses (which inherit env).
# Single `Lab-01/.env` at the lab root is the canonical place; a per-agent
# `cs_agent_v2/.env` is supported as an optional override.
load_dotenv(_LAB_ROOT / ".env")
load_dotenv(Path(__file__).parent / ".env", override=False)

from agent.core import ROOT, build_agent, frame_prompt, prepend_memory
from agent.planner import format_tool_specs, plan_for_prompt
from agent.profile import apply_overrides, load_profile
from strands import Agent
from strands.models.openai import OpenAIModel

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("cs_agent_v2")

PROFILE = load_profile()
EPISODIC_DIR = ROOT / "memory" / "episodic"

# Agents are expensive to build (MCP subprocess spawn) and the cached
# instance also IS the conversation memory — `agent.messages` accumulates
# across requests for the same customer, keeping conversation history alive
# for the server's lifetime. Per-customer cache key gives each user their
# own isolated history. In production each customer would map to a
# session/JWT, not a header.
_AGENTS: dict[str, Agent] = {}


def get_agent(customer_id: str, profile=PROFILE) -> Agent:
    if customer_id not in _AGENTS:
        _AGENTS[customer_id] = build_agent(profile=profile, customer_id=customer_id)
    return _AGENTS[customer_id]


# Dedicated catalog agents for /api/tools — one per (skills_enabled,
# episodic_enabled) combo so the drawer reflects the live tool set for
# the current UI toggle state. At most 4 cached instances.
_CATALOG_AGENTS: dict[tuple[bool, bool], Agent] = {}


def _get_catalog_agent(skills_enabled: bool, episodic_enabled: bool) -> Agent:
    key = (skills_enabled, episodic_enabled)
    if key not in _CATALOG_AGENTS:
        profile = apply_overrides(
            PROFILE,
            skills_enabled=skills_enabled,
            episodic_enabled=episodic_enabled,
        )
        _CATALOG_AGENTS[key] = build_agent(profile=profile, customer_id="_catalog")
    return _CATALOG_AGENTS[key]


# ---------------------------------------------------------------------------
# SSE event extraction from Strands' stream_async()
# ---------------------------------------------------------------------------


def _truncate(value: Any, n: int = 60) -> str:
    s = "" if value is None else str(value)
    return s if len(s) <= n else s[: n - 1] + "…"


def _summarize_args(name: str, args: dict | None) -> str:
    if not isinstance(args, dict):
        return _truncate(args)
    if name == "lookup_customer":
        return args.get("customer_id", "?")
    if name == "get_order":
        return args.get("order_id", "?")
    if name in {"get_customer_orders", "get_open_tickets", "get_refund_history"}:
        return args.get("customer_id", "?")
    if name == "search_policy_kb":
        return f'"{_truncate(args.get("query", ""), 40)}"'
    if name == "issue_refund":
        pct = args.get("refund_percentage")
        pct_str = f"{pct:.0%}" if isinstance(pct, (int, float)) else "?"
        return (
            f"{args.get('order_id', '?')}, "
            f"{pct_str}, "
            f'"{_truncate(args.get("reason", ""), 30)}"'
        )
    if name == "escalate_to_human":
        return (
            f"priority={args.get('priority', 'normal')}, "
            f'"{_truncate(args.get("reason", ""), 40)}"'
        )
    if name == "skills":
        return args.get("skill_name", "?")
    return ", ".join(f"{k}={_truncate(v, 25)}" for k, v in args.items())


def _summarize_result(name: str, result: Any) -> tuple[str, bool]:
    """Return (summary, is_error)."""
    if isinstance(result, dict) and "error" in result:
        code = result.get("code")
        detail = result.get("detail") or result.get("error")
        remediation = result.get("remediation")
        bits = [str(code)] if code else []
        bits.append(_truncate(detail, 50))
        if remediation:
            bits.append(f"→ {remediation}")
        return "err: " + " ".join(bits), True
    if name == "lookup_customer" and isinstance(result, dict):
        return f"{result.get('name', '?')}, {result.get('tier', '?')}", False
    if name == "get_order" and isinstance(result, dict):
        status = result.get("status", "?")
        total = result.get("total_usd", "?")
        late = result.get("delivery_days_late", 0)
        late_str = f", {late}d late" if late else ""
        return f"{status}, ${total}{late_str}", False
    if name == "issue_refund" and isinstance(result, dict):
        return f"ok {result.get('ref', '')}, ${result.get('amount_usd', '?')}", False
    if name == "escalate_to_human" and isinstance(result, dict):
        return f"ok {result.get('ticket_id', '')} ({result.get('priority', 'normal')})", False
    if isinstance(result, list):
        return f"[{len(result)} items]", False
    if isinstance(result, str):
        return _truncate(result, 70), False
    if isinstance(result, dict):
        if result.get("ok"):
            ref = result.get("ref") or result.get("ticket_id") or ""
            return f"ok {ref}".strip(), False
        return _truncate(result, 70), False
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
    # Echo the exact message handed to the LLM. v2 doesn't frame anything
    # at the message layer (identity is bound by CustomerIdBindingHook at
    # the tool layer), so this is just the raw prompt.
    yield {
        "event": "user_message",
        "data": json.dumps({"content": prompt}),
    }

    # `system_prompt` is emitted AFTER the stream begins so the AgentSkills
    # plugin (which injects its skills catalog via a BeforeInvocationEvent
    # hook) has had a chance to update `agent.system_prompt` first. If we
    # emitted it before stream_async, the drawer in the UI would show the
    # bare prompt without the "Available skills" catalog.
    system_prompt_emitted = False

    pending: dict[str, dict] = {}  # tool_use_id -> {name, args, emitted_call}

    async for event in agent.stream_async(prompt):
        if not system_prompt_emitted:
            yield {
                "event": "system_prompt",
                "data": json.dumps({"content": agent.system_prompt or ""}),
            }
            system_prompt_emitted = True

        if not isinstance(event, dict):
            continue

        # Streaming text delta for the final reply
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

    # Fallback: if the stream yielded zero events (rare — error before any
    # output), emit the (now-injected) system_prompt so the drawer renders.
    if not system_prompt_emitted:
        yield {
            "event": "system_prompt",
            "data": json.dumps({"content": agent.system_prompt or ""}),
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
    customer_id: str
    model: str | None = None  # Per-request override; falls back to PROFILE.model.
    # UI toggles for v2 features. Null falls back to profile defaults.
    # `skills_enabled` and `episodic_enabled` require a session reset (the
    # agent is cached and its system_prompt / tools / plugins are baked at
    # build time), so the frontend calls /api/reset before sending a request
    # with new values. `planner_enabled` is a per-request decision (the
    # planner is a separate LLM call, not part of the agent build), so it
    # can flip freely without a reset.
    skills_enabled: bool | None = None
    episodic_enabled: bool | None = None
    planner_enabled: bool | None = None


app = FastAPI(title="cs_agent_v2", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):51(7[0-9]|8[0-9])",
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "agent": "cs_agent_v2", "agent_id": PROFILE.agent_id}


@app.get("/api/tools")
def tools_catalog(
    skills_enabled: bool | None = None,
    episodic_enabled: bool | None = None,
) -> dict[str, Any]:
    """List the agent's tools (MCP specs + local episodic-memory tools + the
    AgentSkills loader). The toggle flags scope the result to the live tool
    set for that combo — the UI refetches whenever the toggles flip so the
    drawer matches what the agent actually has."""
    effective_skills = (
        skills_enabled if skills_enabled is not None else bool(PROFILE.skills_dir)
    )
    effective_episodic = (
        episodic_enabled
        if episodic_enabled is not None
        else PROFILE.memory.episodic.enabled
    )
    agent = _get_catalog_agent(effective_skills, effective_episodic)
    return {"tools": agent.tool_registry.get_all_tool_specs()}


@app.get("/api/memory")
def get_memory(customer_id: str) -> dict[str, Any]:
    """Return the episodic-memory file contents for a customer.

    The endpoint is unconditional so the UI can show "empty" vs "missing"
    states. The web frontend gates whether to surface the drawer at all
    behind the v2 episodic_enabled toggle."""
    from agent.memory import _path, load

    return {
        "customer_id": customer_id,
        "exists": _path(customer_id).exists(),
        "content": load(customer_id),
    }


@app.post("/api/run")
async def run(req: RunRequest):
    # Apply UI toggle overrides to a per-request profile copy. From here on
    # the profile IS the source of truth — no separate flag plumbing.
    effective_profile = apply_overrides(
        PROFILE,
        skills_enabled=req.skills_enabled,
        episodic_enabled=req.episodic_enabled,
        planner_enabled=req.planner_enabled,
    )
    print(effective_profile)
    agent = get_agent(req.customer_id, effective_profile)
    # Apply the per-request model choice by mutating the cached agent's
    # model. Conversation memory (`agent.messages`) is untouched, so the
    # same chat continues with a different backend.
    agent.model = OpenAIModel(model_id=req.model or PROFILE.model)

    # frame_prompt lives in agent/core.py — parallels cs_agent_v1's
    # `frame_prompt`. v2's version is a no-op: customer_id is bound by
    # CustomerIdBindingHook, not inlined into the message.
    framed_prompt = frame_prompt(req.customer_id, req.prompt)

    # Planning layer: a small non-streaming LLM call (no tools) that reads
    # the customer message and produces a <plan> block scoping the turn —
    # intent, approach, info_needed, skills, policies. Prepended to the
    # user message so the main agent reads intent BEFORE picking tools.
    # Separating intent recognition from tool selection is what stops the
    # main agent from pattern-matching on "late order → refund" and missing
    # what the customer actually wants. See agent/planner.py.
    #
    # Gated by `profile.planner.enabled` so the UI toggle / YAML flag can
    # flip it off mid-demo to show the regression. The planner sees the
    # LIVE tool surface — tool specs come straight from the cached agent's
    # registry, so adding / removing an MCP tool is auto-reflected in the
    # planner's catalogue. No drift.
    plan = ""
    if effective_profile.planner.enabled:
        planner_model = req.model or PROFILE.model
        try:
            tools_catalogue = format_tool_specs(
                agent.tool_registry.get_all_tool_specs()
            )
            # Only let the planner suggest skills if the main agent
            # actually has the AgentSkills plugin loaded — otherwise the
            # plan would point at procedures the agent can't load.
            plan = await plan_for_prompt(
                req.prompt,
                model=planner_model,
                tools_catalogue=tools_catalogue,
                skills_enabled=bool(effective_profile.skills_dir),
            )
        except Exception:  # noqa: BLE001
            # Planner failures (timeout, rate limit, tool-registry hiccup)
            # shouldn't take the turn down — fall back to the unplanned
            # prompt and let the main agent handle the message as it would
            # have before.
            log.exception("planner call failed; proceeding without a plan")
            plan = ""

    # Episodic memory injection: on the FIRST turn after a fresh Agent build
    # (e.g. right after /api/end_session has cleared the cache), prepend the
    # customer's stored notes inside `<episodic_memory>` tags. We deliberately
    # put memory at the user-message level — not the system prompt — so the
    # LLM weights it as session context, and so the protocol text in the
    # system prompt doesn't drown out the actual notes.
    if not agent.messages and effective_profile.memory.episodic.enabled:
        framed_prompt = prepend_memory(
            req.customer_id,
            framed_prompt,
            compact_threshold=effective_profile.memory.episodic.compact_threshold,
        )

    # Plan goes above the memory + message, since intent is the first thing
    # the model should read. Order in the final user message:
    #   <plan>…</plan>
    #   <episodic_memory>…</episodic_memory>   (only on the first turn of a session)
    #   <customer's actual message>
    if plan:
        framed_prompt = f"{plan}\n\n{framed_prompt}"

    async def generator():
        # Emit the plan as its own SSE event so the trace UI can render it
        # as a distinct step before tool calls start. Frontend that doesn't
        # know about this event type will silently drop it.
        if plan:
            yield {"event": "plan", "data": json.dumps({"content": plan})}
        try:
            async for ev in _run_agent_stream(agent, framed_prompt):
                yield ev
        except Exception as exc:  # noqa: BLE001
            log.exception("agent stream failed")
            yield {"event": "error", "data": json.dumps({"message": str(exc)})}

    return EventSourceResponse(generator())


@app.post("/api/reset")
def reset() -> dict[str, Any]:
    """Reset writable state: wipe v2's mock data on disk and reseed,
    rebuild agents (which respawns MCP subprocesses that re-read the
    fresh data files), clear non-seed episodic memory."""
    # Mock data is file-backed on disk and scoped per-agent — wiping
    # v2's files here leaves v1's state alone. The freshly spawned v2
    # MCP subprocesses on the next /api/run pull from seeds.
    from mocks.client import reset_data_files
    reset_data_files(PROFILE.agent_id)

    # Dropping cached agents triggers a fresh build (and fresh MCP subprocesses
    # that read the now-reseeded data files) on the next request.
    _AGENTS.clear()

    # Episodic memory: drop everything EXCEPT the committed seed (cust_002).
    if EPISODIC_DIR.exists():
        for f in EPISODIC_DIR.glob("customer_*.md"):
            if f.name != "customer_cust_002.md":
                f.unlink()

    return {"ok": True, "agent": "cs_agent_v2"}


class EndSessionRequest(BaseModel):
    customer_id: str | None = None


@app.post("/api/end_session")
def end_session(req: EndSessionRequest) -> dict[str, Any]:
    """Simulate 'time has passed' for the §5 episodic-memory demo. Drops the
    cached Agent for the given customer so the next request rebuilds it
    fresh — which wipes `agent.messages` (conversation memory) but RELOADS
    the customer's episodic memory file into the new system prompt. Mock
    backend state (orders, refunds, tickets) is untouched."""
    if req.customer_id:
        _AGENTS.pop(req.customer_id, None)
    else:
        _AGENTS.clear()
    return {"ok": True, "agent": "cs_agent_v2", "ended": req.customer_id or "all"}
