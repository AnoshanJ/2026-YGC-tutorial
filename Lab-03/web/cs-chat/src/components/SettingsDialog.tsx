import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { CheckCircle2, Eye, EyeOff, Loader2, Network, Plug, RotateCcw, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  clearAgentConfigOverride,
  getAgentConfig,
  getConfigSource,
  getSeedConfig,
  setAgentConfig,
  type ConfigSource,
} from "@/lib/config";
import { clearOpenAIKey, getOpenAIKey, setOpenAIKey } from "@/lib/extract";

type TestState =
  | { kind: "idle" }
  | { kind: "running" }
  | { kind: "ok" }
  | { kind: "fail"; message: string };

export function SettingsDialog({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const initial = useMemo(() => getAgentConfig(), [open]);
  const source: ConfigSource = useMemo(() => getConfigSource(), [open]);

  const [url, setUrl] = useState(initial?.url ?? "");
  const [apiKey, setApiKey] = useState(initial?.apiKey ?? "");
  const [openaiKey, setOpenaiKeyInput] = useState(() => getOpenAIKey() ?? "");
  const [initialOpenai, setInitialOpenai] = useState(() => getOpenAIKey() ?? "");
  const [showKey, setShowKey] = useState(false);
  const [showOpenai, setShowOpenai] = useState(false);
  const [test, setTest] = useState<TestState>({ kind: "idle" });

  // Re-sync inputs whenever the dialog opens.
  useEffect(() => {
    if (!open) return;
    const cfg = getAgentConfig();
    const oai = getOpenAIKey() ?? "";
    setUrl(cfg?.url ?? "");
    setApiKey(cfg?.apiKey ?? "");
    setOpenaiKeyInput(oai);
    setInitialOpenai(oai);
    setTest({ kind: "idle" });
  }, [open]);

  // Esc to close.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  const canSave = url.trim().length > 0 && apiKey.trim().length > 0;
  const isDirty =
    (initial?.url ?? "") !== url.trim() ||
    (initial?.apiKey ?? "") !== apiKey.trim() ||
    initialOpenai !== openaiKey.trim();

  const onSave = () => {
    if (!canSave) return;
    setAgentConfig({ url: url.trim(), apiKey: apiKey.trim() });
    const trimmed = openaiKey.trim();
    if (trimmed) setOpenAIKey(trimmed);
    else clearOpenAIKey();
    onClose();
  };

  const onResetToSeed = () => {
    const seed = getSeedConfig();
    clearAgentConfigOverride();
    setUrl(seed?.url ?? "");
    setApiKey(seed?.apiKey ?? "");
    setTest({ kind: "idle" });
  };

  const onTest = async () => {
    if (!canSave) return;
    setTest({ kind: "running" });
    try {
      const base = url.trim().replace(/\/+$/, "");
      const target = base.endsWith("/chat") ? base : `${base}/chat`;
      const resp = await fetch(target, {
        method: "POST",
        headers: { "Content-Type": "application/json", "x-api-key": apiKey.trim() },
        body: JSON.stringify({
          message: "ping",
          session_id: `ui-test-${Date.now()}`,
          context: {},
        }),
      });
      if (resp.ok) {
        setTest({ kind: "ok" });
      } else {
        setTest({ kind: "fail", message: `HTTP ${resp.status} ${resp.statusText}` });
      }
    } catch (e) {
      setTest({
        kind: "fail",
        message: e instanceof Error ? e.message : String(e),
      });
    }
  };

  return createPortal(
    <div
      className="fixed inset-0 z-[70] flex items-center justify-center bg-foreground/40 backdrop-blur-sm p-4 animate-fade-in"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="w-full max-w-lg rounded-2xl border bg-card shadow-2xl">
        <div className="flex items-center justify-between border-b px-5 py-3">
          <div className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-md bg-primary/10 text-primary">
              <Plug className="h-3.5 w-3.5" />
            </div>
            <div className="leading-tight">
              <div className="text-sm font-semibold">Agent connection</div>
              <div className="text-[11px] text-muted-foreground">
                Point Aria at a deployed agent endpoint.
              </div>
            </div>
          </div>
          <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close settings">
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="px-5 py-4 space-y-4">
          <SourceBadge source={source} />

          <div className="space-y-2">
            <Label htmlFor="agent-url">Agent URL</Label>
            <Input
              id="agent-url"
              type="url"
              spellCheck={false}
              autoComplete="off"
              placeholder="https://your-gateway/agents/cs-agent/default"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
            />
            <p className="text-[11px] text-muted-foreground">
              The base endpoint exposed by Agent Manager. The <code>/chat</code> suffix is added
              automatically if you don't include it.
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="agent-key">API key</Label>
            <div className="relative">
              <Input
                id="agent-key"
                type={showKey ? "text" : "password"}
                spellCheck={false}
                autoComplete="off"
                placeholder="sk_..."
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                className="pr-10 font-mono text-xs"
              />
              <button
                type="button"
                onClick={() => setShowKey((v) => !v)}
                className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-muted-foreground hover:text-foreground"
                aria-label={showKey ? "Hide API key" : "Show API key"}
              >
                {showKey ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
              </button>
            </div>
            <p className="text-[11px] text-muted-foreground">
              Sent as the <code>x-api-key</code> header on every chat request. Stored only in this
              browser.
            </p>
          </div>

          <TestPanel state={test} />

          <div className="mt-2 rounded-xl border bg-muted/30 p-4 space-y-3">
            <div className="flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-md bg-brand/10 text-brand">
                <Network className="h-3.5 w-3.5" />
              </div>
              <div className="leading-tight">
                <div className="text-sm font-semibold">Live knowledge graph</div>
                <div className="text-[11px] text-muted-foreground">
                  Optional. Aria uses your OpenAI key to summarize each turn into a sidebar graph.
                </div>
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="openai-key" className="text-xs">OpenAI API key</Label>
              <div className="relative">
                <Input
                  id="openai-key"
                  type={showOpenai ? "text" : "password"}
                  spellCheck={false}
                  autoComplete="off"
                  placeholder="sk-..."
                  value={openaiKey}
                  onChange={(e) => setOpenaiKeyInput(e.target.value)}
                  className="pr-10 font-mono text-xs"
                />
                <button
                  type="button"
                  onClick={() => setShowOpenai((v) => !v)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-muted-foreground hover:text-foreground"
                  aria-label={showOpenai ? "Hide key" : "Show key"}
                >
                  {showOpenai ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                </button>
              </div>
              <p className="text-[11px] text-muted-foreground">
                Stored only in this browser. Sent directly from this page to{" "}
                <code>api.openai.com</code>. Leave empty to disable the graph.
              </p>
            </div>
          </div>

          {import.meta.env.DEV && source === "seed" && (
            <div className="rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-[11px] leading-relaxed text-amber-900 dark:text-amber-300">
              In dev, calls go through the Vite proxy when the config came from <code>config.js</code>.
              If you change the URL here, requests bypass the proxy and need CORS on the agent.
            </div>
          )}
        </div>

        <div className="flex items-center justify-between gap-2 border-t bg-muted/30 px-5 py-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={onResetToSeed}
            disabled={!getSeedConfig() || source === "seed"}
            title="Drop the local override and use the URL from config.js"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            Reset to seed
          </Button>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={onTest}
              disabled={!canSave || test.kind === "running"}
            >
              {test.kind === "running" ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Plug className="h-3.5 w-3.5" />
              )}
              Test
            </Button>
            <Button size="sm" onClick={onSave} disabled={!canSave || !isDirty}>
              Save
            </Button>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}

function SourceBadge({ source }: { source: ConfigSource }) {
  if (source === "override") {
    return (
      <div className="rounded-md border border-primary/30 bg-primary/5 px-3 py-2 text-[11px] text-foreground">
        Using a <strong>local override</strong> saved in this browser. Clear it to fall back to{" "}
        <code>config.js</code>.
      </div>
    );
  }
  if (source === "seed") {
    return (
      <div className="rounded-md border bg-muted/40 px-3 py-2 text-[11px] text-muted-foreground">
        Loaded from <code>config.js</code>. Edits below will be saved as a per-browser override.
      </div>
    );
  }
  return (
    <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-[11px] text-destructive">
      No agent connection configured. Paste a URL and API key to get started.
    </div>
  );
}

function TestPanel({ state }: { state: TestState }) {
  if (state.kind === "idle") return null;
  if (state.kind === "running") {
    return (
      <div className="flex items-center gap-2 rounded-md bg-muted/40 px-3 py-2 text-[11px] text-muted-foreground">
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
        Sending a test ping…
      </div>
    );
  }
  if (state.kind === "ok") {
    return (
      <div className="flex items-center gap-2 rounded-md border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-[11px] text-emerald-700 dark:text-emerald-300">
        <CheckCircle2 className="h-3.5 w-3.5" />
        Agent responded. Looks good.
      </div>
    );
  }
  return (
    <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-[11px] text-destructive">
      <div className="font-semibold">Test failed</div>
      <div className="font-mono break-all">{state.message}</div>
    </div>
  );
}
