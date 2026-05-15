# Agents

Two real agents used end-to-end in WSO2Con Labs 3 and 4.

| Agent | Framework | Hosting | Role in the labs |
|---|---|---|---|
| [cs-agent](cs-agent/) | LangGraph | Platform-hosted (built by AM) | Lifecycle demo subject (kind → instances → version update). Single-agent trace shape. |
| [triage-agent](triage-agent/) | CrewAI | External (Fly.io / local Docker) | Multi-agent showcase: classifier → router → drafter → verifier. Hierarchical trace shape. |

Both agents use **in-process mocked backends** under each agent's `clients/` directory — no external service deployment. The tool layer in `tools.py` is the only thing that talks to those clients, keeping mock concerns isolated.

OTEL is wired via OpenInference instrumentation (LangChain and CrewAI). Set `OTEL_EXPORTER_OTLP_ENDPOINT` to enable trace export; leaving it unset lets the agents run offline cleanly.
