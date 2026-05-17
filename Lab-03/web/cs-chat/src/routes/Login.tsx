import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { MessageCircle, Sparkles, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { findUser } from "@/lib/users";
import { setCurrentUser } from "@/lib/auth";

export default function Login() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

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

  return (
    <div className="min-h-screen bg-aurora flex items-center justify-center p-6">
      <div className="w-full max-w-5xl grid lg:grid-cols-2 gap-10 items-center">
        {/* Marketing side */}
        <div className="hidden lg:block text-left">
          <div className="inline-flex items-center gap-2 rounded-full bg-primary/10 px-3 py-1 text-xs font-semibold text-primary mb-6">
            <Sparkles className="h-3.5 w-3.5" /> Acme Customer Portal
          </div>
          <h1 className="text-5xl font-bold tracking-tight leading-tight">
            Support that <span className="text-primary">remembers</span> you.
          </h1>
          <p className="mt-5 text-lg text-muted-foreground max-w-md">
            Chat with our team about orders, refunds, and shipping &mdash; we already know who you are
            and what you've bought, so you can skip the small talk.
          </p>
          <div className="mt-8 space-y-3 text-sm">
            <Feature icon={<MessageCircle className="h-4 w-4" />} text="Live agent over chat, 24/7." />
            <Feature icon={<ShieldCheck className="h-4 w-4" />} text="Refunds processed in seconds." />
            <Feature icon={<Sparkles className="h-4 w-4" />} text="Personalized to your account." />
          </div>
        </div>

        {/* Auth card */}
        <Card className="shadow-xl border-border/60">
          <CardHeader className="space-y-2">
            <CardTitle className="text-2xl">Welcome back</CardTitle>
            <CardDescription>Sign in to continue to your support session.</CardDescription>
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

            <div className="mt-6 rounded-md border bg-muted/40 px-3 py-3 text-xs text-muted-foreground space-y-1">
              <p className="font-semibold text-foreground">Demo accounts</p>
              <p>
                <code className="font-mono">ava.morgan@example.com</code> &middot; gold &middot; NA
              </p>
              <p>
                <code className="font-mono">lukas.weber@example.de</code> &middot; silver &middot; EMEA
              </p>
              <p>
                <code className="font-mono">sora.tanaka@example.jp</code> &middot; gold &middot; APAC
              </p>
              <p className="pt-1">Password is anything non-empty.</p>
            </div>
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
