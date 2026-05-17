import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { ChevronDown, LogOut, Settings } from "lucide-react";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { cn, initials } from "@/lib/utils";
import type { Customer } from "@/lib/users";

const TIER_COLOR: Record<Customer["tier"], string> = {
  bronze: "bg-amber-700/15 text-amber-700 border-amber-700/20 dark:text-amber-300",
  silver: "bg-slate-400/15 text-slate-600 border-slate-400/20 dark:text-slate-300",
  gold: "bg-yellow-500/15 text-yellow-700 border-yellow-500/20 dark:text-yellow-300",
  platinum: "bg-indigo-500/15 text-indigo-700 border-indigo-500/20 dark:text-indigo-300",
};

const MENU_WIDTH = 288; // w-72
const GAP_BELOW_TRIGGER = 8; // mt-2

export function UserMenu({
  user,
  onOpenSettings,
  onLogout,
}: {
  user: Customer;
  onOpenSettings: () => void;
  onLogout: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [coords, setCoords] = useState<{ top: number; right: number } | null>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  // Position the portaled menu just below the trigger button's bottom-right.
  // Recompute on open and on viewport resize/scroll so it stays anchored.
  useLayoutEffect(() => {
    if (!open) return;
    const update = () => {
      const el = triggerRef.current;
      if (!el) return;
      const rect = el.getBoundingClientRect();
      setCoords({
        top: rect.bottom + GAP_BELOW_TRIGGER,
        right: window.innerWidth - rect.right,
      });
    };
    update();
    window.addEventListener("resize", update);
    window.addEventListener("scroll", update, true);
    return () => {
      window.removeEventListener("resize", update);
      window.removeEventListener("scroll", update, true);
    };
  }, [open]);

  // Esc to close.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  // Strip the "C-" customer-key prefix for display — internal ID format,
  // shouldn't look like a negative number to the customer.
  const memberNumber = user.id.replace(/^[A-Z]+-/, "");

  const handleSettings = () => {
    setOpen(false);
    onOpenSettings();
  };
  const handleLogout = () => {
    setOpen(false);
    onLogout();
  };

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setOpen((v) => !v)}
        className={cn(
          "flex items-center gap-2 rounded-full pl-1 pr-2 py-1 hover:bg-accent transition-colors",
          open && "bg-accent",
        )}
        aria-haspopup="menu"
        aria-expanded={open}
      >
        <Avatar className="h-8 w-8 bg-secondary ring-1 ring-border">
          <AvatarFallback className="text-xs font-semibold">{initials(user.name)}</AvatarFallback>
        </Avatar>
        <span className="hidden sm:inline text-sm font-medium leading-none">
          {user.name.split(" ")[0]}
        </span>
        <ChevronDown
          className={cn(
            "h-3.5 w-3.5 text-muted-foreground transition-transform",
            open && "rotate-180",
          )}
        />
      </button>

      {open && coords && createPortal(
        <>
          {/* Full-viewport backdrop — closes the menu on outside click. */}
          <div
            className="fixed inset-0 z-[55]"
            onClick={() => setOpen(false)}
            aria-hidden
          />
          {/* Menu — portaled to body so it escapes the header's backdrop-filter
              stacking context, which otherwise traps clicks. */}
          <div
            role="menu"
            style={{ top: coords.top, right: coords.right, width: MENU_WIDTH }}
            className="fixed z-[60] rounded-xl border bg-popover text-popover-foreground shadow-xl overflow-hidden animate-fade-in"
          >
            <div className="px-4 py-3 border-b">
              <div className="flex items-center gap-3">
                <Avatar className="h-10 w-10 bg-secondary">
                  <AvatarFallback className="text-sm font-semibold">
                    {initials(user.name)}
                  </AvatarFallback>
                </Avatar>
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-semibold truncate">{user.name}</div>
                  <div className="text-[11px] text-muted-foreground truncate">{user.email}</div>
                </div>
              </div>
              <div className="mt-3 flex items-center gap-1.5">
                <span
                  className={cn(
                    "inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-medium capitalize",
                    TIER_COLOR[user.tier],
                  )}
                >
                  {user.tier} member
                </span>
                <span className="inline-flex items-center rounded-full border bg-muted/50 px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
                  {user.region}
                </span>
                <span className="ml-auto text-[10px] text-muted-foreground">
                  #{memberNumber}
                </span>
              </div>
            </div>

            <div className="py-1">
              <MenuItem
                icon={<Settings className="h-4 w-4" />}
                label="Settings"
                onClick={handleSettings}
              />
              <MenuItem
                icon={<LogOut className="h-4 w-4" />}
                label="Sign out"
                onClick={handleLogout}
              />
            </div>
          </div>
        </>,
        document.body,
      )}
    </>
  );
}

function MenuItem({
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
      role="menuitem"
      onClick={onClick}
      className="flex w-full items-center gap-2.5 px-4 py-2 text-sm hover:bg-accent text-foreground/90 hover:text-foreground transition-colors text-left"
    >
      <span className="text-muted-foreground">{icon}</span>
      {label}
    </button>
  );
}
