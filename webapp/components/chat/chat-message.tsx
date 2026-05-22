"use client";

import { useState } from "react";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { FileText, ThumbsUp, ThumbsDown, Zap, Clock, Hash } from "lucide-react";
import { MarkdownRenderer } from "@/components/chat/markdown-renderer";
import { chatApi } from "@/lib/api-client";
import { toast } from "sonner";
import type { ChatMessage } from "@/types/chat";

interface ChatMessageProps {
  message: ChatMessage;
  isStreaming?: boolean;
  isThinking?: boolean;
  stats?: {
    total_ms: number;
    ttft_ms: number | null;
    prompt_tokens?: number;
    completion_tokens?: number;
    total_tokens?: number;
    estimated_cost_usd?: number;
  } | null;
}

export function ChatMessage({ message, isStreaming = false, isThinking = false, stats }: ChatMessageProps) {
  const [showCitations, setShowCitations] = useState(false);
  const [localFeedback, setLocalFeedback] = useState<number>(message.feedback || 0);

  const handleFeedback = async (value: number) => {
    const newValue = localFeedback === value ? 0 : value;
    setLocalFeedback(newValue);
    try {
      await chatApi.setMessageFeedback(message.id, newValue);
    } catch {
      toast.error("Không thể lưu đánh giá.");
      setLocalFeedback(message.feedback || 0);
    }
  };

  const isUser = message.role === "user";
  const isLoading = !isUser && (isStreaming && !message.content) || isThinking;
  const isStreamingContent = !isUser && isStreaming && message.content;

  return (
    <div className={`flex gap-3 px-4 py-3 ${isUser ? "justify-end" : ""}`}>
      {!isUser && (
        <Avatar className="h-8 w-8 shrink-0">
          <AvatarFallback className="text-xs bg-primary text-primary-foreground">AI</AvatarFallback>
        </Avatar>
      )}

      <div className={`max-w-[90%] sm:max-w-[80%] space-y-2 ${isUser ? "items-end" : ""}`}>
        {isUser && (
          <div className="rounded-2xl px-4 py-2.5 text-sm leading-relaxed bg-primary text-primary-foreground whitespace-pre-wrap">
            {message.content}
          </div>
        )}

        {!isUser && (
          <>
            {isLoading && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground rounded-2xl bg-muted px-4 py-3">
                <span className="flex gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-current animate-bounce [animation-delay:0ms]" />
                  <span className="w-1.5 h-1.5 rounded-full bg-current animate-bounce [animation-delay:150ms]" />
                  <span className="w-1.5 h-1.5 rounded-full bg-current animate-bounce [animation-delay:300ms]" />
                </span>
                Đang tìm kiếm tài liệu...
              </div>
            )}

            {message.content && (
              <div className={`rounded-2xl bg-muted px-4 py-2.5 ${isStreamingContent ? "streaming-active" : ""}`}>
                {isStreamingContent ? (
                  <div className="text-sm leading-relaxed whitespace-pre-wrap font-sans">
                    {message.content}
                    <span className="inline-block w-0.5 h-4 bg-foreground/70 ml-0.5 align-text-bottom animate-pulse" />
                  </div>
                ) : (
                  <MarkdownRenderer content={message.content} />
                )}
              </div>
            )}

            {message.citations && message.citations.length > 0 && !isStreaming && (
              <div className="mt-2">
                <Button variant="ghost" size="sm" className="h-6 text-xs gap-1" onClick={() => setShowCitations(!showCitations)}>
                  <FileText className="h-3 w-3" />
                  {message.citations.length} nguồn
                </Button>

                {showCitations && (
                  <div className="mt-1 flex gap-3">
                    {/* Citations */}
                    <div className="flex-1 space-y-1">
                      {message.citations.map((c, i) => (
                        <div key={i} className="text-xs p-2 rounded bg-muted/50 border flex items-start gap-2">
                          <Badge variant="outline" className="shrink-0 text-[10px]">{i + 1}</Badge>
                          <div>
                            <span className="font-medium">{c.title}</span>
                            {c.heading && <span className="text-muted-foreground">{" > "}{c.heading}</span>}
                            {c.page_range && <span className="text-muted-foreground"> (trang {c.page_range})</span>}
                          </div>
                        </div>
                      ))}
                    </div>

                    {/* Stats */}
                    {stats && (
                      <div className="shrink-0 w-48 space-y-1.5 text-xs p-3 rounded-lg bg-muted/30 border">
                        <div className="flex items-center gap-1.5 text-muted-foreground">
                          <Zap className="h-3 w-3" />
                          <span className="font-medium">AI Stats</span>
                        </div>
                        <div className="space-y-1">
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">Time</span>
                            <span className="font-medium">{(stats.total_ms / 1000).toFixed(2)}s</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">TTFT</span>
                            <span className="font-medium">{(stats.ttft_ms != null ? (stats.ttft_ms / 1000).toFixed(2) : '0')}s</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">In</span>
                            <span className="font-medium text-orange-500">{(stats.prompt_tokens ?? 0).toLocaleString()}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">Out</span>
                            <span className="font-medium text-emerald-500">{(stats.completion_tokens ?? 0).toLocaleString()}</span>
                          </div>
                          <div className="flex justify-between border-t pt-1 mt-1">
                            <span className="text-muted-foreground">Total</span>
                            <span className="font-medium">{(stats.total_tokens ?? 0).toLocaleString()}</span>
                          </div>
                          {(stats.estimated_cost_usd ?? 0) > 0 && (
                            <div className="flex justify-between">
                              <span className="text-muted-foreground">Cost</span>
                              <span className="font-medium text-green-600">${(stats.estimated_cost_usd ?? 0).toFixed(4)}</span>
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {!isUser && !isStreaming && message.content && (
              <div className="flex items-center gap-2 mt-2 pt-2 border-t border-border/30">
                <span className="text-xs text-muted-foreground">Câu trả lời này:</span>
                <Button
                  variant="ghost"
                  size="sm"
                  className={`h-7 px-2 gap-1 text-xs ${
                    localFeedback === 1
                      ? "text-green-600 bg-green-500/10"
                      : "text-muted-foreground hover:text-green-600"
                  }`}
                  onClick={() => handleFeedback(1)}
                >
                  <ThumbsUp className="h-3.5 w-3.5" />
                  <span>Hữu ích</span>
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className={`h-7 px-2 gap-1 text-xs ${
                    localFeedback === -1
                      ? "text-red-600 bg-red-500/10"
                      : "text-muted-foreground hover:text-red-600"
                  }`}
                  onClick={() => handleFeedback(-1)}
                >
                  <ThumbsDown className="h-3.5 w-3.5" />
                  <span>Không hữu ích</span>
                </Button>
                {localFeedback !== 0 && (
                  <span className="text-xs text-muted-foreground animate-in fade-in">
                    Đã ghi nhận!
                  </span>
                )}
              </div>
            )}
          </>
        )}
      </div>

      {isUser && (
        <Avatar className="h-8 w-8 shrink-0">
          <AvatarFallback className="text-xs">Bạn</AvatarFallback>
        </Avatar>
      )}
    </div>
  );
}
