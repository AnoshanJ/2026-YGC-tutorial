import { cn } from "@/lib/utils";

// CSS-only brand mark — a soft gradient "N" tile that reads as both Northwind
// and a chat bubble at small sizes. No image asset required.
export function NorthwindMark({
  className,
  size = 32,
}: {
  className?: string;
  size?: number;
}) {
  return (
    <div
      className={cn(
        "relative flex items-center justify-center rounded-lg text-primary-foreground font-bold shadow-sm",
        className,
      )}
      style={{
        width: size,
        height: size,
        background:
          "conic-gradient(from 220deg at 50% 50%, hsl(221 83% 53%), hsl(280 75% 60%), hsl(188 78% 50%), hsl(221 83% 53%))",
        fontSize: size * 0.55,
        lineHeight: 1,
      }}
      aria-hidden
    >
      <span className="drop-shadow-[0_1px_0_rgba(0,0,0,0.2)]">N</span>
      <span
        className="absolute right-[-2px] bottom-[-2px] h-2 w-2 rounded-full bg-emerald-400 ring-2 ring-background"
        aria-hidden
      />
    </div>
  );
}
