import { MapPin, Receipt, ScrollText, Truck } from "lucide-react";

type Suggestion = {
  icon: React.ReactNode;
  category: string;
  prompt: string;
  hint: string;
  accent: "primary" | "brand" | "emerald" | "violet";
};

const SUGGESTIONS: Suggestion[] = [
  {
    icon: <Truck className="h-4 w-4" />,
    category: "Track",
    prompt: "Where is my latest order?",
    hint: "Live status + ETA",
    accent: "primary",
  },
  {
    icon: <Receipt className="h-4 w-4" />,
    category: "Refund",
    prompt: "I'd like a refund on a recent order.",
    hint: "Instant if within policy",
    accent: "emerald",
  },
  {
    icon: <MapPin className="h-4 w-4" />,
    category: "Shipping",
    prompt: "Change the shipping address on my latest order.",
    hint: "Only before it ships",
    accent: "brand",
  },
  {
    icon: <ScrollText className="h-4 w-4" />,
    category: "Policy",
    prompt: "What's your return policy for opened items?",
    hint: "Returns, windows, exceptions",
    accent: "violet",
  },
];

const ACCENT_RING: Record<Suggestion["accent"], string> = {
  primary: "group-hover:ring-primary/30 [&_.bubble]:bg-primary/10 [&_.bubble]:text-primary",
  brand: "group-hover:ring-brand/30 [&_.bubble]:bg-brand/10 [&_.bubble]:text-brand",
  emerald:
    "group-hover:ring-emerald-500/30 [&_.bubble]:bg-emerald-500/10 [&_.bubble]:text-emerald-600 dark:[&_.bubble]:text-emerald-400",
  violet:
    "group-hover:ring-violet-500/30 [&_.bubble]:bg-violet-500/10 [&_.bubble]:text-violet-600 dark:[&_.bubble]:text-violet-400",
};

export function SuggestionChips({ onPick }: { onPick: (text: string) => void }) {
  return (
    <div className="mb-3 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2">
      {SUGGESTIONS.map((s) => (
        <button
          key={s.prompt}
          type="button"
          onClick={() => onPick(s.prompt)}
          className={`group flex flex-col gap-2 rounded-xl border bg-card/80 p-3 text-left ring-1 ring-transparent shadow-sm hover:bg-card hover:shadow-md transition-all ${ACCENT_RING[s.accent]}`}
        >
          <div className="flex items-center gap-2">
            <span className="bubble flex h-7 w-7 items-center justify-center rounded-lg">
              {s.icon}
            </span>
            <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              {s.category}
            </span>
          </div>
          <div className="text-sm font-medium leading-snug text-foreground/90 group-hover:text-foreground">
            {s.prompt}
          </div>
          <div className="text-[11px] text-muted-foreground">{s.hint}</div>
        </button>
      ))}
    </div>
  );
}
