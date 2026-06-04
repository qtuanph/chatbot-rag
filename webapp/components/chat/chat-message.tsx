"use client";

import { Bot, Coins, FileText, UserRound } from "lucide-react";

import { MarkdownRenderer } from "@/components/chat/markdown-renderer";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { formatNumber, formatVnd } from "@/lib/format";
import type { ChatUsage } from "@/types/api";
import type { ChatMessage } from "@/types/chat";

interface ChatMessageProps {
  message: ChatMessage;
  isStreaming?: boolean;
  isThinking?: boolean;
  usage?: ChatUsage | null;
}

export function ChatMessage({ message, isStreaming = false, isThinking = false, usage }: ChatMessageProps) {
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
    <div className={`flex gap-3 px-4 py-4 ${isUser ? "justify-end" : ""}`}>
      {!isUser ? (
        <Avatar className="mt-1 h-9 w-9 shrink-0 ring-1 ring-border/60">
          <AvatarFallback className="bg-primary/10 text-primary">
            <Bot className="h-4 w-4" />
          </AvatarFallback>
        </Avatar>
      ) : null}

      <div className={`max-w-[92%] space-y-3 sm:max-w-[80%] ${isUser ? "items-end" : ""}`}>
        {isUser ? (
          <>
            <div className="flex items-center justify-end gap-2">
              <div className="text-xs font-medium text-muted-foreground">Bạn</div>
            </div>
            <div className="whitespace-pre-wrap rounded-[24px] rounded-tr-md bg-primary px-4 py-3 text-sm leading-7 text-primary-foreground shadow-sm">
              {message.content}
            </div>
          </>
        ) : (
          <>
            {showLoading ? (
              <div className="rounded-[24px] rounded-tl-md border border-border/60 bg-card px-4 py-3 text-sm text-muted-foreground shadow-sm">
                Đang phân tích tài liệu và dựng ngữ cảnh...
              </div>
            ) : null}

            {message.content ? (
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <div className="text-xs font-semibold text-foreground/90">Trợ lý AI</div>
                  {isStreaming ? (
                    <Badge variant="outline" className="rounded-full border-primary/30 bg-primary/5 text-[11px] text-primary">
                      Đang trả lời
                    </Badge>
                  ) : null}
                </div>
                <div
                  className={
                    isStreaming
                      ? "rounded-[24px] rounded-tl-md border border-border/60 bg-card px-4 py-3 shadow-sm streaming-active"
                      : "rounded-[24px] rounded-tl-md border border-border/60 bg-card px-4 py-3 shadow-sm"
                  }
                >
                  <MarkdownRenderer content={message.content} showCursor={isStreaming} />
                </div>
              </div>
            ) : null}

            {!!citations.length && !isStreaming ? (
              <div className="space-y-3 rounded-2xl border border-border/70 bg-background/95 p-4 shadow-sm">
                <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  <FileText className="h-3.5 w-3.5" />
                  Tài liệu tham khảo
                </div>
                <div className="grid gap-2">
                  {visibleCitations.map((citation, index) => (
                    <div
                      key={`${citation.document_id}-${citation.section_id}-${index}`}
                      className="rounded-xl border border-border/60 bg-muted/30 p-3 text-xs"
                    >
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="rounded-full">
                          {index + 1}
                        </Badge>
                        <span className="font-medium">{citation.file_name || citation.title}</span>
                      </div>
                      <div className="mt-1.5 text-muted-foreground">
                        {citation.heading || citation.title}
                        {citation.page_range ? ` • trang ${citation.page_range}` : ""}
                      </div>
                    </div>
                  ))}
                  {hiddenCitationCount > 0 ? (
                    <div className="text-xs text-muted-foreground">
                      +{hiddenCitationCount} tài liệu khác đã được dùng trong câu trả lời này
                    </div>
                  ) : null}
                </div>
              </div>
            ) : null}

            {usage && !isStreaming ? (
              <div className="space-y-3 rounded-2xl border border-border/70 bg-background/95 p-4 shadow-sm">
                <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  <Coins className="h-3.5 w-3.5" />
                  Thống kê lượt trả lời
                </div>
                <div className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
                  <div>
                    <div className="text-muted-foreground">Prompt</div>
                    <div className="font-medium">{formatNumber(usage.prompt_tokens)}</div>
                  </div>
                  <div>
                    <div className="text-muted-foreground">Completion</div>
                    <div className="font-medium">{formatNumber(usage.completion_tokens)}</div>
                  </div>
                  <div>
                    <div className="text-muted-foreground">Tổng token</div>
                    <div className="font-medium">{formatNumber(usage.total_tokens)}</div>
                  </div>
                  <div>
                    <div className="text-muted-foreground">Chi phí</div>
                    <div className="font-medium">{formatVnd(usage.cost_vnd_rounded)}</div>
                  </div>
                  <div>
                    <div className="text-muted-foreground">Model</div>
                    <div className="font-medium">{usage.model || "chatbot-rag"}</div>
                  </div>
                  <div>
                    <div className="text-muted-foreground">Đơn vị</div>
                    <div className="font-medium">{usage.currency_code}</div>
                  </div>
                  <div className="col-span-2">
                    <div className="text-muted-foreground">Thông tin thêm</div>
                    <div className="font-medium">
                      Prompt {formatNumber(usage.prompt_tokens)} • Completion {formatNumber(usage.completion_tokens)}
                    </div>
                  </div>
                </div>
              </div>
            ) : null}
          </>
        )}
      </div>

      {isUser ? (
        <Avatar className="mt-1 h-9 w-9 shrink-0 ring-1 ring-border/60">
          <AvatarFallback className="bg-muted text-foreground">
            <UserRound className="h-4 w-4" />
          </AvatarFallback>
        </Avatar>
      ) : null}
    </div>
  );
}
