import type { AgentConfig } from "./config";

export type ChatRequest = { message: string; session_id: string };
export type ChatResponse = { response: string; session_id?: string };

function normalizeAgentUrl(raw: string): string {
  const base = raw.replace(/\/+$/, "");
  return base.endsWith("/chat") ? base : `${base}/chat`;
}

// URL selection rules:
//   - In dev, the Vite proxy at /proxy/agent/* forwards to the URL baked from
//     public/config.js at server start. Same-origin → no CORS preflight.
//   - In a production build (no Vite proxy), we call the agent URL directly,
//     which requires the AM gateway / agent to permit CORS for this origin.
function chatUrl(config: AgentConfig): string {
  if (import.meta.env.DEV) {
    return "/proxy/agent/chat";
  }
  return normalizeAgentUrl(config.url);
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
