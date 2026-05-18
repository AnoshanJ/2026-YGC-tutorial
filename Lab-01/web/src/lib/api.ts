// SSE client over fetch + ReadableStream.
//
// We can't use the browser's native `EventSource` because it only supports
// GET. The agents accept POST with a JSON body, so we read the streamed
// response manually and parse SSE frames as they arrive.
//
// Frame format (per https://html.spec.whatwg.org/multipage/server-sent-events.html):
//   event: <type>\n
//   data: <payload>\n
//   \n
// Multiple `data:` lines per frame are joined with newlines; we only emit
// a single-line JSON per event so we don't bother handling multi-line.

import type { AgentEvent, AgentVariant } from "./types";

// Model choices shown in the header dropdown. Both backends accept any
// string in their `model` field and pass it straight to OpenAIModel; this
// list just constrains what the UI offers.
export const SUPPORTED_MODELS = [
  "gpt-5.4",
  "gpt-5.4-mini",
  "gpt-5",
  "gpt-5-mini",
] as const;
export type SupportedModel = (typeof SUPPORTED_MODELS)[number];
export const DEFAULT_MODEL: SupportedModel = "gpt-5-mini";

export interface AgentService {
  variant: AgentVariant;
  baseUrl: string;
  label: string;       // e.g. "Customer Support · v1"
  caption: string;     // e.g. "cs-agent-v1"
}

export const AGENTS: Record<AgentVariant, AgentService> = {
  v1: {
    variant: "v1",
    baseUrl: "http://localhost:8001",
    label: "Customer Support · v1",
    caption: "cs-agent-v1",
  },
  v2: {
    variant: "v2",
    baseUrl: "http://localhost:8002",
    label: "Customer Support · v2",
    caption: "cs-agent-v2",
  },
};

export interface RunArgs {
  prompt: string;
  customer_id: string;
  model?: string;
  signal?: AbortSignal;
  onEvent: (ev: AgentEvent) => void;
}

/** POST /api/run and stream SSE events through `onEvent`. */
export async function runAgent(svc: AgentService, args: RunArgs): Promise<void> {
  const response = await fetch(`${svc.baseUrl}/api/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      prompt: args.prompt,
      customer_id: args.customer_id,
      ...(args.model ? { model: args.model } : {}),
    }),
    signal: args.signal,
  });

  if (!response.ok || !response.body) {
    throw new Error(`${svc.variant} /api/run returned ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    // Normalize line endings as we go. The SSE spec allows \r\n, \r, or
    // \n; sse-starlette emits strict \r\n. Stripping \r lets us split on
    // \n\n regardless of which server we're talking to.
    buffer += decoder.decode(value, { stream: true }).replace(/\r/g, "");

    // Frames are separated by blank lines (\n\n). Process every complete
    // frame in the buffer; keep the partial tail for the next read.
    let sep = buffer.indexOf("\n\n");
    while (sep !== -1) {
      const frame = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      sep = buffer.indexOf("\n\n");
      handleFrame(frame, args.onEvent);
    }
  }

  // Flush any remaining frame (partial reads at EOF).
  if (buffer.trim()) {
    handleFrame(buffer, args.onEvent);
  }
}

function handleFrame(frame: string, onEvent: (ev: AgentEvent) => void): void {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of frame.split("\n")) {
    if (line.startsWith(":")) continue; // SSE comment / keepalive ping
    if (line.startsWith("event:")) {
      event = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trim());
    }
  }
  if (!dataLines.length) return;
  const payload = dataLines.join("\n");
  let parsed: unknown;
  try {
    parsed = JSON.parse(payload);
  } catch {
    return; // Drop unparseable frames silently.
  }
  if (typeof parsed !== "object" || parsed === null) return;
  onEvent({ ...(parsed as object), type: event } as AgentEvent);
}

/** POST /api/reset. Fire-and-forget. */
export async function resetAgent(svc: AgentService): Promise<void> {
  const response = await fetch(`${svc.baseUrl}/api/reset`, { method: "POST" });
  if (!response.ok) {
    throw new Error(`${svc.variant} /api/reset returned ${response.status}`);
  }
}

/** POST /api/end_session — simulates time passing for the episodic-memory
 *  demo. Drops the cached Agent (clears conversation memory) but preserves
 *  the customer's episodic memory file on disk and the mock backend state. */
export async function endSession(svc: AgentService, customerId: string): Promise<void> {
  const response = await fetch(`${svc.baseUrl}/api/end_session`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ customer_id: customerId }),
  });
  if (!response.ok) {
    throw new Error(`${svc.variant} /api/end_session returned ${response.status}`);
  }
}

/** One tool entry as returned by the agent's tool registry. */
export interface AgentTool {
  name: string;
  description?: string;
  inputSchema?: {
    json?: {
      properties?: Record<string, { type?: string; description?: string }>;
      required?: string[];
    };
  };
}

/** GET /api/tools — list of tools this agent has registered.
 *  Static for the server's lifetime; UI fetches once per panel. */
export async function fetchTools(svc: AgentService): Promise<AgentTool[]> {
  const response = await fetch(`${svc.baseUrl}/api/tools`);
  if (!response.ok) {
    throw new Error(`${svc.variant} /api/tools returned ${response.status}`);
  }
  const body = (await response.json()) as { tools?: AgentTool[] };
  return body.tools ?? [];
}
