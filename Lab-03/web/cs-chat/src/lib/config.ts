// Bridge to /config.js (loaded as a script tag in index.html).
// config.js sets window.AGENT_CONFIG = { url, apiKey } and is generated as
// part of the local setup — never bundled, never committed.

declare global {
  interface Window {
    AGENT_CONFIG?: { url: string; apiKey: string } | null;
  }
}

export type AgentConfig = { url: string; apiKey: string };

export function getAgentConfig(): AgentConfig | null {
  const c = window.AGENT_CONFIG;
  if (!c || !c.url || !c.apiKey) return null;
  return c;
}

export {};
