"use client";

import { useState } from "react";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { FileText, ThumbsUp, ThumbsDown } from "lucide-react";
import { MarkdownRenderer } from "@/components/chat/markdown-renderer";
import { chatApi } from "@/lib/api-client";
import { toast } from "sonner";
import type { ChatMessage } from "@/types/chat";

interface ChatMessageProps {
  message: ChatMessage;
  isStreaming?: boolean;
}

export function ChatMessage({ message, isStreaming = false }: ChatMessageProps) {
  const [showCitations, setShowCitations] = useState(false);
  const [localFeedback, setLocalFeedback] = useState<number>(message.feedback || 0);

  const handleFeedback = async (value: number) => {
    // If clicking same feedback again, reset to 0
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
  const isLoading = !isUser && isStreaming && !message.content;

  return (
    <div className={`flex gap-3 px-4 py-3 group ${isUser ? "justify-end" : ""}`}>
      {!isUser && (
        <Avatar className="h-8 w-8 shrink-0">
          <AvatarFallback className="text-xs bg-primary text-primary-foreground">AI</AvatarFallback>
        </Avatar>
      )}

      <div className={`max-w-[80%] space-y-2 ${isUser ? "items-end" : ""}`}>
        {isUser && (
          <div className="rounded-2xl px-4 py-2.5 text-sm leading-relaxed bg-primary text-primary-foreground whitespace-pre-wrap">
            {message.content}
          </div>
        )}

        {!isUser && (
          <>
            {/* Loading indicator — waiting for first chunk */}
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

            {/* Answer — stream live with markdown */}
            {message.content && (
              <div className={`rounded-2xl bg-muted px-4 py-2.5 ${isStreaming ? "streaming-active" : ""}`}>
                <MarkdownRenderer content={message.content} />
                {isStreaming && (
                  <span className="inline-block w-1.5 h-4 bg-foreground/70 ml-0.5 align-text-bottom [animation:cursor-blink_1s_step-end_infinite]" />
                )}
              </div>
            )}

            {/* Citations — only after stream completes */}
            {message.citations && message.citations.length > 0 && !isStreaming && (
              <div>
                <div className="flex items-center gap-2">
                  <Button variant="ghost" size="sm" className="h-6 text-xs gap-1" onClick={() => setShowCitations(!showCitations)}>
                    <FileText className="h-3 w-3" />
                    {message.citations.length} nguồn
                  </Button>

                  <div className="flex items-center gap-0.5 ml-auto opacity-0 group-hover:opacity-100 transition-opacity">
                    <Button
                      variant="ghost"
                      size="icon"
                      className={`h-7 w-7 ${localFeedback === 1 ? "text-green-500 bg-green-500/10" : "text-muted-foreground"}`}
                      onClick={() => handleFeedback(1)}
                    >
                      <ThumbsUp className="h-3.5 w-3.5" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className={`h-7 w-7 ${localFeedback === -1 ? "text-red-500 bg-red-500/10" : "text-muted-foreground"}`}
                      onClick={() => handleFeedback(-1)}
                    >
                      <ThumbsDown className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </div>

                {showCitations && (
                  <div className="mt-1 space-y-1">
                    {message.citations.map((c, i) => (
                      <div key={i} className="text-xs p-2 rounded bg-muted/50 border flex items-start gap-2">
                        <Badge variant="outline" className="shrink-0 text-[10px]">{i + 1}</Badge>
                        <div>
                          <span className="font-medium">{c.title}</span>
                          {c.heading && <span className="text-muted-foreground"> &gt; {c.heading}</span>}
                          {c.page_range && <span className="text-muted-foreground"> (trang {c.page_range})</span>}
                        </div>
                      </div>
                    ))}
                  </div>
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
