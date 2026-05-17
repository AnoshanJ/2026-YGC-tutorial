import { Bot } from "lucide-react";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { cn, initials } from "@/lib/utils";

export type Message = {
  id: string;
  role: "user" | "assistant" | "error";
  content: string;
  ts: number;
};

export function MessageBubble({
  msg,
  userName,
}: {
  msg: Message;
  userName: string;
}) {
  const isUser = msg.role === "user";
  const isError = msg.role === "error";
  return (
    <div
      className={cn(
        "flex w-full animate-fade-in",
        isUser ? "justify-end" : "justify-start",
      )}
    >
      {!isUser && (
        <Avatar className="mr-3 h-8 w-8 bg-primary/10 ring-1 ring-primary/20">
          <AvatarFallback className="bg-transparent text-primary">
            <Bot className="h-4 w-4" />
          </AvatarFallback>
        </Avatar>
      )}
      <div
        className={cn(
          "max-w-[78%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap shadow-sm",
          isUser && "bg-primary text-primary-foreground rounded-br-sm",
          !isUser && !isError && "bg-card border rounded-bl-sm",
          isError && "bg-destructive/10 border border-destructive/30 text-destructive rounded-bl-sm",
        )}
      >
        {msg.content}
      </div>
      {isUser && (
        <Avatar className="ml-3 h-8 w-8 bg-secondary">
          <AvatarFallback className="text-[11px] font-semibold text-secondary-foreground">
            {initials(userName)}
          </AvatarFallback>
        </Avatar>
      )}
    </div>
  );
}

export function TypingBubble() {
  return (
    <div className="flex justify-start animate-fade-in">
      <Avatar className="mr-3 h-8 w-8 bg-primary/10 ring-1 ring-primary/20">
        <AvatarFallback className="bg-transparent text-primary">
          <Bot className="h-4 w-4" />
        </AvatarFallback>
      </Avatar>
      <div className="bg-card border rounded-2xl rounded-bl-sm px-4 py-3 shadow-sm">
        <div className="flex gap-1.5">
          <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground/60 animate-blink" />
          <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground/60 animate-blink" style={{ animationDelay: "120ms" }} />
          <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground/60 animate-blink" style={{ animationDelay: "240ms" }} />
        </div>
      </div>
    </div>
  );
}
