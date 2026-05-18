import { Loader2, MessageSquare, Power } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import type { AgentService, AgentTool } from "@/lib/api";
import type { AgentState } from "@/lib/types";
import { ToolsDrawer } from "./ToolsDrawer";
import { TurnCard } from "./TurnCard";

interface Props {
  service: AgentService;
  state: AgentState;
  tools: AgentTool[];
  toolsLoading: boolean;
  toolsError: string | null;
  onToggleEnabled: () => void;
}

export function AgentPanel({
  service,
  state,
  tools,
  toolsLoading,
  toolsError,
  onToggleEnabled,
}: Props) {
  const lastTurn = state.turns[state.turns.length - 1];
  const status = lastTurn?.status ?? "idle";
  const isRunning = status === "running";
  const isError = status === "error";
  const isDone = status === "done";

  // v1 = amber accent, v2 = emerald. Used for the top stripe and the
  // status dot when the panel is idle / running so the columns are visually
  // distinct at a glance — even before the audience reads the labels.
  const accentClass = service.variant === "v1" ? "bg-v1" : "bg-v2";
  const dotColor = isError ? "bg-destructive" : accentClass;

  const statusVariant: "secondary" | "destructive" | "success" = isError
    ? "destructive"
    : isDone
      ? "success"
      : "secondary";

  return (
    <section
      className={cn(
        "relative flex h-full min-h-0 flex-col overflow-hidden rounded-xl border bg-card shadow-sm transition-opacity",
        !state.enabled && "opacity-50",
      )}
    >
      {/* v1/v2 accent stripe */}
      <div className={cn("h-[3px] w-full shrink-0", accentClass)} aria-hidden />

      {/* Header */}
      <div className="flex shrink-0 items-center gap-3 px-4 py-3">
        <span
          className={cn(
            "h-2.5 w-2.5 shrink-0 rounded-full text-current transition-shadow",
            dotColor,
            isRunning && "running-glow",
          )}
          aria-label={`${service.variant} status: ${status}`}
        />
        <div className="flex min-w-0 flex-col">
          <div className="truncate text-sm font-semibold leading-tight tracking-tight">
            {service.label}
          </div>
          <div className="font-mono text-[11px] text-muted-foreground">
            {service.caption} · :{new URL(service.baseUrl).port}
          </div>
        </div>
        <div className="ml-auto flex items-center gap-2">
          {isRunning && (
            <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />
          )}
          {state.turns.length > 0 && (
            <Badge variant={statusVariant} className="capitalize">
              {status}
            </Badge>
          )}
          <label
            className={cn(
              "inline-flex cursor-pointer select-none items-center gap-1 rounded-md border px-2 py-1 text-xs transition-colors",
              state.enabled
                ? "border-transparent bg-secondary text-secondary-foreground hover:bg-secondary/80"
                : "border-input bg-background text-muted-foreground hover:bg-accent",
            )}
            title={state.enabled ? "Click to disable this agent" : "Click to enable"}
          >
            <input
              type="checkbox"
              checked={state.enabled}
              onChange={onToggleEnabled}
              className="sr-only"
            />
            <Power className="h-3 w-3" />
            <span className="font-medium">{state.enabled ? "on" : "off"}</span>
          </label>
        </div>
      </div>
      <Separator />

      {/* Tools catalog drawer — collapsed by default */}
      <ToolsDrawer
        tools={tools}
        loading={toolsLoading}
        error={toolsError ?? undefined}
      />

      {/* Body — scrolling thread of turns */}
      <div className="scroll-thin flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto p-4">
        {state.turns.length === 0 ? (
          <div className="flex flex-1 flex-col items-center justify-center gap-2 text-center text-muted-foreground">
            <MessageSquare className="h-6 w-6 opacity-60" />
            {state.enabled ? (
              <div className="space-y-1">
                <div className="text-sm">Type a prompt below</div>
                <div className="text-xs">Both agents see the same input.</div>
              </div>
            ) : (
              <div className="space-y-1">
                <div className="text-sm">Disabled</div>
                <div className="text-xs">Won't receive prompts.</div>
              </div>
            )}
          </div>
        ) : (
          state.turns.map((t, i) => (
            <div key={t.id} className="flex flex-col gap-3">
              <TurnCard turn={t} isLatest={i === state.turns.length - 1} />
              {t.session_ended_after && (
                <div className="flex items-center gap-2 px-1 text-[10px] uppercase tracking-widest text-muted-foreground">
                  <div className="h-px flex-1 bg-border" />
                  <span>new session · time has passed</span>
                  <div className="h-px flex-1 bg-border" />
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </section>
  );
}
