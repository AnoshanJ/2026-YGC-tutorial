// Conversation knowledge-graph extractor.
//
// After each assistant turn we send the recent dialogue to OpenAI and ask it
// to return a structured snapshot of everything Aria has touched: orders,
// refunds, address changes, cancellations, policy mentions, escalations.
// The UI replaces its graph state with the returned snapshot.
//
// The OpenAI key is read from localStorage (set via the Settings dialog).
// Calls go directly from the browser to api.openai.com — fine for a demo,
// but the key is visible to anyone with devtools, so don't reuse it.

import type { Message } from "@/components/MessageBubble";

const OPENAI_KEY_STORAGE = "nw-openai-key";
const ENDPOINT = "https://api.openai.com/v1/chat/completions";
const MODEL = "gpt-5.4-mini";

/* ---------- key management --------------------------------------------- */

const keyListeners = new Set<() => void>();

export function getOpenAIKey(): string | null {
  try {
    const v = localStorage.getItem(OPENAI_KEY_STORAGE);
    return v && v.trim() ? v.trim() : null;
  } catch {
    return null;
  }
}

export function setOpenAIKey(key: string) {
  localStorage.setItem(OPENAI_KEY_STORAGE, key.trim());
  keyListeners.forEach((fn) => fn());
}

export function clearOpenAIKey() {
  localStorage.removeItem(OPENAI_KEY_STORAGE);
  keyListeners.forEach((fn) => fn());
}

export function subscribeOpenAIKey(fn: () => void) {
  keyListeners.add(fn);
  return () => {
    keyListeners.delete(fn);
  };
}

/* ---------- graph schema ------------------------------------------------ */

export type Order = {
  order_id: string;
  status?: string | null;
  total?: string | null;
  eta?: string | null;
  items?: string[] | null;
  summary: string;
};
export type Refund = {
  order_id?: string | null;
  amount?: string | null;
  status?: string | null;
  reason?: string | null;
  summary: string;
};
export type AddressChange = {
  order_id?: string | null;
  new_address: string;
  summary: string;
};
export type Cancellation = { order_id: string; summary: string };
export type PolicyMention = { topic: string; summary: string };
export type Escalation = { reason: string; summary: string };

export type KnowledgeGraph = {
  orders: Order[];
  refunds: Refund[];
  address_changes: AddressChange[];
  cancellations: Cancellation[];
  policies: PolicyMention[];
  escalations: Escalation[];
};

export const EMPTY_GRAPH: KnowledgeGraph = {
  orders: [],
  refunds: [],
  address_changes: [],
  cancellations: [],
  policies: [],
  escalations: [],
};

export function isEmptyGraph(g: KnowledgeGraph): boolean {
  return (
    g.orders.length === 0 &&
    g.refunds.length === 0 &&
    g.address_changes.length === 0 &&
    g.cancellations.length === 0 &&
    g.policies.length === 0 &&
    g.escalations.length === 0
  );
}

/* ---------- extraction call -------------------------------------------- */

const SYSTEM_PROMPT = `You extract a structured knowledge graph from a customer-support conversation.

The conversation is between a customer and "Aria", a retail concierge for "Northwind".
Your job is to read the full conversation and return EVERYTHING that has been mentioned
or acted on: orders, refunds, address changes, cancellations, policy references, and
escalations to human agents.

Rules:
- Return the COMPLETE snapshot of all entities visible across the whole conversation,
  not just the latest turn. Re-extract from scratch every call.
- Use order IDs exactly as written (e.g. "N-4827", "5001"). If no order ID is present,
  set order_id to null.
- "summary" is a one-sentence, customer-friendly description in plain English
  (no order IDs in the summary unless natural).
- If the assistant says it WILL do something but it hasn't happened yet, include it
  but mark status accordingly (e.g. "pending", "in progress").
- Only include policies the assistant actually explained or quoted, not generic mentions.
- Skip small talk, greetings, clarifying questions.
- If nothing of a given type is present, return an empty array for that field.`;

const SCHEMA = {
  type: "object",
  additionalProperties: false,
  properties: {
    orders: {
      type: "array",
      items: {
        type: "object",
        additionalProperties: false,
        properties: {
          order_id: { type: "string" },
          status: { type: ["string", "null"] },
          total: { type: ["string", "null"] },
          eta: { type: ["string", "null"] },
          items: { type: ["array", "null"], items: { type: "string" } },
          summary: { type: "string" },
        },
        required: ["order_id", "status", "total", "eta", "items", "summary"],
      },
    },
    refunds: {
      type: "array",
      items: {
        type: "object",
        additionalProperties: false,
        properties: {
          order_id: { type: ["string", "null"] },
          amount: { type: ["string", "null"] },
          status: { type: ["string", "null"] },
          reason: { type: ["string", "null"] },
          summary: { type: "string" },
        },
        required: ["order_id", "amount", "status", "reason", "summary"],
      },
    },
    address_changes: {
      type: "array",
      items: {
        type: "object",
        additionalProperties: false,
        properties: {
          order_id: { type: ["string", "null"] },
          new_address: { type: "string" },
          summary: { type: "string" },
        },
        required: ["order_id", "new_address", "summary"],
      },
    },
    cancellations: {
      type: "array",
      items: {
        type: "object",
        additionalProperties: false,
        properties: {
          order_id: { type: "string" },
          summary: { type: "string" },
        },
        required: ["order_id", "summary"],
      },
    },
    policies: {
      type: "array",
      items: {
        type: "object",
        additionalProperties: false,
        properties: {
          topic: { type: "string" },
          summary: { type: "string" },
        },
        required: ["topic", "summary"],
      },
    },
    escalations: {
      type: "array",
      items: {
        type: "object",
        additionalProperties: false,
        properties: {
          reason: { type: "string" },
          summary: { type: "string" },
        },
        required: ["reason", "summary"],
      },
    },
  },
  required: ["orders", "refunds", "address_changes", "cancellations", "policies", "escalations"],
};

function formatTranscript(messages: Message[]): string {
  return messages
    .filter((m) => m.role === "user" || m.role === "assistant")
    .map((m) => `${m.role === "user" ? "Customer" : "Aria"}: ${m.content}`)
    .join("\n\n");
}

export async function extractKnowledgeGraph(
  messages: Message[],
  signal?: AbortSignal,
): Promise<KnowledgeGraph> {
  const key = getOpenAIKey();
  if (!key) throw new Error("OpenAI key not set");
  if (messages.length === 0) return EMPTY_GRAPH;

  const transcript = formatTranscript(messages);

  const resp = await fetch(ENDPOINT, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${key}`,
    },
    signal,
    body: JSON.stringify({
      model: MODEL,
      temperature: 0,
      messages: [
        { role: "system", content: SYSTEM_PROMPT },
        {
          role: "user",
          content: `Conversation so far:\n\n${transcript}\n\nReturn the knowledge graph.`,
        },
      ],
      response_format: {
        type: "json_schema",
        json_schema: { name: "knowledge_graph", strict: true, schema: SCHEMA },
      },
    }),
  });

  if (!resp.ok) {
    const text = await resp.text().catch(() => "");
    throw new Error(`OpenAI ${resp.status}: ${text.slice(0, 200) || resp.statusText}`);
  }

  const json = await resp.json();
  const raw = json?.choices?.[0]?.message?.content;
  if (typeof raw !== "string") {
    throw new Error("Unexpected OpenAI response shape");
  }
  let parsed: KnowledgeGraph;
  try {
    parsed = JSON.parse(raw) as KnowledgeGraph;
  } catch {
    throw new Error("OpenAI returned non-JSON content");
  }
  // Belt-and-braces: ensure all arrays exist even if model omits them.
  return {
    orders: parsed.orders ?? [],
    refunds: parsed.refunds ?? [],
    address_changes: parsed.address_changes ?? [],
    cancellations: parsed.cancellations ?? [],
    policies: parsed.policies ?? [],
    escalations: parsed.escalations ?? [],
  };
}
