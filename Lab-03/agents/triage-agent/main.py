"""Entrypoint for the Order Triage Crew (CrewAI, multi-agent).

Run locally (not via the AM build path) as an external agent:

    AMP_OTEL_ENDPOINT="http://localhost:22893/otel"   # AM traces observer
    AMP_AGENT_API_KEY="<from POST /agents/<name>/token>"
    amp-instrument python main.py

``amp-instrument`` is a CLI shipped with the ``amp-instrumentation`` package;
it injects OTEL auto-instrumentation for CrewAI / OpenAI / LangChain at
interpreter startup. Traces are pushed to AMP_OTEL_ENDPOINT and the agent's
record in AM auto-registers (or attaches) on the first span.

``seed-2.sh`` handles the env wiring + process management for the demo.
"""

from __future__ import annotations

import uvicorn

from app import app


def main() -> None:
    uvicorn.run(app, host="0.0.0.0", port=8001)


if __name__ == "__main__":
    main()
