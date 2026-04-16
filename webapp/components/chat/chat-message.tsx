"use client";

import { useState, useMemo } from "react";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { FileText, ChevronDown, ChevronUp } from "lucide-react";
import { MarkdownRenderer } from "@/components/chat/markdown-renderer";
import type { ChatMessage } from "@/types/chat";

interface ChatMessageProps {
  message: ChatMessage;
}

interface ParsedContent {
  thinking: string | null;
  answer: string;
  isStreaming: boolean;
}

function parseMessageContent(content: string): ParsedContent {
  if (!content) {
    return { thinking: null, answer: "", isStreaming: false };
  }

  const thinkingMatches = [...content.matchAll(/<thinking>([\s\S]*?)<\/thinking>/g)];
  const lastThinkingMatch = thinkingMatches.length > 0 ? thinkingMatches[thinkingMatches.length - 1] : null;

  const finalMatches = [...content.matchAll(/<final>([\s\S]*?)<\/final>/g)];
  const lastFinalMatch = finalMatches.length > 0 ? finalMatches[finalMatches.length - 1] : null;

  // Both tags complete
  if (lastThinkingMatch && lastFinalMatch) {
    let thinkingText = lastThinkingMatch[1].trim();
    // Truncate leaked chain-of-thought in thinking
    if (thinkingText.length > 300) {
      const sentences = thinkingText.split(/[.!?\n]+/).filter((s) => s.trim().length > 10);
      thinkingText = sentences.slice(-2).join(". ").trim();
      if (thinkingText) thinkingText += ".";
    }
    return {
      thinking: thinkingText || null,
      answer: lastFinalMatch[1].trim(),
      isStreaming: false,
    };
  }

  // <thinking> closed, <final> streaming
  if (lastThinkingMatch && !lastFinalMatch) {
    const afterThinking = content.slice(lastThinkingMatch.index! + lastThinkingMatch[0].length);
    const finalOpenIdx = afterThinking.indexOf("<final>");
    if (finalOpenIdx >= 0) {
      return {
        thinking: null,
        answer: afterThinking.slice(finalOpenIdx + 7).trim(),
        isStreaming: true,
      };
    }
    return { thinking: null, answer: "", isStreaming: true };
  }

  // <thinking> opened but not closed — AI still in chain-of-thought
  if (content.includes("<thinking>") && !content.includes("</thinking>")) {
    return { thinking: null, answer: "", isStreaming: true };
  }

  // <final> opened but not closed (no thinking found)
  const lastFinalOpen = content.lastIndexOf("<final>");
  if (lastFinalOpen >= 0 && !lastFinalMatch) {
    return {
      thinking: null,
      answer: content.slice(lastFinalOpen + 7).trim(),
      isStreaming: true,
    };
  }

  // No tags — check if it's chain-of-thought garbage
  const looksLikeReasoning =
    content.includes("*   ") ||
    content.includes("* Constraint") ||
    content.includes("* Drafting") ||
    content.includes("* Self-Correction");

  if (looksLikeReasoning) {
    return { thinking: null, answer: "", isStreaming: true };
  }

  // Genuine no-tag content — show as-is
  return { thinking: null, answer: content.trim(), isStreaming: false };
}

export function ChatMessage({ message }: ChatMessageProps) {
  const [showCitations, setShowCitations] = useState(false);
  const [showThinking, setShowThinking] = useState(false);
  const isUser = message.role === "user";

  const { thinking, answer, isStreaming } = useMemo(
    () => parseMessageContent(message.content),
    [message.content],
  );

  const showLoading = !isUser && isStreaming && !answer;

  return (
    <div className={`flex gap-3 px-4 py-3 ${isUser ? "justify-end" : ""}`}>
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
            {/* Animated loading — chain-of-thought hidden */}
            {showLoading && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground rounded-2xl bg-muted px-4 py-3">
                <span className="flex gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-current animate-bounce [animation-delay:0ms]" />
                  <span className="w-1.5 h-1.5 rounded-full bg-current animate-bounce [animation-delay:150ms]" />
                  <span className="w-1.5 h-1.5 rounded-full bg-current animate-bounce [animation-delay:300ms]" />
                </span>
                Đang suy nghĩ...
              </div>
            )}

            {/* Thinking button — only after stream completes */}
            {!isStreaming && thinking && (
              <Button
                variant="ghost"
                size="sm"
                className="h-6 text-xs gap-1 text-muted-foreground"
                onClick={() => setShowThinking(!showThinking)}
              >
                {showThinking ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                Suy nghĩ
              </Button>
            )}
            {!isStreaming && thinking && showThinking && (
              <div className="rounded-lg border border-dashed bg-muted/30 p-3 text-xs text-muted-foreground">
                {thinking}
              </div>
            )}

            {/* Answer — always render with Markdown (streaming or not) */}
            {answer && (
              <div className="rounded-2xl bg-muted px-4 py-2.5">
                <MarkdownRenderer content={answer} />
              </div>
            )}

            {/* Citations — only after stream completes */}
            {message.citations && message.citations.length > 0 && !isStreaming && (
              <div>
                <Button variant="ghost" size="sm" className="h-6 text-xs gap-1" onClick={() => setShowCitations(!showCitations)}>
                  <FileText className="h-3 w-3" />
                  {message.citations.length} nguồn
                  {showCitations ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                </Button>
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
          <AvatarFallback className="text-xs">You</AvatarFallback>
        </Avatar>
      )}
    </div>
  );
}
