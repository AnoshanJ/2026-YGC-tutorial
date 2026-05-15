# triage-agent — Order Triage Crew (CrewAI, API-type)

Multi-agent CrewAI service that classifies, routes, drafts, and verifies a response to an inbound customer support email. Uses OpenAI's `gpt-4o-mini` for all sub-agents. Used as the *external* working agent in WSO2Con Lab 3 — the showcase for agent-level OTEL span hierarchies.

## AM contract — API-type (custom-api)

| Aspect | Spec |
|---|---|
| Agent type | `api` / sub-type `custom-api` |
| Interface type | `OPENAPI` (declared via `InputInterface.SchemaPath`) |
| Schema path | [`openapi.yaml`](openapi.yaml) (this agent's root) |
| Port | `8001` (set via `runCommand` / `InputInterface.Port`) |
| Auth | Optional `X-API-Key` (when `enableApiKeySecurity=true`) |
| Routes | Declared in `openapi.yaml` — `POST /triage` and `GET /health` |

## Crew

Sequential CrewAI process, four sub-agents:

1. **Email Classifier** — categorize (refund_request / shipping_question / product_question / complaint / other) with confidence.
2. **Team Router** — pick the owning team via `lookup_team_roster`, set priority.
3. **Response Drafter** — write a concise reply, grounding policy claims via `search_policy_kb` and `lookup_order_status`.
4. **Response Verifier** — `tone_check` + `policy_compliance_check`; emit `approved` or `needs_revision`.

Each sub-agent produces its own OTEL agent-span via AM's auto-instrumentation. The resulting trace shape is the multi-agent contrast point against `cs-agent`'s single-agent trace.

## Build & deploy via AM

Buildpack-based — no Dockerfile. AM detects Python via `requirements.txt`. Run command: `uvicorn app:app --host 0.0.0.0 --port 8001`.

OTEL is handled by AM's auto-instrumentation trait at deploy time; the agent code does not set up OTEL itself.

## Environment

| Var | Required | Default | Meaning |
|---|---|---|---|
| `OPENAI_API_KEY` | yes | — | OpenAI credentials |

## Run locally

```bash
cd agents/triage-agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

export OPENAI_API_KEY=...
uvicorn app:app --host 0.0.0.0 --port 8001
```

```bash
curl -s -X POST localhost:8001/triage \
  -H 'Content-Type: application/json' \
  -d '{
        "from": "ava@example.com",
        "subject": "refund for order 5001",
        "body": "My headphones arrived broken. Please refund. Order 5001."
      }' | jq
```

## Sample demo queries

Each request runs the full four-sub-agent pipeline. The interesting beat in the trace view is the **multi-agent span hierarchy**: one orchestrator span containing four sub-agent spans (`Classifier`, `Router`, `Drafter`, `Verifier`), each with their own tool spans. Pick a couple of these for the live demo — they exercise distinct branches.

### One per category — classifier accuracy + routing variety

```bash
# refund_request → refunds-team
curl -s -X POST localhost:8001/triage -H 'Content-Type: application/json' -d '{
  "from":"ava.morgan@example.com",
  "subject":"refund for order 5001",
  "body":"My wireless headphones (order 5001) arrived with a cracked earcup. I would like a refund please."
}' | jq

# shipping_question → shipping-team (drafter calls lookup_order_status)
curl -s -X POST localhost:8001/triage -H 'Content-Type: application/json' -d '{
  "from":"lukas.weber@example.de",
  "subject":"Where is order 2001?",
  "body":"Hello, I placed order 2001 a week ago and have heard nothing. Can you check tracking?"
}' | jq

# product_question → product-team (drafter cites Product Questions policy)
curl -s -X POST localhost:8001/triage -H 'Content-Type: application/json' -d '{
  "from":"priya.nair@example.in",
  "subject":"power bank charging speed",
  "body":"Hi! Quick question — does the 20k power bank support fast charging for iPhones?"
}' | jq
```

### Verifier flags — needs_revision branch

```bash
# Complaint that the drafter MUST escalate. If the draft does not contain
# escalation language, policy_compliance_check returns
# {compliant:false, findings:["complaint_without_escalation"]} and the
# verifier emits verdict=needs_revision.
curl -s -X POST localhost:8001/triage -H 'Content-Type: application/json' -d '{
  "from":"marie.dubois@example.fr",
  "subject":"TERRIBLE experience",
  "body":"This is the third order that has been delayed. Your customer service is awful. I want to speak with a manager NOW."
}' | jq

# PII in the body. If the drafter echoes the card number back,
# policy_compliance_check returns findings:["contains_pii"] and the
# verifier emits verdict=needs_revision. A well-behaved drafter omits it.
curl -s -X POST localhost:8001/triage -H 'Content-Type: application/json' -d '{
  "from":"noah.brown@example.com",
  "subject":"double charge on order 1500",
  "body":"My card 4111 1111 1111 1111 was charged twice for order 1500. Please refund the duplicate."
}' | jq
```

### Low-confidence classification (escalations route)

```bash
# Vague, no actionable content. Classifier confidence drops; category falls to "other".
# Router sends it to escalations-team. Useful to show "the system asks for help when uncertain."
curl -s -X POST localhost:8001/triage -H 'Content-Type: application/json' -d '{
  "from":"kai.hayashi@example.jp",
  "subject":"hi",
  "body":"hey just checking in"
}' | jq
```

### Recommended demo sequence

For a 60-second crew showcase pick **three** queries that visit different branches:

1. The **refund** query above — clean classify → route → draft → verify → approved. Shows the canonical 4-sub-agent span tree.
2. The **complaint** query — same shape but verifier flags `needs_revision`. Lets you point at the verifier's `policy_compliance_check` tool span and explain "this is why we have a verifier."
3. The **low-confidence** query — confidence attribute visible on the classifier span. Lets you call out OTEL span attributes carrying classifier confidence as a teaching moment for Lab 4's evaluator design.

