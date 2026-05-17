import type { AgentConfig } from "./config";

export type ChatRequest = { message: string; session_id: string };
export type ChatResponse = { response: string; session_id?: string };

// In dev, calls go through the Vite proxy (/proxy/agent/*) — same-origin from
// the browser's perspective, so no CORS preflight is involved. The proxy's
// target is set in vite.config.ts from public/config.js.
//
// In a built bundle (no Vite proxy), we fall back to the direct URL from
// config.apiKey + config.url. That path needs the AM gateway to permit CORS,
// which is typically not configured for arbitrary origins — so production
// deploys will need their own reverse proxy.
function chatUrl(config: AgentConfig): string {
  if (import.meta.env.DEV) {
    return "/proxy/agent/chat";
  }
  return config.url.replace(/\/+$/, "") + "/chat";
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
