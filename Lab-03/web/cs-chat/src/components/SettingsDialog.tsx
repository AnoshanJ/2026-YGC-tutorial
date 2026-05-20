import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { Eye, EyeOff, Network, Trash2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { clearOpenAIKey, getOpenAIKey, setOpenAIKey } from "@/lib/extract";

export function SettingsDialog({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const [openaiKey, setOpenaiKeyInput] = useState(() => getOpenAIKey() ?? "");
  const [initialOpenai, setInitialOpenai] = useState(() => getOpenAIKey() ?? "");
  const [showOpenai, setShowOpenai] = useState(false);

  // Re-sync whenever the dialog opens.
  useEffect(() => {
    if (!open) return;
    const oai = getOpenAIKey() ?? "";
    setOpenaiKeyInput(oai);
    setInitialOpenai(oai);
  }, [open]);

  // Esc to close.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  const trimmed = openaiKey.trim();
  const isDirty = trimmed !== initialOpenai;

  const onSave = () => {
    if (trimmed) setOpenAIKey(trimmed);
    else clearOpenAIKey();
    onClose();
  };

  const onClear = () => {
    clearOpenAIKey();
    setOpenaiKeyInput("");
    setInitialOpenai("");
  };

  return createPortal(
    <div
      className="fixed inset-0 z-[70] flex items-center justify-center bg-foreground/40 backdrop-blur-sm p-4 animate-fade-in"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="w-full max-w-md rounded-2xl border bg-card shadow-2xl">
        <div className="flex items-center justify-between border-b px-5 py-3">
          <div className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-md bg-brand/10 text-brand">
              <Network className="h-3.5 w-3.5" />
            </div>
            <div className="leading-tight">
              <div className="text-sm font-semibold">Settings</div>
              <div className="text-[11px] text-muted-foreground">
                Configure your live knowledge graph.
              </div>
            </div>
          </div>
          <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close settings">
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="px-5 py-5 space-y-3">
          <div>
            <h3 className="text-sm font-semibold">Live knowledge graph</h3>
            <p className="mt-1 text-xs text-muted-foreground leading-relaxed">
              Aria uses your OpenAI key to summarize each turn into the graph on the left. Leave
              empty to disable.
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="openai-key" className="text-xs">OpenAI API key</Label>
            <div className="relative">
              <Input
                id="openai-key"
                type={showOpenai ? "text" : "password"}
                spellCheck={false}
                autoComplete="off"
                placeholder="sk-..."
                value={openaiKey}
                onChange={(e) => setOpenaiKeyInput(e.target.value)}
                className="pr-10 font-mono text-xs"
              />
              <button
                type="button"
                onClick={() => setShowOpenai((v) => !v)}
                className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-muted-foreground hover:text-foreground"
                aria-label={showOpenai ? "Hide key" : "Show key"}
              >
                {showOpenai ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
              </button>
            </div>
            <p className="text-[11px] text-muted-foreground">
              Stored only in this browser. Sent directly to <code>api.openai.com</code>.
            </p>
          </div>
        </div>

        <div className="flex items-center justify-between gap-2 border-t bg-muted/30 px-5 py-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={onClear}
            disabled={!initialOpenai}
            title="Remove the saved OpenAI key"
          >
            <Trash2 className="h-3.5 w-3.5" />
            Clear key
          </Button>
          <Button size="sm" onClick={onSave} disabled={!isDirty}>
            Save
          </Button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
