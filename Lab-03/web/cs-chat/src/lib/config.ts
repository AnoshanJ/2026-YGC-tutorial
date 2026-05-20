// Agent connection config.
//
// Sourced exclusively from window.AGENT_CONFIG, which is populated by
// /config.js (written by seed-2.sh). Not editable at runtime — to point
// the UI at a different agent, edit public/config.js and restart the dev
// server (or rebuild).

declare global {
  interface Window {
    AGENT_CONFIG?: { url: string; apiKey: string } | null;
  }
}

export type AgentConfig = { url: string; apiKey: string };

let cached: AgentConfig | null = null;
let cacheReady = false;

function rebuildCache() {
  const c = typeof window !== "undefined" ? window.AGENT_CONFIG : null;
  cached = c && c.url && c.apiKey ? { url: c.url, apiKey: c.apiKey } : null;
  cacheReady = true;
}

export function getAgentConfig(): AgentConfig | null {
  if (!cacheReady) rebuildCache();
  return cached;
}

export {};
