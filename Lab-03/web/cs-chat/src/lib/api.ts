import { getSeedConfig, type AgentConfig } from "./config";

export type ChatRequest = { message: string; session_id: string };
export type ChatResponse = { response: string; session_id?: string };

function normalizeAgentUrl(raw: string): string {
  const base = raw.replace(/\/+$/, "");
  return base.endsWith("/chat") ? base : `${base}/chat`;
}

// URL selection rules:
//   - In dev, the Vite proxy at /proxy/agent/* forwards to the URL baked from
//     public/config.js at server start. We use it whenever the *current* URL
//     matches the seed URL — regardless of whether it came from config.js or
//     a Settings-dialog override that just happens to point at the same place.
//     Same-origin → no CORS preflight.
//   - Otherwise (the override URL is different, or we're in a prod build),
//     we call the agent URL directly. That path needs the AM gateway / agent
//     to permit CORS for the page origin.
function chatUrl(config: AgentConfig): string {
  const target = normalizeAgentUrl(config.url);
  if (import.meta.env.DEV) {
    const seed = getSeedConfig();
    if (seed && normalizeAgentUrl(seed.url) === target) {
      return "/proxy/agent/chat";
    }
  }
  return target;
}

// Customer identity travels in the request body's `context` field, per the
// AM chat-agent contract (POST /chat with {message, session_id, context}).
// The agent reads context.customer_id, loads the full profile server-side,
// and never asks the user to identify themselves.
export async function sendChat(
  config: AgentConfig,
  customerId: string,
  req: ChatRequest,
): Promise<ChatResponse> {
  const resp = await fetch(chatUrl(config), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-api-key": config.apiKey,
    },
    body: JSON.stringify({
      ...req,
      context: { customer_id: customerId },
    }),
  });
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`HTTP ${resp.status}: ${text || resp.statusText}`);
  }
  return (await resp.json()) as ChatResponse;
}
