import {
  AlertOctagon,
  CheckCircle2,
  Key,
  Loader2,
  MapPin,
  Network,
  Package,
  Receipt,
  ScrollText,
  XCircle,
} from "lucide-react";
import type {
  AddressChange,
  Cancellation,
  Escalation,
  KnowledgeGraph as KG,
  Order,
  PolicyMention,
  Refund,
} from "@/lib/extract";

export type GraphStatus =
  | { kind: "idle" }
  | { kind: "extracting" }
  | { kind: "ok"; ts: number }
  | { kind: "error"; message: string }
  | { kind: "disabled" };

export function KnowledgeGraph({
  graph,
  status,
  onOpenSettings,
}: {
  graph: KG;
  status: GraphStatus;
  onOpenSettings: () => void;
}) {
  const total =
    graph.orders.length +
    graph.refunds.length +
    graph.address_changes.length +
    graph.cancellations.length +
    graph.policies.length +
    graph.escalations.length;

  return (
    <aside className="hidden md:flex flex-col border-r bg-card/40 w-80 shrink-0">
      <div className="flex items-center gap-2 border-b px-5 py-4">
        <div className="flex h-7 w-7 items-center justify-center rounded-md bg-brand/10 text-brand">
          <Network className="h-3.5 w-3.5" />
        </div>
        <div className="flex-1 leading-tight">
          <div className="text-sm font-semibold">What Aria knows</div>
          <div className="text-[11px] text-muted-foreground">
            {total === 0 ? "Updates appear as you chat." : `${total} ${total === 1 ? "item" : "items"} tracked`}
          </div>
        </div>
        <StatusBadge status={status} />
      </div>

      <div className="flex-1 overflow-y-auto px-3 py-3 space-y-3">
        {status.kind === "disabled" && (
          <EmptyState
            icon={<Key className="h-4 w-4" />}
            title="Add your OpenAI key"
            body="Paste an OpenAI API key in Settings and Aria will summarize each turn into a live graph here."
            actionLabel="Open Settings"
            onAction={onOpenSettings}
          />
        )}

        {status.kind !== "disabled" && total === 0 && (
          <EmptyState
            icon={<Network className="h-4 w-4" />}
            title="Nothing yet"
            body="Ask Aria about an order, a refund, or anything you'd like changed. Updates land here as you talk."
          />
        )}

        <Section title="Orders" icon={<Package className="h-3.5 w-3.5" />}>
          {graph.orders.map((o, i) => <OrderCard key={`${o.order_id}-${i}`} order={o} />)}
        </Section>

        <Section title="Refunds" icon={<Receipt className="h-3.5 w-3.5" />}>
          {graph.refunds.map((r, i) => <RefundCard key={i} refund={r} />)}
        </Section>

        <Section title="Address changes" icon={<MapPin className="h-3.5 w-3.5" />}>
          {graph.address_changes.map((a, i) => <AddressCard key={i} change={a} />)}
        </Section>

        <Section title="Cancellations" icon={<XCircle className="h-3.5 w-3.5" />}>
          {graph.cancellations.map((c, i) => <CancellationCard key={i} c={c} />)}
        </Section>

        <Section title="Policies" icon={<ScrollText className="h-3.5 w-3.5" />}>
          {graph.policies.map((p, i) => <PolicyCard key={i} p={p} />)}
        </Section>

        <Section title="Escalations" icon={<AlertOctagon className="h-3.5 w-3.5" />}>
          {graph.escalations.map((e, i) => <EscalationCard key={i} e={e} />)}
        </Section>
      </div>

      <div className="border-t px-5 py-3 text-[11px] text-muted-foreground leading-relaxed">
        Aria is designed to give you a personalized experience &mdash; she already knows your account,
        so just say what you need.
      </div>
    </aside>
  );
}

/* ---------- status pill ------------------------------------------------ */

function StatusBadge({ status }: { status: GraphStatus }) {
  if (status.kind === "extracting") {
    return (
      <span
        className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-medium text-primary"
        title="Updating the graph"
      >
        <Loader2 className="h-3 w-3 animate-spin" />
        Updating
      </span>
    );
  }
  if (status.kind === "ok") {
    return (
      <span
        className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] font-medium text-emerald-700 dark:text-emerald-300"
        title="Up to date"
      >
        <CheckCircle2 className="h-3 w-3" />
        Live
      </span>
    );
  }
  if (status.kind === "error") {
    return (
      <span
        className="inline-flex items-center gap-1 rounded-full bg-destructive/10 px-2 py-0.5 text-[10px] font-medium text-destructive"
        title={status.message}
      >
        <AlertOctagon className="h-3 w-3" />
        Error
      </span>
    );
  }
  return null;
}

/* ---------- section wrapper -------------------------------------------- */

function Section({
  title,
  icon,
  children,
}: {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode[];
}) {
  const items = (Array.isArray(children) ? children : [children]).filter(Boolean);
  if (items.length === 0) return null;
  return (
    <div>
      <div className="flex items-center gap-1.5 px-2 pb-1.5 text-[10px] uppercase tracking-wider font-semibold text-muted-foreground">
        <span className="text-brand">{icon}</span>
        {title}
        <span className="ml-auto text-[10px] font-normal opacity-60">{items.length}</span>
      </div>
      <div className="space-y-1.5">{items}</div>
    </div>
  );
}

/* ---------- entity cards ------------------------------------------------ */

function CardShell({
  children,
  accent = "primary",
}: {
  children: React.ReactNode;
  accent?: "primary" | "brand" | "emerald" | "rose" | "violet" | "amber";
}) {
  const stripe: Record<typeof accent, string> = {
    primary: "border-l-primary",
    brand: "border-l-brand",
    emerald: "border-l-emerald-500",
    rose: "border-l-rose-500",
    violet: "border-l-violet-500",
    amber: "border-l-amber-500",
  } as const;
  return (
    <div
      className={`rounded-lg border border-l-4 ${stripe[accent]} bg-card px-3 py-2 shadow-sm animate-fade-in`}
    >
      {children}
    </div>
  );
}

function OrderCard({ order }: { order: Order }) {
  return (
    <CardShell accent="primary">
      <div className="flex items-center gap-2">
        <span className="font-mono text-xs font-semibold">{order.order_id}</span>
        {order.status && <Pill>{order.status}</Pill>}
        {order.total && <span className="ml-auto text-xs font-medium">{order.total}</span>}
      </div>
      <p className="mt-1 text-xs text-muted-foreground leading-snug">{order.summary}</p>
      {(order.eta || (order.items && order.items.length > 0)) && (
        <div className="mt-1.5 flex flex-wrap gap-1">
          {order.eta && <Pill subtle>ETA · {order.eta}</Pill>}
          {order.items?.slice(0, 3).map((it, i) => <Pill key={i} subtle>{it}</Pill>)}
        </div>
      )}
    </CardShell>
  );
}

function RefundCard({ refund }: { refund: Refund }) {
  return (
    <CardShell accent="emerald">
      <div className="flex items-center gap-2">
        {refund.amount && <span className="text-xs font-semibold">{refund.amount}</span>}
        {refund.order_id && <span className="font-mono text-[11px] text-muted-foreground">{refund.order_id}</span>}
        {refund.status && <Pill className="ml-auto">{refund.status}</Pill>}
      </div>
      <p className="mt-1 text-xs text-muted-foreground leading-snug">{refund.summary}</p>
      {refund.reason && (
        <p className="mt-1 text-[11px] text-muted-foreground italic">&ldquo;{refund.reason}&rdquo;</p>
      )}
    </CardShell>
  );
}

function AddressCard({ change }: { change: AddressChange }) {
  return (
    <CardShell accent="brand">
      <div className="flex items-center gap-2">
        <MapPin className="h-3 w-3 text-brand" />
        {change.order_id && <span className="font-mono text-[11px] text-muted-foreground">{change.order_id}</span>}
      </div>
      <p className="mt-1 text-xs font-medium leading-snug">{change.new_address}</p>
      <p className="mt-0.5 text-[11px] text-muted-foreground leading-snug">{change.summary}</p>
    </CardShell>
  );
}

function CancellationCard({ c }: { c: Cancellation }) {
  return (
    <CardShell accent="rose">
      <div className="flex items-center gap-2">
        <XCircle className="h-3 w-3 text-rose-500" />
        <span className="font-mono text-xs font-semibold">{c.order_id}</span>
      </div>
      <p className="mt-1 text-xs text-muted-foreground leading-snug">{c.summary}</p>
    </CardShell>
  );
}

function PolicyCard({ p }: { p: PolicyMention }) {
  return (
    <CardShell accent="violet">
      <div className="text-xs font-semibold">{p.topic}</div>
      <p className="mt-0.5 text-xs text-muted-foreground leading-snug">{p.summary}</p>
    </CardShell>
  );
}

function EscalationCard({ e }: { e: Escalation }) {
  return (
    <CardShell accent="amber">
      <div className="flex items-center gap-2">
        <AlertOctagon className="h-3 w-3 text-amber-600" />
        <span className="text-xs font-semibold">{e.reason}</span>
      </div>
      <p className="mt-1 text-xs text-muted-foreground leading-snug">{e.summary}</p>
    </CardShell>
  );
}

/* ---------- bits ------------------------------------------------------- */

function Pill({
  children,
  subtle,
  className,
}: {
  children: React.ReactNode;
  subtle?: boolean;
  className?: string;
}) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-1.5 py-0.5 text-[10px] font-medium capitalize ${
        subtle
          ? "bg-muted text-muted-foreground"
          : "bg-primary/10 text-primary"
      } ${className ?? ""}`}
    >
      {children}
    </span>
  );
}

function EmptyState({
  icon,
  title,
  body,
  actionLabel,
  onAction,
}: {
  icon: React.ReactNode;
  title: string;
  body: string;
  actionLabel?: string;
  onAction?: () => void;
}) {
  return (
    <div className="rounded-xl border border-dashed bg-card/50 px-4 py-5 text-center">
      <div className="mx-auto mb-2 flex h-8 w-8 items-center justify-center rounded-full bg-muted text-muted-foreground">
        {icon}
      </div>
      <div className="text-sm font-semibold">{title}</div>
      <p className="mt-1 text-[11px] text-muted-foreground leading-relaxed">{body}</p>
      {actionLabel && onAction && (
        <button
          type="button"
          onClick={onAction}
          className="mt-3 inline-flex items-center gap-1 rounded-md border bg-card px-2.5 py-1 text-[11px] font-medium hover:bg-accent transition-colors"
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
}
