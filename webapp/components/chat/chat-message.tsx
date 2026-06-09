"use client";

import { Bot, Coins, FileText, ThumbsDown, ThumbsUp, UserRound } from "lucide-react";

import { MarkdownRenderer } from "@/components/chat/markdown-renderer";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { formatNumber, formatVnd } from "@/lib/format";
import type { ChatUsage } from "@/types/api";
import type { ChatMessage } from "@/types/chat";
import { cn } from "@/lib/utils";

interface ChatMessageProps {
  message: ChatMessage;
  isStreaming?: boolean;
  isThinking?: boolean;
  usage?: ChatUsage | null;
  feedback?: "like" | "dislike" | null;
  feedbackDisabled?: boolean;
  onFeedback?: (messageId: string, feedbackType: "like" | "dislike") => void;
}

export function ChatMessage({
  message,
  isStreaming = false,
  isThinking = false,
  usage,
  feedback = null,
  feedbackDisabled = false,
  onFeedback,
}: ChatMessageProps) {
  const isUser = message.role === "user";
  const showLoading = !isUser && isThinking && !message.content;
  const citations = Array.from(
    new Map(
      (message.citations || []).map((citation) => [
        `${citation.document_id}-${citation.section_id}-${citation.file_name || citation.title}`,
        citation,
      ]),
    ).values(),
  );
  const visibleCitations = citations.slice(0, 4);
  const hiddenCitationCount = Math.max(citations.length - visibleCitations.length, 0);

  return (
    <div className={cn("group/message flex gap-3 px-4 py-4", isUser ? "justify-end" : "justify-start")}>
      {!isUser ? (
        <Avatar className="mt-0.5 h-8 w-8 shrink-0 ring-1 ring-border/40">
          <AvatarFallback className="bg-gradient-to-br from-primary to-[#084ea4] text-primary-foreground">
            <Bot className="h-4 w-4" />
          </AvatarFallback>
        </Avatar>
      ) : null}

      <div className={cn("flex max-w-[92%] min-w-0 flex-col gap-2 sm:max-w-[78%]", isUser ? "items-end" : "items-start")}>
        <div
          className={cn(
            "text-[11px] font-medium tracking-wide uppercase opacity-60",
            isUser ? "text-muted-foreground" : "text-primary/80",
          )}
        >
          {isUser ? "Bạn" : "SSE Assistant"}
        </div>

        {isUser ? (
          <div className="rounded-2xl rounded-tr-md bg-primary px-4 py-2.5 text-[15px] leading-6 text-primary-foreground shadow-[0_2px_12px_-6px_rgba(1,56,123,0.4)]">
            <div className="whitespace-pre-wrap break-words">{message.content}</div>
          </div>
        ) : (
          <>
            {showLoading ? (
              <div className="rounded-2xl rounded-tl-md bg-muted/60 px-4 py-3 text-sm text-muted-foreground">
                <span className="inline-flex items-center gap-1.5">
                  <span className="size-1.5 animate-pulse rounded-full bg-primary/60" />
                  <span className="size-1.5 animate-pulse rounded-full bg-primary/60 [animation-delay:120ms]" />
                  <span className="size-1.5 animate-pulse rounded-full bg-primary/60 [animation-delay:240ms]" />
                  Đang suy luận...
                </span>
              </div>
            ) : null}

            {message.content ? (
              <div
                className={cn(
                  "rounded-2xl rounded-tl-md bg-muted/40 px-4 py-3 text-[15px] leading-6 text-foreground",
                  isStreaming && "streaming-active",
                )}
              >
                <MarkdownRenderer content={message.content} showCursor={isStreaming} />
              </div>
            ) : null}

            {!!citations.length && !isStreaming ? (
              <div className="w-full space-y-2 rounded-xl border border-border/50 bg-background/60 p-3">
                <div className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                  <FileText className="h-3 w-3" />
                  Nguồn tham khảo
                </div>
                <div className="grid gap-1.5">
                  {visibleCitations.map((citation, index) => (
                    <div
                      key={`${citation.document_id}-${citation.section_id}-${index}`}
                      className="flex items-start gap-2 rounded-lg bg-muted/30 px-2.5 py-2 text-xs transition-colors hover:bg-muted/60"
                    >
                      <Badge variant="outline" className="mt-0.5 h-5 shrink-0 rounded-full px-1.5 text-[10px]">
                        {index + 1}
                      </Badge>
                      <div className="min-w-0 flex-1">
                        <div className="truncate font-medium text-foreground">
                          {citation.file_name || citation.title}
                        </div>
                        <div className="mt-0.5 text-muted-foreground">
                          {citation.heading || citation.title}
                          {citation.page_range ? ` · trang ${citation.page_range}` : ""}
                        </div>
                      </div>
                    </div>
                  ))}
                  {hiddenCitationCount > 0 ? (
                    <div className="px-2.5 text-xs text-muted-foreground">+{hiddenCitationCount} nguồn khác</div>
                  ) : null}
                </div>
              </div>
            ) : null}

            {usage && !isStreaming ? (
              <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
                <Badge variant="secondary" className="gap-1 rounded-full px-2.5 py-0.5 font-normal">
                  <Coins className="h-3 w-3" />
                  {formatNumber(usage.total_tokens)} token
                </Badge>
                <Badge variant="secondary" className="rounded-full px-2.5 py-0.5 font-normal">
                  {formatVnd(usage.cost_vnd_rounded)}
                </Badge>
                <Badge variant="outline" className="rounded-full px-2.5 py-0.5 font-normal text-muted-foreground">
                  {usage.model || "chatbot-rag"}
                </Badge>
              </div>
            ) : null}

            {!isStreaming && message.content ? (
              <div className="flex items-center gap-1.5 pt-1">
                <button
                  type="button"
                  className={cn(
                    "inline-flex h-8 items-center justify-center rounded-full border border-border/60 px-2.5 text-xs text-muted-foreground transition-colors hover:bg-muted",
                    feedback === "like" && "border-primary/40 bg-primary/10 text-primary",
                  )}
                  onClick={() => onFeedback?.(message.id, "like")}
                  disabled={!onFeedback || feedbackDisabled}
                  title="Hữu ích"
                >
                  <ThumbsUp className="h-3.5 w-3.5" />
                </button>
                <button
                  type="button"
                  className={cn(
                    "inline-flex h-8 items-center justify-center rounded-full border border-border/60 px-2.5 text-xs text-muted-foreground transition-colors hover:bg-muted",
                    feedback === "dislike" && "border-destructive/40 bg-destructive/10 text-destructive",
                  )}
                  onClick={() => onFeedback?.(message.id, "dislike")}
                  disabled={!onFeedback || feedbackDisabled}
                  title="Chưa hữu ích"
                >
                  <ThumbsDown className="h-3.5 w-3.5" />
                </button>
              </div>
            ) : null}
          </>
        )}
      </div>

      {isUser ? (
        <Avatar className="mt-0.5 h-8 w-8 shrink-0 ring-1 ring-border/40">
          <AvatarFallback className="bg-muted text-foreground">
            <UserRound className="h-4 w-4" />
          </AvatarFallback>
        </Avatar>
      ) : null}
    </div>
  );
}
