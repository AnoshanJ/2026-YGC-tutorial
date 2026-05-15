"""LangGraph CS agent construction.

Builds a ReAct-style agent bound to the instance config. Uses OpenAI via
``ChatOpenAI``; the API key is read from ``OPENAI_API_KEY`` at startup.
"""

from __future__ import annotations

from typing import Any

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from config import Config
from tools import build_tools

MODEL = "gpt-4o-mini"

SYSTEM_PROMPT_TEMPLATE = (
    "You are a customer support agent for {company_name}, serving the {region} region. "
    "Primary language: {language}. Currency: {currency}.\n\n"
    "You can look up customers, orders, and policies; update shipping; cancel orders; "
    "and issue refunds up to {refund_cap} {currency}. For amounts above the cap, "
    "always escalate via escalate_to_human — do not approximate, do not partial-refund.\n\n"
    "Always cite the relevant policy before issuing a refund or making a cancellation. "
    "Use search_policy_kb first when policy is involved.\n\n"
    "Tone: {tone}. {additional_guidance}"
)


def build_agent(cfg: Config) -> Any:
    llm = ChatOpenAI(model=MODEL, temperature=0)
    tools = build_tools(cfg)
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        company_name=cfg.company_name,
        region=cfg.region.upper(),
        language=cfg.language,
        currency=cfg.currency,
        refund_cap=cfg.refund_cap,
        tone=cfg.tone,
        additional_guidance=cfg.additional_guidance,
    )
    return create_react_agent(model=llm, tools=tools, prompt=system_prompt)
