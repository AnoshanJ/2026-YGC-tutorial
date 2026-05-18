// Event shapes match what cs_agent_v1/main.py and cs_agent_v2/main.py emit
// as SSE frames. Keep these in sync with the Python `_run_agent_stream`
// generators on both services.

export type AgentVariant = "v1" | "v2";

export interface SystemPromptEvent {
  type: "system_prompt";
  content: string;
}

export interface UserMessageEvent {
  type: "user_message";
  content: string;
}

export interface ToolCallEvent {
  type: "tool_call";
  tool_use_id: string;
  name: string;
  args: unknown;
  args_summary: string;
}

export interface ToolResultEvent {
  type: "tool_result";
  tool_use_id: string;
  result: unknown;
  result_summary: string;
  is_error: boolean;
}

export interface TextDeltaEvent {
  type: "text_delta";
  delta: string;
}

export interface DoneEvent {
  type: "done";
  final_reply: string;
}

export interface ErrorEvent {
  type: "error";
  message: string;
}

export type AgentEvent =
  | SystemPromptEvent
  | UserMessageEvent
  | ToolCallEvent
  | ToolResultEvent
  | TextDeltaEvent
  | DoneEvent
  | ErrorEvent;

// One row in the trace UI. We pair each tool_call with its matching
// tool_result (if it has arrived) so they collapse to one expandable row.
export interface TraceRow {
  tool_use_id: string;
  name: string;
  args: unknown;
  args_summary: string;
  result?: unknown;
  result_summary?: string;
  is_error?: boolean;
}

// One full turn of conversation, from the user's prompt through the
// agent's final reply. We keep an array of these per agent so the chat
// view shows the whole session until the user hits reset.
export interface Turn {
  id: string;                // unique key for React rendering
  user_prompt: string;       // what the user typed
  framed_message: string;    // what the server reported handing to the LLM
  system_prompt: string;     // the rendered system prompt for this turn
  trace: TraceRow[];
  streaming_reply: string;
  final_reply: string;
  status: "running" | "done" | "error";
  error: string | null;
  // When the user clicks "Next session" after this turn, this flag is set
  // and the panel renders a "─── new session ───" divider beneath it.
  session_ended_after?: boolean;
}

export function newTurn(user_prompt: string): Turn {
  return {
    id:
      typeof crypto !== "undefined" && "randomUUID" in crypto
        ? crypto.randomUUID()
        : `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
    user_prompt,
    framed_message: "",
    system_prompt: "",
    trace: [],
    streaming_reply: "",
    final_reply: "",
    status: "running",
    error: null,
  };
}

// One column's accumulated state across the whole session.
export interface AgentState {
  enabled: boolean;          // user toggle — when false, /api/run is skipped
  turns: Turn[];             // appended on each send; cleared on reset
}

export function emptyAgentState(): AgentState {
  return { enabled: true, turns: [] };
}
