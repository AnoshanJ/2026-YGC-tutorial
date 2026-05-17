import { useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  Box,
  Bot,
  Check,
  ChevronRight,
  CreditCard,
  MessageCircle,
  Package,
  Settings,
  ShieldCheck,
  Sparkles,
  Truck,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/ThemeToggle";
import { SettingsDialog } from "@/components/SettingsDialog";
import { NorthwindMark } from "@/components/NorthwindMark";

export default function Landing() {
  const [settingsOpen, setSettingsOpen] = useState(false);

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Nav onOpenSettings={() => setSettingsOpen(true)} />
      <Hero />
      <FeatureBand />
      <ProductStrip />
      <AriaPreview />
      <Footer />
      <SettingsDialog open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Top navigation                                                    */
/* ------------------------------------------------------------------ */

function Nav({ onOpenSettings }: { onOpenSettings: () => void }) {
  return (
    <header className="sticky top-0 z-30 border-b bg-background/80 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-3">
        <Link to="/" className="flex items-center gap-2">
          <NorthwindMark />
          <span className="font-semibold tracking-tight">Northwind</span>
        </Link>
        <nav className="hidden md:flex items-center gap-6 text-sm text-muted-foreground">
          <a href="#shop" className="hover:text-foreground transition-colors">Shop</a>
          <a href="#aria" className="hover:text-foreground transition-colors">Meet Aria</a>
          <a href="#help" className="hover:text-foreground transition-colors">Help</a>
          <a href="#story" className="hover:text-foreground transition-colors">Our story</a>
        </nav>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            onClick={onOpenSettings}
            aria-label="Agent connection settings"
            title="Agent connection"
          >
            <Settings className="h-4 w-4" />
          </Button>
          <ThemeToggle />
          <Link to="/login">
            <Button size="sm" className="ml-1">
              Open Aria
              <ArrowRight className="h-4 w-4" />
            </Button>
          </Link>
        </div>
      </div>
    </header>
  );
}

/* ------------------------------------------------------------------ */
/*  Hero                                                              */
/* ------------------------------------------------------------------ */

function Hero() {
  return (
    <section className="relative overflow-hidden">
      <div className="absolute inset-0 bg-aurora" aria-hidden />
      <div className="absolute inset-0 bg-grid opacity-40" aria-hidden />
      <div className="relative mx-auto max-w-6xl px-5 pt-16 pb-24 lg:pt-24 lg:pb-32 grid lg:grid-cols-[1.1fr,1fr] gap-12 items-center">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full border bg-card/70 px-3 py-1 text-xs font-medium text-muted-foreground backdrop-blur">
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
            New · Meet Aria, your Northwind concierge
          </div>
          <h1 className="mt-5 text-5xl lg:text-6xl font-bold tracking-tight leading-[1.05]">
            Shopping that
            <br />
            <span className="bg-gradient-to-r from-indigo-600 via-fuchsia-600 to-teal-500 dark:from-indigo-400 dark:via-fuchsia-400 dark:to-teal-300 bg-clip-text text-transparent">
              actually remembers you.
            </span>
          </h1>
          <p className="mt-6 max-w-xl text-lg text-muted-foreground leading-relaxed">
            Northwind makes the essentials worth keeping &mdash; and Aria handles the rest. Track an
            order, swap a size, settle a refund. No tickets, no hold music, no repeating yourself.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-3">
            <Link to="/login">
              <Button size="lg" className="gap-2">
                <Sparkles className="h-4 w-4" />
                Open Aria
              </Button>
            </Link>
            <a href="#aria">
              <Button size="lg" variant="outline" className="gap-2">
                See how it works
                <ChevronRight className="h-4 w-4" />
              </Button>
            </a>
          </div>
          <div className="mt-8 flex flex-wrap gap-x-6 gap-y-2 text-xs text-muted-foreground">
            <Trust label="Free returns, 60 days" />
            <Trust label="Carbon-neutral shipping" />
            <Trust label="4.8 / 5 from 12k customers" />
          </div>
        </div>

        <HeroVisual />
      </div>
    </section>
  );
}

function Trust({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-1.5">
      <Check className="h-3.5 w-3.5 text-emerald-500" />
      {label}
    </div>
  );
}

function HeroVisual() {
  // Pure-CSS hero composition: a glowing brand orb behind a stylized chat
  // preview, with three floating order chips drifting around it.
  return (
    <div className="relative h-[440px] hidden lg:block">
      <div className="brand-orb absolute left-1/2 top-1/2 h-56 w-56 -translate-x-1/2 -translate-y-1/2 rounded-full bg-card/30" />

      {/* Chat preview card */}
      <div className="absolute left-1/2 top-1/2 w-[360px] -translate-x-1/2 -translate-y-1/2 rounded-2xl border bg-card/80 p-4 shadow-2xl backdrop-blur-xl">
        <div className="flex items-center gap-2 border-b pb-3">
          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-primary/10 text-primary">
            <Bot className="h-3.5 w-3.5" />
          </div>
          <div className="text-xs">
            <div className="font-semibold">Aria · Northwind concierge</div>
            <div className="text-[10px] text-muted-foreground flex items-center gap-1">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 inline-block" /> Online
            </div>
          </div>
        </div>
        <div className="mt-3 space-y-2.5">
          <div className="ml-auto max-w-[80%] rounded-2xl rounded-br-sm bg-primary px-3 py-2 text-xs text-primary-foreground">
            Where is order #N-4827?
          </div>
          <div className="max-w-[88%] rounded-2xl rounded-bl-sm bg-muted px-3 py-2 text-xs">
            Out for delivery &mdash; arriving today before 6pm. Want me to text you when it's at the door?
          </div>
          <div className="ml-auto max-w-[60%] rounded-2xl rounded-br-sm bg-primary px-3 py-2 text-xs text-primary-foreground">
            Yes please.
          </div>
        </div>
      </div>

      {/* Floating chips */}
      <FloatingChip
        className="left-2 top-8 animate-float"
        icon={<Truck className="h-3.5 w-3.5" />}
        title="Order shipped"
        sub="N-4827 · 2 items"
      />
      <FloatingChip
        className="right-4 top-20 animate-float"
        style={{ animationDelay: "1.5s" }}
        icon={<CreditCard className="h-3.5 w-3.5" />}
        title="Refund issued"
        sub="$48.00 · instant"
      />
      <FloatingChip
        className="right-8 bottom-12 animate-float"
        style={{ animationDelay: "3s" }}
        icon={<Package className="h-3.5 w-3.5" />}
        title="Address updated"
        sub="2 orders re-routed"
      />
    </div>
  );
}

function FloatingChip({
  icon,
  title,
  sub,
  className,
  style,
}: {
  icon: React.ReactNode;
  title: string;
  sub: string;
  className?: string;
  style?: React.CSSProperties;
}) {
  return (
    <div
      className={`absolute flex items-center gap-2 rounded-xl border bg-card/90 px-3 py-2 shadow-lg backdrop-blur ${className ?? ""}`}
      style={style}
    >
      <div className="flex h-7 w-7 items-center justify-center rounded-md bg-brand/10 text-brand">
        {icon}
      </div>
      <div className="leading-tight">
        <div className="text-[11px] font-semibold">{title}</div>
        <div className="text-[10px] text-muted-foreground">{sub}</div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Feature band                                                      */
/* ------------------------------------------------------------------ */

function FeatureBand() {
  const items = [
    {
      icon: <Truck className="h-4 w-4" />,
      title: "Track every order",
      copy: "Ask once. Aria pulls your latest shipments and tells you exactly when they'll land.",
    },
    {
      icon: <CreditCard className="h-4 w-4" />,
      title: "Refunds in seconds",
      copy: "Within policy and under cap? Done. Outside it? Aria escalates without making you repeat anything.",
    },
    {
      icon: <Package className="h-4 w-4" />,
      title: "Change your mind",
      copy: "Swap a size, change your shipping address, cancel an order that hasn't gone out yet.",
    },
    {
      icon: <ShieldCheck className="h-4 w-4" />,
      title: "Knows you, only you",
      copy: "Your identity travels with every message. Aria can't see anyone else's orders, ever.",
    },
  ];
  return (
    <section className="border-y bg-card/40">
      <div className="mx-auto max-w-6xl px-5 py-16">
        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
          {items.map((it) => (
            <div
              key={it.title}
              className="card-sheen rounded-2xl border bg-card p-5 transition-shadow hover:shadow-md"
            >
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
                {it.icon}
              </div>
              <h3 className="mt-4 text-sm font-semibold">{it.title}</h3>
              <p className="mt-1.5 text-xs text-muted-foreground leading-relaxed">{it.copy}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/*  Product strip (visual filler, all CSS)                            */
/* ------------------------------------------------------------------ */

function ProductStrip() {
  // Six product placeholders rendered as gradient tiles. No images required —
  // the "feel" is what matters for the marketing surface.
  const swatches = [
    { name: "Linen Crew", price: "$48", from: "from-amber-200", to: "to-amber-400" },
    { name: "Walker 03", price: "$120", from: "from-emerald-200", to: "to-emerald-500" },
    { name: "Field Tote", price: "$72", from: "from-rose-200", to: "to-rose-400" },
    { name: "Cloud Hoodie", price: "$84", from: "from-sky-200", to: "to-sky-500" },
    { name: "Terrace Mug", price: "$18", from: "from-violet-200", to: "to-violet-400" },
    { name: "Trail Cap", price: "$28", from: "from-teal-200", to: "to-teal-500" },
  ];
  return (
    <section id="shop" className="mx-auto max-w-6xl px-5 py-20">
      <div className="flex items-end justify-between mb-8">
        <div>
          <div className="text-xs font-semibold uppercase tracking-widest text-brand">Shop</div>
          <h2 className="mt-2 text-2xl font-bold tracking-tight">New this week</h2>
        </div>
        <a href="#" className="text-sm text-muted-foreground hover:text-foreground inline-flex items-center gap-1">
          View all <ChevronRight className="h-4 w-4" />
        </a>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        {swatches.map((s) => (
          <div key={s.name} className="card-sheen group rounded-xl border bg-card p-2 transition-shadow hover:shadow-md">
            <div
              className={`aspect-square rounded-lg bg-gradient-to-br ${s.from} ${s.to} relative overflow-hidden`}
            >
              <div className="absolute inset-0 bg-[radial-gradient(circle_at_30%_30%,rgba(255,255,255,0.6),transparent_60%)]" />
            </div>
            <div className="mt-2 px-1.5 pb-1">
              <div className="text-xs font-medium">{s.name}</div>
              <div className="text-[11px] text-muted-foreground">{s.price}</div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/*  Aria preview ("Meet Aria" section)                                */
/* ------------------------------------------------------------------ */

function AriaPreview() {
  const prompts = [
    "Where is order N-4827?",
    "I need to return one of these shoes.",
    "Change shipping for order 5001 to my work address.",
    "What's your refund policy on opened items?",
  ];
  return (
    <section id="aria" className="border-t bg-card/30">
      <div className="mx-auto max-w-6xl px-5 py-20 grid lg:grid-cols-2 gap-12 items-center">
        <div>
          <div className="text-xs font-semibold uppercase tracking-widest text-brand">Meet Aria</div>
          <h2 className="mt-2 text-3xl lg:text-4xl font-bold tracking-tight">
            Less waiting. More <span className="text-primary">getting on with your day.</span>
          </h2>
          <p className="mt-4 text-muted-foreground max-w-lg leading-relaxed">
            Aria is the Northwind concierge. She already knows what you've bought, when it shipped,
            and what you're allowed to do about it. Just ask &mdash; in plain English.
          </p>
          <div className="mt-6 space-y-2.5">
            {prompts.map((p) => (
              <div
                key={p}
                className="flex items-center gap-2 rounded-lg border bg-card px-3 py-2 text-sm"
              >
                <MessageCircle className="h-4 w-4 text-primary shrink-0" />
                <span className="text-foreground/80">{p}</span>
              </div>
            ))}
          </div>
          <div className="mt-7">
            <Link to="/login">
              <Button size="lg" className="gap-2">
                <Sparkles className="h-4 w-4" />
                Try Aria with a demo account
              </Button>
            </Link>
          </div>
        </div>

        <div className="relative">
          <div className="brand-orb absolute -inset-10 rounded-full opacity-60" aria-hidden />
          <div className="relative rounded-2xl border bg-card shadow-xl overflow-hidden">
            <div className="flex items-center gap-2 border-b bg-card/60 px-4 py-3">
              <div className="flex h-7 w-7 items-center justify-center rounded-md bg-primary/10 text-primary">
                <Bot className="h-4 w-4" />
              </div>
              <div className="text-sm font-semibold">Aria</div>
              <div className="ml-auto flex items-center gap-1 text-[10px] text-muted-foreground">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" /> Connected
              </div>
            </div>
            <div className="p-4 space-y-3">
              <Bubble role="user">I bought the Walker 03 last week — can I exchange the size?</Bubble>
              <Bubble role="aria">
                Sure. Order <strong>N-4912</strong> arrived 3 days ago, well inside the 60-day window.
                Want me to start a free exchange and email a return label?
              </Bubble>
              <Bubble role="user">Yes, swap them to a 10.</Bubble>
              <Bubble role="aria">
                <div className="flex items-center gap-2 text-xs">
                  <Check className="h-3.5 w-3.5 text-emerald-500" />
                  Exchange started. Label sent to <strong>ava.morgan@example.com</strong>.
                </div>
                <div className="mt-2 inline-flex items-center gap-2 rounded-md border bg-background/50 px-2 py-1 text-[11px]">
                  <Box className="h-3 w-3 text-brand" />
                  New pair ships once we receive the return.
                </div>
              </Bubble>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function Bubble({ role, children }: { role: "user" | "aria"; children: React.ReactNode }) {
  const isUser = role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[85%] rounded-2xl px-3 py-2 text-xs leading-relaxed shadow-sm ${
          isUser
            ? "bg-primary text-primary-foreground rounded-br-sm"
            : "bg-muted text-foreground rounded-bl-sm"
        }`}
      >
        {children}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Footer                                                            */
/* ------------------------------------------------------------------ */

function Footer() {
  return (
    <footer id="help" className="border-t bg-background">
      <div className="mx-auto max-w-6xl px-5 py-10 grid sm:grid-cols-2 lg:grid-cols-4 gap-8 text-sm">
        <div>
          <div className="flex items-center gap-2">
            <NorthwindMark />
            <span className="font-semibold tracking-tight">Northwind</span>
          </div>
          <p className="mt-3 text-xs text-muted-foreground max-w-xs leading-relaxed">
            Modern essentials, made to last. Made for the way you actually live.
          </p>
        </div>
        <FooterCol title="Shop">
          <FooterLink>New arrivals</FooterLink>
          <FooterLink>Bestsellers</FooterLink>
          <FooterLink>Gift cards</FooterLink>
        </FooterCol>
        <FooterCol title="Help">
          <FooterLink>Talk to Aria</FooterLink>
          <FooterLink>Shipping &amp; returns</FooterLink>
          <FooterLink>Order status</FooterLink>
        </FooterCol>
        <FooterCol title="Company">
          <FooterLink>Our story</FooterLink>
          <FooterLink>Sustainability</FooterLink>
          <FooterLink>Careers</FooterLink>
        </FooterCol>
      </div>
      <div className="border-t">
        <div className="mx-auto max-w-6xl px-5 py-4 text-[11px] text-muted-foreground flex flex-wrap items-center justify-between gap-2">
          <span>&copy; {new Date().getFullYear()} Northwind Goods · A demo storefront for the WSO2 AI tutorial.</span>
          <span>Built on Agent Manager &middot; LangGraph &middot; OpenAI</span>
        </div>
      </div>
    </footer>
  );
}

function FooterCol({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">{title}</div>
      <ul className="mt-3 space-y-2 text-xs">{children}</ul>
    </div>
  );
}

function FooterLink({ children }: { children: React.ReactNode }) {
  return (
    <li>
      <a href="#" className="text-foreground/80 hover:text-foreground transition-colors">
        {children}
      </a>
    </li>
  );
}
