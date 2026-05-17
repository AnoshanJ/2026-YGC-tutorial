import { Link } from "react-router-dom";
import { RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/ThemeToggle";
import { UserMenu } from "@/components/UserMenu";
import { NorthwindMark } from "@/components/NorthwindMark";
import type { Customer } from "@/lib/users";

export function TopBar({
  user,
  onNewSession,
  onLogout,
  onOpenSettings,
}: {
  user: Customer;
  onNewSession: () => void;
  onLogout: () => void;
  onOpenSettings: () => void;
}) {
  return (
    <header className="flex items-center justify-between border-b bg-card/80 backdrop-blur px-5 py-2.5">
      <Link to="/" className="flex items-center gap-2 group">
        <NorthwindMark size={28} />
        <div className="leading-tight">
          <div className="text-sm font-semibold tracking-tight group-hover:text-primary transition-colors">
            Northwind
          </div>
          <div className="text-[11px] text-muted-foreground">Aria · concierge chat</div>
        </div>
      </Link>

      <div className="flex items-center gap-1">
        <Button
          variant="ghost"
          size="sm"
          onClick={onNewSession}
          title="Start a new chat session"
        >
          <RotateCcw className="h-4 w-4" />
          <span className="hidden md:inline">New session</span>
        </Button>
        <ThemeToggle />
        <div className="mx-1 h-5 w-px bg-border" aria-hidden />
        <UserMenu user={user} onOpenSettings={onOpenSettings} onLogout={onLogout} />
      </div>
    </header>
  );
}
