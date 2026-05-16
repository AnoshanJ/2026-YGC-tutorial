# triage-agent — Order Triage Crew (CrewAI)

Multi-agent CrewAI service that classifies, routes, drafts, and verifies a response to an inbound customer support email. Uses OpenAI's `gpt-4o-mini` for all sub-agents.

Registered in AM as an **external** agent — not built or hosted by AM. The agent runs on the demo lead's machine (or anywhere with outbound HTTPS to the AM traces observer) and pushes OTEL spans into AM via amp-instrumentation. Its AM record auto-attaches the first time a span is received.

## Crew

Sequential CrewAI process, four sub-agents:

1. **Email Classifier** — categorize (refund_request / shipping_question / product_question / complaint / other) with confidence.
2. **Team Router** — pick the owning team via `lookup_team_roster`, set priority.
3. **Response Drafter** — write a concise reply, grounding policy claims via `search_policy_kb` and `lookup_order_status`.
4. **Response Verifier** — `tone_check` + `policy_compliance_check`; emit `approved` or `needs_revision`.

Each sub-agent produces its own OTEL agent-span via amp-instrumentation. The resulting trace shape is the multi-agent contrast point against `cs-agent`'s single-agent trace.

## How OTEL push works

`amp-instrument` is the CLI wrapper bundled with `amp-instrumentation` (a separate pip package — see `seed-2.sh`, which installs it into a venv at first run). It:

- Loads OTEL auto-instrumentation hooks for CrewAI, OpenAI, LangChain, etc. via the standard Python `sitecustomize` mechanism, so they fire on `import` regardless of how the agent code is structured.
- Wires the OTEL SDK's HTTP exporter to `AMP_OTEL_ENDPOINT` and authenticates spans with `AMP_AGENT_API_KEY`. Both env vars must be set in the process environment.

Run-time contract:

| Var | Required | Source |
|---|---|---|
| `AMP_OTEL_ENDPOINT` | yes | seed/.env (defaults to `http://localhost:22893/otel` locally) |
| `AMP_AGENT_API_KEY` | yes | minted by `POST /api/v1/orgs/{org}/projects/{proj}/agents/{name}/token?environment={env}` — seed-2 does this automatically |
| `OPENAI_API_KEY`    | yes | seed/.env — the crew calls OpenAI directly |

## Run via seed-2 (recommended)

```bash
cd Lab-03/seed
bash seed-2.sh
```

`seed-2.sh` creates a venv under `agents/triage-agent/.venv` (one-time, ~1 min), installs `requirements.txt` + `amp-instrumentation`, fetches the AMP token, exports it along with `AMP_OTEL_ENDPOINT` + `OPENAI_API_KEY`, and starts the agent in the background. PID + log are stored in `seed/.seed-cache/`. Stop with:

```bash
kill $(cat Lab-03/seed/.seed-cache/triage-agent.pid)
```

## Run manually

```bash
cd Lab-03/agents/triage-agent
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt amp-instrumentation==0.1.7

export OPENAI_API_KEY=...
export AMP_OTEL_ENDPOINT=http://localhost:22893/otel
export AMP_AGENT_API_KEY=$(curl -sS -X POST \
  -H "Authorization: Bearer $AM_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"expires_in":"8760h"}' \
  "http://localhost:9000/api/v1/orgs/default/projects/lab-03/agents/lab-03-triage-agent/token?environment=default" \
  | jq -r '.apiKey // .token')

amp-instrument python main.py
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

