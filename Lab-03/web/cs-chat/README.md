# cs-chat — chat UI for the Lab-03 CS agent

Vite + React + TypeScript + Tailwind + shadcn/ui. Mock-login screen + chat panel that talks to the deployed `lab-03-cs-agent` via the AM gateway.

## What it shows

- A polished "real product" login screen. Email picks the persona from the same 10 customers in [`../../agents/cs-agent/data/customers.json`](../../agents/cs-agent/data/customers.json). Password is ignored (mock auth — never sent anywhere).
- A chat page with a top bar (logged-in customer, tier + region badges), a sidebar with suggested prompts, message bubbles, and a typing indicator.
- Each chat message becomes a `POST {AGENT_URL}/chat` with the `x-api-key` header (from `config.js`) and `context.customer_id` in the request body (the logged-in user's id, per the AM chat-agent spec).
- The agent loads the customer's full profile server-side and emits OTEL span attributes (`customer.id`, `customer.tier`, `customer.region`, `session.id`) on every trace's root span — so the AM console can filter traces by customer with one click.

## Setup

Install once (Node 18+):

```bash
cd Lab-03/web/cs-chat
npm install
```

## Configure the agent connection

The app reads the agent URL + API key from `public/config.js`. Create it once:

```bash
cd public
cp config.sample.js config.js
# edit config.js — paste your agent's runtime URL and an API key
```

```js
// public/config.js
window.AGENT_CONFIG = {
  url: "https://your-am-gateway/agents/lab-03-cs-agent/default",
  apiKey: "sk_..."
};
```

### CORS + the Vite dev proxy

The AM gateway doesn't send CORS headers, so direct browser-to-gateway calls fail. To work around it, the Vite dev server proxies all chat requests through `/proxy/agent/*` — the browser only ever makes same-origin calls.

The proxy target is read from `public/config.js` **at dev-server startup**. After editing `config.js`, **restart `npm run dev`** so the new target is picked up.

## Run

Two terminals.

**Terminal 1 — generate config.js by running seed-2:**

```bash
cd Lab-03/seed
bash seed-2.sh           # writes ../web/cs-chat/public/config.js
```

**Terminal 2 — start the dev server:**

```bash
cd Lab-03/web/cs-chat
npm run dev              # serves on http://localhost:5173
```

Open <http://localhost:5173>. Sign in with any demo email below, type any password.

## Demo accounts

| Email | Customer | Tier | Region |
|---|---|---|---|
| `ava.morgan@example.com` | Ava Morgan · C-1001 | gold | NA |
| `lukas.weber@example.de` | Lukas Weber · C-1002 | silver | EMEA |
| `sora.tanaka@example.jp` | Sora Tanaka · C-1003 | gold | APAC |
| `diego.alvarez@example.com` | Diego Alvarez · C-1004 | bronze | NA |
| `marie.dubois@example.fr` | Marie Dubois · C-1005 | platinum | EMEA |
| `kai.hayashi@example.jp` | Kai Hayashi · C-1006 | silver | APAC |
| `olivia.smith@example.com` | Olivia Smith · C-1007 | gold | NA |
| `hans.muller@example.de` | Hans Muller · C-1008 | bronze | EMEA |
| `priya.nair@example.in` | Priya Nair · C-1009 | silver | APAC |
| `noah.brown@example.com` | Noah Brown · C-1010 | platinum | NA |

Full list in [`src/lib/users.ts`](src/lib/users.ts).

## Project layout

```
src/
├── main.tsx           — entry, mounts <App/>
├── App.tsx            — router (RequireAuth wraps /chat)
├── index.css          — Tailwind + shadcn theme tokens
├── lib/
│   ├── auth.ts        — localStorage-backed login + session id
│   ├── users.ts       — hardcoded customer directory
│   ├── api.ts         — POST /chat fetch wrapper
│   ├── config.ts      — bridge to window.AGENT_CONFIG (from /config.js)
│   └── utils.ts       — cn() + initials()
├── routes/
│   ├── Login.tsx      — marketing pitch + auth card
│   └── Chat.tsx       — top bar + sidebar + message list + composer
├── components/
│   ├── TopBar.tsx
│   ├── Sidebar.tsx
│   ├── MessageBubble.tsx
│   ├── Composer.tsx
│   └── ui/            — shadcn primitives (button, input, card, …)
public/
└── config.js          — gitignored; written by seed-2.sh
```
