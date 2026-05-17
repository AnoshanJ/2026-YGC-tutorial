import { Bot } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
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
  const isAssistant = msg.role === "assistant";
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
          "max-w-[78%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed shadow-sm",
          !isAssistant && "whitespace-pre-wrap",
          isUser && "bg-primary text-primary-foreground rounded-br-sm",
          !isUser && !isError && "bg-card border rounded-bl-sm",
          isError && "bg-destructive/10 border border-destructive/30 text-destructive rounded-bl-sm",
        )}
      >
        {isAssistant ? <Markdown content={msg.content} /> : msg.content}
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

function Markdown({ content }: { content: string }) {
  return (
    <div className="space-y-2 [&>*:first-child]:mt-0 [&>*:last-child]:mb-0">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          p: ({ children }) => <p className="my-2 whitespace-pre-wrap">{children}</p>,
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noreferrer noopener"
              className="text-primary underline underline-offset-2 hover:opacity-80"
            >
              {children}
            </a>
          ),
          ul: ({ children }) => <ul className="my-2 list-disc pl-5 space-y-1">{children}</ul>,
          ol: ({ children }) => <ol className="my-2 list-decimal pl-5 space-y-1">{children}</ol>,
          li: ({ children }) => <li className="leading-relaxed">{children}</li>,
          h1: ({ children }) => <h1 className="mt-3 mb-2 text-base font-semibold">{children}</h1>,
          h2: ({ children }) => <h2 className="mt-3 mb-2 text-sm font-semibold">{children}</h2>,
          h3: ({ children }) => <h3 className="mt-2 mb-1 text-sm font-semibold">{children}</h3>,
          strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
          em: ({ children }) => <em className="italic">{children}</em>,
          blockquote: ({ children }) => (
            <blockquote className="my-2 border-l-2 border-muted-foreground/30 pl-3 italic text-muted-foreground">
              {children}
            </blockquote>
          ),
          code: ({ className, children, ...props }) => {
            const isBlock = /language-/.test(className || "");
            if (isBlock) {
              return (
                <code className="block whitespace-pre" {...props}>
                  {children}
                </code>
              );
            }
            return (
              <code
                className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em]"
                {...props}
              >
                {children}
              </code>
            );
          },
          pre: ({ children }) => (
            <pre className="my-2 overflow-x-auto rounded-md bg-muted p-3 text-[0.85em] font-mono">
              {children}
            </pre>
          ),
          table: ({ children }) => (
            <div className="my-2 overflow-x-auto">
              <table className="w-full border-collapse text-left text-[0.9em]">{children}</table>
            </div>
          ),
          th: ({ children }) => (
            <th className="border-b border-border px-2 py-1 font-semibold">{children}</th>
          ),
          td: ({ children }) => <td className="border-b border-border/50 px-2 py-1">{children}</td>,
          hr: () => <hr className="my-3 border-border" />,
        }}
      >
        {content}
      </ReactMarkdown>
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
