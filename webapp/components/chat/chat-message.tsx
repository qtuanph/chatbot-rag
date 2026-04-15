"use client";

import { useState, useMemo } from "react";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ChevronDown, ChevronUp, FileText, Brain } from "lucide-react";
import { MarkdownRenderer } from "@/components/chat/markdown-renderer";
import type { ChatMessage } from "@/types/chat";

interface ChatMessageProps {
  message: ChatMessage;
}

function parseThinking(content: string): { thinking: string | null; answer: string } {
  // Match <thinking>...</thinking> tags (may span multiple lines)
  const match = content.match(/<thinking>([\s\S]*?)<\/thinking>/);
  if (match) {
    const thinking = match[1].trim();
    const answer = content.slice(match[0].length).trim();
    return { thinking, answer };
  }

  // Handle incomplete thinking (still streaming, tag not closed yet)
  const openMatch = content.match(/<thinking>([\s\S]*)$/);
  if (openMatch && !content.includes("</thinking>")) {
    return { thinking: openMatch[1].trim(), answer: "" };
  }

  return { thinking: null, answer: content };
}

export function ChatMessage({ message }: ChatMessageProps) {
  const [showCitations, setShowCitations] = useState(false);
  const [showThinking, setShowThinking] = useState(false);
  const isUser = message.role === "user";

  const { thinking, answer } = useMemo(
    () => parseThinking(message.content),
    [message.content],
  );

  return (
    <div className={`flex gap-3 px-4 py-3 ${isUser ? "justify-end" : ""}`}>
      {!isUser && (
        <Avatar className="h-8 w-8 shrink-0">
          <AvatarFallback className="text-xs bg-primary text-primary-foreground">
            AI
          </AvatarFallback>
        </Avatar>
      )}

      <div className={`max-w-[80%] space-y-2 ${isUser ? "items-end" : ""}`}>
        {/* User message */}
        {isUser && (
          <div className="rounded-2xl px-4 py-2.5 text-sm leading-relaxed bg-primary text-primary-foreground whitespace-pre-wrap">
            {message.content}
          </div>
        )}

        {/* Assistant message */}
        {!isUser && (
          <>
            {/* Thinking section */}
            {thinking && (
              <div>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 text-xs gap-1 text-muted-foreground"
                  onClick={() => setShowThinking(!showThinking)}
                >
                  <Brain className="h-3 w-3" />
                  Suy nghĩ
                  {showThinking ? (
                    <ChevronUp className="h-3 w-3" />
                  ) : (
                    <ChevronDown className="h-3 w-3" />
                  )}
                </Button>
                {showThinking && (
                  <div className="mt-1 rounded-lg border border-dashed bg-muted/30 p-3 text-xs text-muted-foreground whitespace-pre-wrap">
                    {thinking}
                  </div>
                )}
              </div>
            )}

            {/* Answer section */}
            {answer && (
              <div className="rounded-2xl bg-muted px-4 py-2.5">
                <MarkdownRenderer content={answer} />
              </div>
            )}

            {/* Still streaming, no answer yet */}
            {!answer && !thinking && !message.content && (
              <div className="rounded-2xl bg-muted px-4 py-2.5 text-sm text-muted-foreground">
                ...
              </div>
            )}

            {/* Citations */}
            {message.citations && message.citations.length > 0 && (
              <div>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 text-xs gap-1"
                  onClick={() => setShowCitations(!showCitations)}
                >
                  <FileText className="h-3 w-3" />
                  {message.citations.length} nguồn
                  {showCitations ? (
                    <ChevronUp className="h-3 w-3" />
                  ) : (
                    <ChevronDown className="h-3 w-3" />
                  )}
                </Button>

                {showCitations && (
                  <div className="mt-1 space-y-1">
                    {message.citations.map((c, i) => (
                      <div
                        key={i}
                        className="text-xs p-2 rounded bg-muted/50 border flex items-start gap-2"
                      >
                        <Badge variant="outline" className="shrink-0 text-[10px]">
                          {i + 1}
                        </Badge>
                        <div>
                          <span className="font-medium">{c.title}</span>
                          {c.heading && (
                            <span className="text-muted-foreground">
                              {" "}
                              &gt; {c.heading}
                            </span>
                          )}
                          {c.page_range && (
                            <span className="text-muted-foreground">
                              {" "}
                              (trang {c.page_range})
                            </span>
                          )}
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
          <AvatarFallback className="text-xs">You</AvatarFallback>
        </Avatar>
      )}
    </div>
  );
}
