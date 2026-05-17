import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AlertTriangle, Sparkles } from "lucide-react";
import { TopBar } from "@/components/TopBar";
import { Sidebar } from "@/components/Sidebar";
import { MessageBubble, TypingBubble, type Message } from "@/components/MessageBubble";
import { Composer } from "@/components/Composer";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  clearCurrentUser,
  getCurrentUser,
  getOrCreateSession,
  rotateSession,
} from "@/lib/auth";
import { getAgentConfig } from "@/lib/config";
import { sendChat } from "@/lib/api";

export default function Chat() {
  const navigate = useNavigate();
  const user = useMemo(() => getCurrentUser(), []);
  const config = useMemo(() => getAgentConfig(), []);
  const [sessionId, setSessionId] = useState<string>(() =>
    user ? getOrCreateSession(user.id) : "",
  );
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [thinking, setThinking] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!user) navigate("/login", { replace: true });
  }, [user, navigate]);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, thinking]);

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
    setMessages((m) => [...m, userMsg]);
    setInput("");

    if (!config) {
      setMessages((m) => [
        ...m,
        {
          id: `e-${Date.now()}`,
          role: "error",
          content:
            "Agent not reachable yet. Deploy the agent, add the config, and try again.",
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
      setMessages((m) => [
        ...m,
        {
          id: `a-${Date.now()}`,
          role: "assistant",
          content: resp.response || "(no response)",
          ts: Date.now(),
        },
      ]);
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
    setSessionId(rotateSession(user.id));
    setMessages([]);
  };

  const onLogout = () => {
    clearCurrentUser();
    navigate("/login", { replace: true });
  };

  return (
    <div className="flex h-screen flex-col bg-aurora">
      <TopBar user={user} onNewSession={onNewSession} onLogout={onLogout} />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar
          customerName={user.name}
          sessionId={sessionId}
          onSuggest={(t) => setInput(t)}
        />
        <main className="flex flex-1 flex-col bg-background/60">
          {!config && (
            <div className="flex items-start gap-2 border-b bg-amber-500/10 px-5 py-3 text-sm text-amber-900">
              <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
              <div>
                Agent not reachable. Deploy the agent, add the config, and refresh this page.
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
            <Composer
              value={input}
              onChange={setInput}
              onSend={onSend}
              disabled={thinking}
            />
          </div>
        </main>
      </div>
    </div>
  );
}

function WelcomeCard({ name }: { name: string }) {
  return (
    <div className="rounded-2xl border bg-card p-6 shadow-sm animate-fade-in">
      <div className="inline-flex items-center gap-2 rounded-full bg-primary/10 px-2.5 py-0.5 text-[11px] font-semibold text-primary">
        <Sparkles className="h-3 w-3" /> Hi {name.split(" ")[0]}
      </div>
      <h2 className="mt-3 text-lg font-semibold">How can we help today?</h2>
      <p className="mt-1 text-sm text-muted-foreground">
        Ask about an order, a refund, a shipment, or our policies. We already have your account in
        front of us &mdash; just tell us what's going on.
      </p>
    </div>
  );
}
