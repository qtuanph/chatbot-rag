"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowUp, Brain, Square, StopCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

interface ChatInputProps {
  onSend: (message: string, thinkingMode?: boolean) => void;
  onStop?: () => void;
  disabled?: boolean;
  streaming?: boolean;
  thinkingMode?: boolean;
  onThinkingToggle?: () => void;
}

export function ChatInput({
  onSend,
  onStop,
  disabled,
  streaming,
  thinkingMode,
  onThinkingToggle,
}: ChatInputProps) {
  const [value, setValue] = useState("");
  const [focused, setFocused] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const resizeTextarea = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "0px";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, []);

  useEffect(() => {
    resizeTextarea();
  }, [resizeTextarea, value]);

  const handleSubmit = useCallback(() => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed, thinkingMode);
    setValue("");
    requestAnimationFrame(() => {
      const el = textareaRef.current;
      if (el) {
        el.style.height = "0px";
        el.focus();
      }
    });
  }, [disabled, onSend, thinkingMode, value]);

  const canSend = value.trim().length > 0 && !disabled;

  return (
    <div className="border-t border-border/60 bg-background/95 px-4 pt-3 pb-4 backdrop-blur supports-[backdrop-filter]:bg-background/80">
      <div className="mx-auto w-full max-w-3xl">
        <div
          className={cn(
            "group/chat-input relative flex w-full flex-col rounded-3xl border border-border/70 bg-card transition-all duration-200",
            "shadow-[0_2px_18px_-12px_rgba(1,56,123,0.18)] focus-within:border-primary/40 focus-within:shadow-[0_4px_24px_-10px_rgba(1,56,123,0.28)]",
            focused && "border-primary/40",
          )}
        >
          <Textarea
            ref={textareaRef}
            value={value}
            onChange={(event) => setValue(event.target.value)}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                handleSubmit();
              }
            }}
            placeholder="Hỏi điều gì đó..."
            className="min-h-[44px] resize-none border-0 bg-transparent px-4 pt-3 pb-1 text-[15px] leading-6 shadow-none focus-visible:ring-0"
            disabled={disabled && !streaming}
            rows={1}
          />

          <div className="flex items-center justify-between gap-2 px-2 pb-2">
            <div className="flex items-center gap-1.5">
              {onThinkingToggle ? (
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  onClick={onThinkingToggle}
                  className={cn(
                    "h-8 gap-1.5 rounded-full px-3 text-xs font-medium transition-colors",
                    thinkingMode
                      ? "bg-primary/10 text-primary hover:bg-primary/15"
                      : "text-muted-foreground hover:bg-muted hover:text-foreground",
                  )}
                  title={thinkingMode ? "Đang bật chế độ suy luận sâu" : "Bật chế độ suy luận sâu"}
                >
                  <Brain className={cn("h-3.5 w-3.5", thinkingMode && "animate-pulse")} />
                  <span>Suy luận sâu</span>
                </Button>
              ) : null}
            </div>

            <div className="flex items-center gap-1.5">
              {streaming ? (
                <Button
                  type="button"
                  size="icon"
                  variant="ghost"
                  onClick={onStop}
                  className="h-9 w-9 rounded-full text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                  title="Dừng phản hồi"
                >
                  <StopCircle className="h-4 w-4" />
                </Button>
              ) : null}

              <Button
                type="button"
                size="icon"
                onClick={handleSubmit}
                disabled={!canSend}
                aria-label="Gửi tin nhắn"
                title="Gửi (Enter)"
                className={cn(
                  "h-9 w-9 rounded-full transition-all duration-200",
                  canSend
                    ? "bg-primary text-primary-foreground hover:bg-primary/90 shadow-[0_4px_14px_-4px_rgba(1,56,123,0.5)]"
                    : "bg-muted text-muted-foreground/60 shadow-none",
                )}
              >
                {streaming ? <Square className="h-3.5 w-3.5 fill-current" /> : <ArrowUp className="h-4 w-4" />}
              </Button>
            </div>
          </div>
        </div>

        <div className="mt-2 flex items-center justify-center gap-2 px-1 text-[11px] text-muted-foreground/80">
          <span>Enter để gửi</span>
          <span className="size-1 rounded-full bg-muted-foreground/40" />
          <span>Shift + Enter để xuống dòng</span>
          <span className="size-1 rounded-full bg-muted-foreground/40" />
          <span className="inline-flex items-center gap-1">
            <span className="size-1.5 rounded-full bg-emerald-500/70" />
            Stateless
          </span>
        </div>
      </div>
    </div>
  );
}
