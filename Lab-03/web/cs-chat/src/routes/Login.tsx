import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowLeft, Eye, EyeOff, MessageCircle, ShieldCheck, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ThemeToggle } from "@/components/ThemeToggle";
import { NorthwindMark } from "@/components/NorthwindMark";
import { findUser } from "@/lib/users";
import { setCurrentUser } from "@/lib/auth";

export default function Login() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [showDemos, setShowDemos] = useState(false);

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!email.trim() || !password.trim()) return;
    setSubmitting(true);
    // Pseudo-login: any password works; email picks the persona.
    const user = findUser(email);
    setTimeout(() => {
      if (!user) {
        setError("We couldn't find an account with that email.");
        setSubmitting(false);
        return;
      }
      setCurrentUser(user);
      navigate("/chat", { replace: true });
    }, 250);
  };

  const useDemo = (e: string) => {
    setEmail(e);
    setPassword("demo");
  };

  return (
    <div className="min-h-screen bg-aurora">
      <div className="mx-auto max-w-6xl px-5 py-4 flex items-center justify-between">
        <Link
          to="/"
          className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Northwind
        </Link>
        <ThemeToggle />
      </div>

      <div className="mx-auto max-w-5xl px-5 py-10 grid lg:grid-cols-2 gap-12 items-center">
        {/* Marketing side */}
        <div className="hidden lg:block">
          <div className="flex items-center gap-2">
            <NorthwindMark />
            <span className="font-semibold tracking-tight">Northwind</span>
          </div>
          <div className="mt-8 inline-flex items-center gap-2 rounded-full bg-primary/10 px-3 py-1 text-xs font-semibold text-primary">
            <Sparkles className="h-3.5 w-3.5" /> Aria · your Northwind concierge
          </div>
          <h1 className="mt-4 text-5xl font-bold tracking-tight leading-tight">
            Sign in to chat with <span className="text-primary">Aria</span>.
          </h1>
          <p className="mt-5 text-lg text-muted-foreground max-w-md">
            She'll already know your orders, your shipping address, and what you're allowed to do
            about them &mdash; so you can skip the small talk.
          </p>
          <div className="mt-8 space-y-3 text-sm">
            <Feature icon={<MessageCircle className="h-4 w-4" />} text="Chat 24/7, no wait time." />
            <Feature icon={<ShieldCheck className="h-4 w-4" />} text="Refunds processed in seconds." />
            <Feature icon={<Sparkles className="h-4 w-4" />} text="Personalized to your account." />
          </div>
        </div>

        {/* Auth card */}
        <Card className="shadow-xl border-border/60">
          <CardHeader className="space-y-2">
            <CardTitle className="text-2xl">Welcome back</CardTitle>
            <CardDescription>Sign in to continue to your Northwind concierge.</CardDescription>
          </CardHeader>
          <CardContent>
            <form className="space-y-4" onSubmit={onSubmit} autoComplete="off">
              {error && (
                <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  {error}
                </div>
              )}
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  placeholder="you@example.com"
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="password">Password</Label>
                <Input
                  id="password"
                  type="password"
                  placeholder="••••••••"
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
              </div>
              <Button type="submit" className="w-full" disabled={submitting}>
                {submitting ? "Signing in…" : "Sign in"}
              </Button>
            </form>

            <div className="mt-6 flex justify-end">
              <button
                type="button"
                onClick={() => setShowDemos((v) => !v)}
                aria-label={showDemos ? "Hide demo accounts" : "Show demo accounts"}
                className="rounded p-1 text-muted-foreground/30 hover:text-muted-foreground transition-colors"
              >
                {showDemos ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
              </button>
            </div>
            {showDemos && (
              <div className="mt-2 rounded-md border bg-muted/40 px-3 py-3 text-xs text-muted-foreground space-y-1.5">
                <DemoRow email="ava.morgan@example.com" tag="gold · NA" onPick={useDemo} />
                <DemoRow email="lukas.weber@example.de" tag="silver · EMEA" onPick={useDemo} />
                <DemoRow email="sora.tanaka@example.jp" tag="gold · APAC" onPick={useDemo} />
                <p className="pt-1">Password is anything non-empty.</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function Feature({ icon, text }: { icon: React.ReactNode; text: string }) {
  return (
    <div className="flex items-center gap-2 text-foreground/80">
      <span className="text-primary">{icon}</span>
      {text}
    </div>
  );
}

function DemoRow({
  email,
  tag,
  onPick,
}: {
  email: string;
  tag: string;
  onPick: (e: string) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onPick(email)}
      className="flex w-full items-center justify-between rounded px-2 py-1 -mx-2 text-left hover:bg-accent hover:text-accent-foreground transition-colors"
    >
      <code className="font-mono">{email}</code>
      <span className="text-[10px] text-muted-foreground">{tag}</span>
    </button>
  );
}
