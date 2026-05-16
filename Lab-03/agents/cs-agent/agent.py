"""LangGraph CS agent construction.

Builds a ReAct-style agent bound to the instance config. Uses OpenAI via
``ChatOpenAI``; the API key is read from ``OPENAI_API_KEY`` at startup.

The graph itself is built once at startup with no system prompt — ``app.py``
composes the per-request system message (including the authenticated
customer's profile) and prepends it to the message list before invoking.
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from config import Config
from tools import build_tools

MODEL = "gpt-4o-mini"

SYSTEM_PROMPT_TEMPLATE = (
    "You are a customer support agent for {company_name}, serving the {region} region. "
    "Primary language: {language}. Currency: {currency}.\n\n"
    "You are currently talking to {customer_name} (id: {customer_id}, tier: {customer_tier}, region: {customer_region}). "
    "You already have their identity — do NOT ask for their email or look them up again. "
    "When you need their orders, call get_customer_orders with customer_id={customer_id}.\n\n"
    "You can look up orders and policies; update shipping; cancel orders; and issue refunds "
    "up to {refund_cap} {currency}. For amounts above the cap, always escalate via "
    "escalate_to_human — do not approximate, do not partial-refund.\n\n"
    "Always cite the relevant policy before issuing a refund or making a cancellation. "
    "Use search_policy_kb first when policy is involved.\n\n"
    "If a customer references an order that does not belong to them, refuse the action and "
    "explain — do not act on another customer's order.\n\n"
    "Tone: {tone}. {additional_guidance}"
)


def build_agent(cfg: Config) -> Any:
    llm = ChatOpenAI(model=MODEL, temperature=0)
    tools = build_tools(cfg)
    return create_react_agent(model=llm, tools=tools)


def system_message_for(cfg: Config, customer: dict[str, Any]) -> SystemMessage:
    content = SYSTEM_PROMPT_TEMPLATE.format(
        company_name=cfg.company_name,
        region=cfg.region.upper(),
        language=cfg.language,
        currency=cfg.currency,
        refund_cap=cfg.refund_cap,
        tone=cfg.tone,
        additional_guidance=cfg.additional_guidance,
        customer_name=customer.get("name", "(unknown)"),
        customer_id=customer.get("id", "(unknown)"),
        customer_tier=customer.get("tier", "standard"),
        customer_region=customer.get("region", cfg.region).upper(),
    )
    return SystemMessage(content=content)
