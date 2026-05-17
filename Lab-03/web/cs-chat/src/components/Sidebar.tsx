import { Package, Receipt, Sparkles, Truck } from "lucide-react";

export function Sidebar({
  customerName,
  sessionId,
  onSuggest,
}: {
  customerName: string;
  sessionId: string;
  onSuggest?: (text: string) => void;
}) {
  return (
    <aside className="hidden md:flex flex-col border-r bg-card/40 w-72 shrink-0">
      <div className="p-5 border-b">
        <div className="text-xs uppercase tracking-wider text-muted-foreground font-semibold">
          Current chat
        </div>
        <div className="mt-1.5 font-semibold text-sm">{customerName}</div>
        <div className="mt-0.5 text-[11px] text-muted-foreground font-mono break-all">
          {sessionId}
        </div>
      </div>

      <div className="p-5 text-xs uppercase tracking-wider text-muted-foreground font-semibold">
        Try asking
      </div>
      <div className="px-3 pb-5 space-y-1">
        <Suggestion
          icon={<Receipt className="h-3.5 w-3.5" />}
          label="I want a refund for a recent order."
          onClick={() => onSuggest?.("I want a refund for a recent order.")}
        />
        <Suggestion
          icon={<Truck className="h-3.5 w-3.5" />}
          label="Where is my latest order?"
          onClick={() => onSuggest?.("Where is my latest order?")}
        />
        <Suggestion
          icon={<Package className="h-3.5 w-3.5" />}
          label="What did I order recently?"
          onClick={() => onSuggest?.("What did I order recently?")}
        />
        <Suggestion
          icon={<Sparkles className="h-3.5 w-3.5" />}
          label="What's your refund policy?"
          onClick={() => onSuggest?.("What's your refund policy?")}
        />
      </div>

      <div className="mt-auto p-5 border-t text-[11px] text-muted-foreground leading-relaxed">
        <p className="font-semibold text-foreground mb-1">About this demo</p>
        <p>
          Your identity is passed to the agent via <code className="font-mono">context.customer_id</code> and
          surfaced on each trace's root span in the AM console.
        </p>
      </div>
    </aside>
  );
}

function Suggestion({
  icon,
  label,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex w-full items-start gap-2 rounded-md px-2.5 py-1.5 text-left text-xs text-muted-foreground hover:bg-accent hover:text-accent-foreground transition-colors"
    >
      <span className="mt-0.5 text-primary/80">{icon}</span>
      <span>{label}</span>
    </button>
  );
}
