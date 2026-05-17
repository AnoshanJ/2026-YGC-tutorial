// Agent connection config.
//
// Sources, in priority order:
//   1. localStorage override (set via the in-app Settings dialog)
//   2. window.AGENT_CONFIG, populated by /config.js
//
// Anything saved in the dialog wins, so the operator can paste a new agent
// URL/API key at runtime without touching config.js or restarting the build.

declare global {
  interface Window {
    AGENT_CONFIG?: { url: string; apiKey: string } | null;
  }
}

export type AgentConfig = { url: string; apiKey: string };
export type ConfigSource = "override" | "seed" | "none";

const STORAGE_KEY = "nw-agent-config";

type Listener = () => void;
const listeners = new Set<Listener>();

// useSyncExternalStore requires getSnapshot to return a stable reference when
// nothing has changed (it uses Object.is between renders). We cache the
// resolved config + source and only rebuild when invalidate() is called.
let cachedConfig: AgentConfig | null = null;
let cachedSource: ConfigSource = "none";
let cacheReady = false;

function readOverrideRaw(): AgentConfig | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<AgentConfig>;
    if (!parsed?.url || !parsed?.apiKey) return null;
    return { url: parsed.url, apiKey: parsed.apiKey };
  } catch {
    return null;
  }
}

function readSeedRaw(): AgentConfig | null {
  const c = typeof window !== "undefined" ? window.AGENT_CONFIG : null;
  if (!c || !c.url || !c.apiKey) return null;
  return { url: c.url, apiKey: c.apiKey };
}

function rebuildCache() {
  const override = readOverrideRaw();
  if (override) {
    cachedConfig = override;
    cachedSource = "override";
  } else {
    const seed = readSeedRaw();
    cachedConfig = seed;
    cachedSource = seed ? "seed" : "none";
  }
  cacheReady = true;
}

function ensureCache() {
  if (!cacheReady) rebuildCache();
}

function invalidate() {
  rebuildCache();
  listeners.forEach((fn) => fn());
}

export function getAgentConfig(): AgentConfig | null {
  ensureCache();
  return cachedConfig;
}

export function getConfigSource(): ConfigSource {
  ensureCache();
  return cachedSource;
}

export function getSeedConfig(): AgentConfig | null {
  return readSeedRaw();
}

export function setAgentConfig(cfg: AgentConfig) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(cfg));
  invalidate();
}

export function clearAgentConfigOverride() {
  localStorage.removeItem(STORAGE_KEY);
  invalidate();
}

export function subscribeAgentConfig(fn: Listener): () => void {
  listeners.add(fn);
  return () => {
    listeners.delete(fn);
  };
}

export {};
