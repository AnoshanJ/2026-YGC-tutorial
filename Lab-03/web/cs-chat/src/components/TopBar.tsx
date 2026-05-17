import { LogOut, MessageSquare, RotateCcw } from "lucide-react";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn, initials } from "@/lib/utils";
import type { Customer } from "@/lib/users";

const TIER_COLOR: Record<Customer["tier"], string> = {
  bronze: "bg-amber-700/15 text-amber-700 border-amber-700/20",
  silver: "bg-slate-400/15 text-slate-600 border-slate-400/20",
  gold: "bg-yellow-500/15 text-yellow-700 border-yellow-500/20",
  platinum: "bg-indigo-500/15 text-indigo-700 border-indigo-500/20",
};

export function TopBar({
  user,
  onNewSession,
  onLogout,
}: {
  user: Customer;
  onNewSession: () => void;
  onLogout: () => void;
}) {
  return (
    <header className="flex items-center justify-between border-b bg-card/80 backdrop-blur px-5 py-3">
      <div className="flex items-center gap-2">
        <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary text-primary-foreground">
          <MessageSquare className="h-4 w-4" />
        </div>
        <div className="leading-tight">
          <div className="text-sm font-semibold">Acme Support</div>
          <div className="text-[11px] text-muted-foreground">Customer portal · live chat</div>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <div className="hidden sm:flex flex-col items-end">
          <div className="text-sm font-medium leading-tight">{user.name}</div>
          <div className="flex items-center gap-1 text-[11px] text-muted-foreground leading-tight">
            <span className="font-mono">{user.id}</span>
            <Badge variant="outline" className={cn("h-4 text-[10px] px-1.5 capitalize", TIER_COLOR[user.tier])}>
              {user.tier}
            </Badge>
            <Badge variant="outline" className="h-4 text-[10px] px-1.5">
              {user.region}
            </Badge>
          </div>
        </div>
        <Avatar className="h-9 w-9 bg-secondary">
          <AvatarFallback className="text-xs font-semibold">{initials(user.name)}</AvatarFallback>
        </Avatar>
        <Button variant="ghost" size="sm" onClick={onNewSession} title="Start a new chat session">
          <RotateCcw className="h-4 w-4" />
          <span className="hidden md:inline">New session</span>
        </Button>
        <Button variant="ghost" size="sm" onClick={onLogout}>
          <LogOut className="h-4 w-4" />
          <span className="hidden md:inline">Logout</span>
        </Button>
      </div>
    </header>
  );
}
