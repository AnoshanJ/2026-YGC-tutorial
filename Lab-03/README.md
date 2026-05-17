# 2026 AUS AI Tutorial — WSO2Con

Source for WSO2Con's AI tutorials — two demo agents (customer support + order triage) and the chat UI used in the Agent Manager Lifecycle and Trust sessions.

## Layout

```
agents/
├── cs-agent/         LangGraph + OpenAI customer-support agent — AM chat-type (POST /chat, port 8000)
├── triage-agent/     CrewAI + OpenAI Order Triage Crew — AM API-type (openapi.yaml, port 8001)
└── mock_agent/       Stdlib placeholder for AM catalog variety (port 8002)
web/
└── cs-chat/          Vite + React chat UI for the deployed cs-agent
```

Neither agent ships a Dockerfile — Agent Manager builds Python agents via Google Cloud Buildpacks. Local runs use `pip install` + `uvicorn` directly. OTEL is handled by AM's auto-instrumentation trait at deploy time.

## Agents

Both agents use in-process mocked backends — no external API calls. Mock behavior lives in each agent's `clients/` so tool logic stays clean of mock concerns.

- `agents/cs-agent` — LangGraph + OpenAI `gpt-4o-mini`, single-agent, AM chat-type. Tools: `lookup_customer`, `get_order`, `get_customer_orders`, `search_policy_kb`, `update_shipping_address`, `cancel_order`, `issue_refund` (enforces `REFUND_CAP`), `escalate_to_human`.
- `agents/triage-agent` — CrewAI + OpenAI `gpt-4o-mini`, sequential crew (Classifier → Router → Drafter → Verifier), AM API-type, `openapi.yaml` declares the surface.

## Local quick start

```bash
# CS agent
cd agents/cs-agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY=...  REGION=na CURRENCY=USD REFUND_CAP=200
python main.py

curl -s -X POST localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"test-1","message":"where is order 1234","context":{}}' | jq
```

```bash
# Triage agent
cd agents/triage-agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY=...
python main.py

curl -s -X POST localhost:8001/triage \
  -H 'Content-Type: application/json' \
  -d '{"from":"a@b.com","subject":"refund please","body":"Order 5001 arrived broken"}' | jq
```
