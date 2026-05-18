import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { BookOpen, Hourglass, RotateCcw, Sparkles } from "lucide-react";
import {
  AGENTS,
  DEFAULT_MODEL,
  SUPPORTED_MODELS,
  endSession,
  fetchTools,
  runAgent,
  resetAgent,
  type AgentService,
  type AgentTool,
  type SupportedModel,
} from "@/lib/api";
import {
  emptyAgentState,
  newTurn,
  type AgentEvent,
  type AgentState,
  type AgentVariant,
  type Turn,
} from "@/lib/types";
import { AgentPanel } from "@/components/AgentPanel";
import { Composer } from "@/components/Composer";
import { ScenariosPanel } from "@/components/ScenariosPanel";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Button } from "@/components/ui/button";
import type { DemoScenario, ScenarioPrompt } from "@/lib/scenarios";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const CUSTOMERS = [
  { id: "cust_001", label: "Alice · cust_001" },
  { id: "cust_002", label: "Bob · cust_002" },
  { id: "cust_003", label: "Carol · cust_003" },
];

export default function App() {
  const [customerId, setCustomerId] = useState<string>("cust_001");
  const [selectedModel, setSelectedModel] = useState<SupportedModel>(DEFAULT_MODEL);
  // Composer text lives in App so the Scenarios panel can pre-fill it on click.
  const [composerText, setComposerText] = useState("");
  const [scenariosOpen, setScenariosOpen] = useState(false);
  const [v1, setV1] = useState<AgentState>(emptyAgentState);
  const [v2, setV2] = useState<AgentState>(emptyAgentState);
  // Tool catalog per agent — fetched once on mount. Tools don't change
  // between requests, so we don't refetch on send/reset.
  const [v1Tools, setV1Tools] = useState<AgentTool[]>([]);
  const [v2Tools, setV2Tools] = useState<AgentTool[]>([]);
  const [v1ToolsLoading, setV1ToolsLoading] = useState(true);
  const [v2ToolsLoading, setV2ToolsLoading] = useState(true);
  const [v1ToolsError, setV1ToolsError] = useState<string | null>(null);
  const [v2ToolsError, setV2ToolsError] = useState<string | null>(null);
  const [resetMsg, setResetMsg] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Fetch tool catalogs once. v2 spawns its MCP subprocesses on first
  // /api/tools call — that one-time spawn cost lands at page load
  // instead of mid-demo.
  useEffect(() => {
    let cancelled = false;
    const load = (
      svc: AgentService,
      setTools: (t: AgentTool[]) => void,
      setLoading: (b: boolean) => void,
      setError: (e: string | null) => void,
    ) => {
      fetchTools(svc)
        .then((tools) => {
          if (cancelled) return;
          setTools(tools);
          setError(null);
        })
        .catch((err) => {
          if (cancelled) return;
          setError(err instanceof Error ? err.message : String(err));
        })
        .finally(() => {
          if (cancelled) return;
          setLoading(false);
        });
    };
    load(AGENTS.v1, setV1Tools, setV1ToolsLoading, setV1ToolsError);
    load(AGENTS.v2, setV2Tools, setV2ToolsLoading, setV2ToolsError);
    return () => {
      cancelled = true;
    };
  }, []);

  const setters = useMemo(
    (): Record<AgentVariant, React.Dispatch<React.SetStateAction<AgentState>>> => ({
      v1: setV1,
      v2: setV2,
    }),
    [],
  );

  const lastTurnRunning = (s: AgentState) => {
    const last = s.turns[s.turns.length - 1];
    return last?.status === "running";
  };
  const anyRunning = lastTurnRunning(v1) || lastTurnRunning(v2);

  const updateTurn = useCallback(
    (variant: AgentVariant, turnId: string, updater: (t: Turn) => Turn) => {
      setters[variant]((s) => ({
        ...s,
        turns: s.turns.map((t) => (t.id === turnId ? updater(t) : t)),
      }));
    },
    [setters],
  );

  const handleEvent = useCallback(
    (variant: AgentVariant, turnId: string) => (ev: AgentEvent) => {
      switch (ev.type) {
        case "system_prompt":
          updateTurn(variant, turnId, (t) => ({ ...t, system_prompt: ev.content }));
          break;
        case "user_message":
          updateTurn(variant, turnId, (t) => ({ ...t, framed_message: ev.content }));
          break;
        case "tool_call":
          updateTurn(variant, turnId, (t) => ({
            ...t,
            trace: [
              ...t.trace,
              {
                tool_use_id: ev.tool_use_id,
                name: ev.name,
                args: ev.args,
                args_summary: ev.args_summary,
              },
            ],
          }));
          break;
        case "tool_result":
          updateTurn(variant, turnId, (t) => ({
            ...t,
            trace: t.trace.map((r) =>
              r.tool_use_id === ev.tool_use_id
                ? {
                    ...r,
                    result: ev.result,
                    result_summary: ev.result_summary,
                    is_error: ev.is_error,
                  }
                : r,
            ),
          }));
          break;
        case "text_delta":
          updateTurn(variant, turnId, (t) => ({
            ...t,
            streaming_reply: t.streaming_reply + ev.delta,
          }));
          break;
        case "done":
          updateTurn(variant, turnId, (t) => ({
            ...t,
            status: "done",
            final_reply: ev.final_reply || t.streaming_reply,
          }));
          break;
        case "error":
          updateTurn(variant, turnId, (t) => ({
            ...t,
            status: "error",
            error: ev.message,
          }));
          break;
      }
    },
    [updateTurn],
  );

  async function send(prompt: string) {
    if (anyRunning) return;

    // Append a new turn to each ENABLED agent. Disabled ones simply skip.
    const v1Turn = v1.enabled ? newTurn(prompt) : null;
    const v2Turn = v2.enabled ? newTurn(prompt) : null;

    if (!v1Turn && !v2Turn) return; // both off → nothing to do

    if (v1Turn) setV1((s) => ({ ...s, turns: [...s.turns, v1Turn] }));
    if (v2Turn) setV2((s) => ({ ...s, turns: [...s.turns, v2Turn] }));
    setResetMsg(null);

    const controller = new AbortController();
    abortRef.current = controller;

    const launch = async (svc: AgentService, variant: AgentVariant, turnId: string) => {
      try {
        await runAgent(svc, {
          prompt,
          customer_id: customerId,
          model: selectedModel,
          signal: controller.signal,
          onEvent: handleEvent(variant, turnId),
        });
        // Servers may close the stream without an explicit `done`. Mark
        // as done if we never received one.
        updateTurn(variant, turnId, (t) =>
          t.status === "running" ? { ...t, status: "done" } : t,
        );
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        updateTurn(variant, turnId, (t) => ({ ...t, status: "error", error: message }));
      }
    };

    // Kick off v2 first — v2 has the MCP-subprocess spawn cost and the
    // AgentSkills injection on first request, so it's slower to issue the
    // first SSE chunk. v1 fires immediately after; both still stream
    // concurrently, but the head start helps the two columns finish
    // visually in sync on the projector.
    const launches: Promise<void>[] = [];
    if (v2Turn) launches.push(launch(AGENTS.v2, "v2", v2Turn.id));
    if (v1Turn) launches.push(launch(AGENTS.v1, "v1", v1Turn.id));
    await Promise.allSettled(launches);
  }

  async function reset() {
    abortRef.current?.abort();
    // Clear chat history on both columns but keep their enabled toggles.
    setV1((s) => ({ ...s, turns: [] }));
    setV2((s) => ({ ...s, turns: [] }));
    setResetMsg("resetting…");
    try {
      await Promise.all([resetAgent(AGENTS.v1), resetAgent(AGENTS.v2)]);
      setResetMsg("both agents reset");
      setTimeout(() => setResetMsg(null), 2500);
    } catch (err) {
      setResetMsg(`reset failed: ${err instanceof Error ? err.message : String(err)}`);
    }
  }

  function toggleEnabled(variant: AgentVariant) {
    setters[variant]((s) => ({ ...s, enabled: !s.enabled }));
  }

  /** Simulate "time has passed" for the episodic-memory demo. Both agents'
   *  cached Agent is dropped (server-side and client-side conversation
   *  memory wiped), but v2's episodic memory file on disk persists. A
   *  divider is appended in each panel's thread to mark the boundary. */
  async function nextSession() {
    if (anyRunning) return;
    // Mark a divider after the last turn in each enabled panel.
    setV1((s) => {
      if (s.turns.length === 0) return s;
      return {
        ...s,
        turns: s.turns.map((t, i) =>
          i === s.turns.length - 1 ? { ...t, session_ended_after: true } : t,
        ),
      };
    });
    setV2((s) => {
      if (s.turns.length === 0) return s;
      return {
        ...s,
        turns: s.turns.map((t, i) =>
          i === s.turns.length - 1 ? { ...t, session_ended_after: true } : t,
        ),
      };
    });
    setResetMsg("new session…");
    try {
      await Promise.all([
        endSession(AGENTS.v1, customerId),
        endSession(AGENTS.v2, customerId),
      ]);
      setResetMsg("session ended — episodic memory preserved");
      setTimeout(() => setResetMsg(null), 3000);
    } catch (err) {
      setResetMsg(`end_session failed: ${err instanceof Error ? err.message : String(err)}`);
    }
  }

  /** Called when the presenter clicks a scenario prompt in the panel.
   *  Pre-fills the composer; flips the session/model dropdowns to whatever
   *  the scenario specifies. Sending stays manual. */
  function applyScenario(scenario: DemoScenario, prompt: ScenarioPrompt) {
    setComposerText(prompt.text);
    if (scenario.customer_id) setCustomerId(scenario.customer_id);
    if (scenario.model) setSelectedModel(scenario.model);
  }

  return (
    <div className="flex h-full flex-col bg-aurora">
      {/* Top bar — single backdrop-blur for the whole page lives only here. */}
      <header className="sticky top-0 z-10 flex shrink-0 items-center gap-4 border-b bg-background/80 px-6 py-3 backdrop-blur-md">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-primary text-primary-foreground shadow-sm">
            <Sparkles className="h-3.5 w-3.5" />
          </div>
          <div className="flex flex-col leading-tight">
            <div className="text-sm font-semibold tracking-tight">
              Lab-01 — Agent comparison
            </div>
            <div className="text-[11px] text-muted-foreground">
              Same prompt → both agents → watch the boundary lessons land
            </div>
          </div>
        </div>

        <div className="ml-auto flex items-center gap-3">
          <Field label="session" htmlFor="customer">
            <Select
              value={customerId}
              onValueChange={setCustomerId}
              disabled={anyRunning}
            >
              <SelectTrigger id="customer" className="w-[180px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {CUSTOMERS.map((c) => (
                  <SelectItem key={c.id} value={c.id}>
                    {c.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>

          <Field label="model" htmlFor="model">
            <Select
              value={selectedModel}
              onValueChange={(v) => setSelectedModel(v as SupportedModel)}
              disabled={anyRunning}
            >
              <SelectTrigger id="model" className="w-[160px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {SUPPORTED_MODELS.map((m) => (
                  <SelectItem key={m} value={m}>
                    {m}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>

          <Button
            variant={scenariosOpen ? "secondary" : "outline"}
            size="sm"
            onClick={() => setScenariosOpen((o) => !o)}
            aria-pressed={scenariosOpen}
            aria-controls="scenarios-sidebar"
            title="Toggle demo scenarios sidebar"
          >
            <BookOpen className="mr-1 h-3.5 w-3.5" />
            scenarios
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={nextSession}
            disabled={anyRunning}
            title="Simulate 'time has passed' — drop conversation memory on both sides; v2's episodic memory file persists."
          >
            <Hourglass className="mr-1 h-3.5 w-3.5" />
            next session
          </Button>
          <Button variant="outline" size="sm" onClick={reset} disabled={anyRunning}>
            <RotateCcw className="mr-1 h-3.5 w-3.5" />
            reset
          </Button>
          <ThemeToggle />
          {resetMsg && (
            <span className="ml-1 text-xs text-muted-foreground animate-fade-in">
              {resetMsg}
            </span>
          )}
        </div>
      </header>

      {/* Body row: agent panels + composer on the left; scenarios sidebar
          docks full-height on the right when open so the composer shrinks
          to the panels' width instead of spanning under it. */}
      <div className="flex min-h-0 flex-1 gap-4 px-4 pt-4">
        <div className="flex min-h-0 flex-1 flex-col gap-4">
          <main className="grid min-h-0 flex-1 grid-cols-2 gap-4">
            <AgentPanel
              service={AGENTS.v1}
              state={v1}
              tools={v1Tools}
              toolsLoading={v1ToolsLoading}
              toolsError={v1ToolsError}
              onToggleEnabled={() => toggleEnabled("v1")}
            />
            <AgentPanel
              service={AGENTS.v2}
              state={v2}
              tools={v2Tools}
              toolsLoading={v2ToolsLoading}
              toolsError={v2ToolsError}
              onToggleEnabled={() => toggleEnabled("v2")}
            />
          </main>
          <footer className="shrink-0 pb-4">
            <Composer
              disabled={anyRunning}
              onSend={send}
              value={composerText}
              onChange={setComposerText}
            />
          </footer>
        </div>
        {scenariosOpen && (
          <aside
            id="scenarios-sidebar"
            className="flex w-[380px] shrink-0 min-h-0 flex-col pb-4"
          >
            <ScenariosPanel
              onApply={applyScenario}
              onClose={() => setScenariosOpen(false)}
              disabled={anyRunning}
            />
          </aside>
        )}
      </div>
    </div>
  );
}

interface FieldProps {
  label: string;
  htmlFor: string;
  children: React.ReactNode;
}

function Field({ label, htmlFor, children }: FieldProps) {
  return (
    <div className="flex items-center gap-1.5">
      <label
        htmlFor={htmlFor}
        className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground"
      >
        {label}
      </label>
      {children}
    </div>
  );
}
