import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";
import { useNavigate } from "react-router-dom";
import { AlertTriangle, Bot } from "lucide-react";
import { TopBar } from "@/components/TopBar";
import { KnowledgeGraph, type GraphStatus } from "@/components/KnowledgeGraph";
import { MessageBubble, TypingBubble, type Message } from "@/components/MessageBubble";
import { Composer } from "@/components/Composer";
import { SuggestionChips } from "@/components/SuggestionChips";
import { SettingsDialog } from "@/components/SettingsDialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  clearCurrentUser,
  getCurrentUser,
  getOrCreateSession,
  rotateSession,
} from "@/lib/auth";
import { getAgentConfig } from "@/lib/config";
import { sendChat } from "@/lib/api";
import {
  EMPTY_GRAPH,
  extractKnowledgeGraph,
  getOpenAIKey,
  subscribeOpenAIKey,
  type KnowledgeGraph as KG,
} from "@/lib/extract";

function useOpenAIKey() {
  return useSyncExternalStore(subscribeOpenAIKey, getOpenAIKey, getOpenAIKey);
}

export default function Chat() {
  const navigate = useNavigate();
  const [user] = useState(() => getCurrentUser());
  // Agent config is baked in from public/config.js at page load — never
  // changes at runtime, so a single read is enough.
  const [config] = useState(() => getAgentConfig());
  const openaiKey = useOpenAIKey();
  const [sessionId, setSessionId] = useState<string>(() =>
    user ? getOrCreateSession(user.id) : "",
  );
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [thinking, setThinking] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [graph, setGraph] = useState<KG>(EMPTY_GRAPH);
  const [graphStatus, setGraphStatus] = useState<GraphStatus>(
    openaiKey ? { kind: "idle" } : { kind: "disabled" },
  );
  const scrollRef = useRef<HTMLDivElement>(null);
  const extractAbort = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!user) navigate("/login", { replace: true });
  }, [user, navigate]);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, thinking]);

  // Toggle graph "disabled" vs "idle" when the user adds/removes the OpenAI key.
  useEffect(() => {
    setGraphStatus((s) => {
      if (!openaiKey) return { kind: "disabled" };
      if (s.kind === "disabled") return { kind: "idle" };
      return s;
    });
  }, [openaiKey]);

  const runExtraction = useCallback(async (history: Message[]) => {
    if (!getOpenAIKey()) return;
    extractAbort.current?.abort();
    const ctrl = new AbortController();
    extractAbort.current = ctrl;
    setGraphStatus({ kind: "extracting" });
    try {
      const g = await extractKnowledgeGraph(history, ctrl.signal);
      if (ctrl.signal.aborted) return;
      setGraph(g);
      setGraphStatus({ kind: "ok", ts: Date.now() });
    } catch (e) {
      if (ctrl.signal.aborted) return;
      setGraphStatus({
        kind: "error",
        message: e instanceof Error ? e.message : String(e),
      });
    }
  }, []);

  if (!user) return null;

  const onSend = async () => {
    const text = input.trim();
    if (!text) return;
    const userMsg: Message = {
      id: `u-${Date.now()}`,
      role: "user",
      content: text,
      ts: Date.now(),
    };
    const nextAfterUser = [...messages, userMsg];
    setMessages(nextAfterUser);
    setInput("");

    if (!config) {
      setMessages((m) => [
        ...m,
        {
          id: `e-${Date.now()}`,
          role: "error",
          content:
            "Aria isn't connected to an agent. Generate public/config.js (run seed-2.sh) and reload the page.",
          ts: Date.now(),
        },
      ]);
      return;
    }

    setThinking(true);
    try {
      const resp = await sendChat(config, user.id, {
        message: text,
        session_id: sessionId,
      });
      const assistantMsg: Message = {
        id: `a-${Date.now()}`,
        role: "assistant",
        content: resp.response || "(no response)",
        ts: Date.now(),
      };
      const nextAfterReply = [...nextAfterUser, assistantMsg];
      setMessages(nextAfterReply);
      // Kick off background extraction with the full updated history.
      void runExtraction(nextAfterReply);
    } catch (e) {
      setMessages((m) => [
        ...m,
        {
          id: `e-${Date.now()}`,
          role: "error",
          content: e instanceof Error ? e.message : String(e),
          ts: Date.now(),
        },
      ]);
    } finally {
      setThinking(false);
    }
  };

  const onNewSession = () => {
    extractAbort.current?.abort();
    setSessionId(rotateSession(user.id));
    setMessages([]);
    setGraph(EMPTY_GRAPH);
    setGraphStatus(getOpenAIKey() ? { kind: "idle" } : { kind: "disabled" });
  };

  const onLogout = () => {
    clearCurrentUser();
    navigate("/", { replace: true });
  };

  return (
    <div className="flex h-screen flex-col bg-aurora">
      <TopBar
        user={user}
        onNewSession={onNewSession}
        onLogout={onLogout}
        onOpenSettings={() => setSettingsOpen(true)}
      />
      <div className="flex flex-1 overflow-hidden">
        <KnowledgeGraph
          graph={graph}
          status={graphStatus}
          onOpenSettings={() => setSettingsOpen(true)}
        />
        <main className="flex flex-1 flex-col bg-background/60">
          {!config && (
            <div className="flex items-start gap-3 border-b bg-amber-500/10 px-5 py-3 text-sm text-amber-900 dark:text-amber-300">
              <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
              <div className="flex-1">
                Aria isn't connected to an agent. <code className="font-mono text-xs">public/config.js</code> is
                missing &mdash; run <code className="font-mono text-xs">seed-2.sh</code> from the seed directory and reload this page.
              </div>
            </div>
          )}
          <ScrollArea className="flex-1">
            <div ref={scrollRef} className="mx-auto max-w-3xl px-5 py-6 space-y-4">
              {messages.length === 0 && <WelcomeCard name={user.name} />}
              {messages.map((m) => (
                <MessageBubble key={m.id} msg={m} userName={user.name} />
              ))}
              {thinking && <TypingBubble />}
            </div>
          </ScrollArea>
          <div className="mx-auto w-full max-w-3xl px-3 pb-4">
            {messages.length === 0 && <SuggestionChips onPick={(t) => setInput(t)} />}
            <Composer
              value={input}
              onChange={setInput}
              onSend={onSend}
              disabled={thinking}
            />
          </div>
        </main>
      </div>
      <SettingsDialog open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  );
}

function WelcomeCard({ name }: { name: string }) {
  const firstName = name.split(" ")[0];
  return (
    <div className="relative mx-auto max-w-xl px-4 pt-10 pb-2 text-center animate-fade-in">
      <div className="relative mx-auto mb-6 h-16 w-16">
        <div className="brand-orb absolute inset-0 rounded-full" aria-hidden />
        <div className="relative flex h-16 w-16 items-center justify-center rounded-full border bg-card shadow-lg">
          <Bot className="h-7 w-7 text-primary" />
        </div>
        <span className="absolute -right-0.5 -bottom-0.5 h-3 w-3 rounded-full bg-emerald-500 ring-2 ring-card" aria-hidden />
      </div>

      <h2 className="text-3xl font-bold tracking-tight leading-tight">
        Hi {firstName}, I'm{" "}
        <span className="bg-gradient-to-r from-indigo-600 via-fuchsia-600 to-teal-500 dark:from-indigo-400 dark:via-fuchsia-400 dark:to-teal-300 bg-clip-text text-transparent">
          Aria
        </span>
        .
      </h2>
      <p className="mt-2 text-base text-muted-foreground">
        How can I help today?
      </p>

      <p className="mx-auto mt-5 max-w-md text-sm text-muted-foreground leading-relaxed">
        I already have your Northwind account in front of me &mdash; your orders, addresses, and what
        you can do with each. Just tell me what you need.
      </p>

      <div className="mt-6 inline-flex items-center gap-1.5 rounded-full border bg-card/70 px-3 py-1 text-[11px] text-muted-foreground backdrop-blur">
        <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
        Online &middot; typically replies in seconds
      </div>
    </div>
  );
}
