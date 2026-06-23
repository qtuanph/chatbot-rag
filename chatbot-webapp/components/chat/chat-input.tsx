"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowUp, Brain, StopCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
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
    <div className="px-4">
      <div className="mx-auto w-full max-w-3xl">
        <div
          className={cn(
            "group/chat-input relative flex w-full flex-col rounded-3xl border border-white/10 bg-background/60 shadow-[0_8px_40px_-12px_rgba(0,0,0,0.1)] backdrop-blur-2xl transition-all duration-300 dark:border-white/5",
            "focus-within:border-primary/30 focus-within:bg-background/80 focus-within:shadow-[0_8px_40px_-12px_rgba(var(--primary),0.15)]",
            focused && "border-primary/30",
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
              className="min-h-[56px] resize-none border-0 bg-transparent px-5 pt-4 pb-2 text-[15px] leading-relaxed shadow-none focus-visible:ring-0 placeholder:text-muted-foreground/60"
              disabled={disabled && !streaming}
              rows={1}
            />

          <TooltipProvider>
            <div className="flex items-center justify-between gap-2 px-2 pb-2">
              <div className="flex items-center gap-1.5">
                {onThinkingToggle ? (
                  <Tooltip>
                    <TooltipTrigger
                      render={
                        <Button
                          type="button"
                          size="sm"
                          variant={thinkingMode ? "secondary" : "ghost"}
                          onClick={onThinkingToggle}
                          className={cn("h-8 rounded-full px-3 text-xs font-medium", thinkingMode ? "text-primary" : "text-muted-foreground")}
                        >
                          <Brain data-icon="inline-start" className={cn(thinkingMode && "animate-pulse")} />
                          <span>Suy luận sâu</span>
                        </Button>
                      }
                    />
                    <TooltipContent>{thinkingMode ? "Đang bật chế độ suy luận sâu" : "Bật chế độ suy luận sâu"}</TooltipContent>
                  </Tooltip>
                ) : null}
              </div>

              <div className="flex items-center gap-1.5">
                {streaming ? (
                  <Tooltip>
                    <TooltipTrigger
                      render={
                        <Button
                          type="button"
                          size="icon"
                          variant="ghost"
                          onClick={onStop}
                          className="rounded-full text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                        >
                          <StopCircle />
                        </Button>
                      }
                    />
                    <TooltipContent>Dừng phản hồi</TooltipContent>
                  </Tooltip>
                ) : null}

                <Tooltip>
                  <TooltipTrigger
                    render={
                      <Button
                        type="button"
                        size="icon"
                        onClick={handleSubmit}
                        disabled={!canSend}
                        aria-label="Gửi tin nhắn"
                        className={cn(
                          "rounded-full transition-all duration-200",
                          canSend ? "shadow-md" : "bg-muted text-muted-foreground/60 shadow-none",
                        )}
                      >
                        <ArrowUp className={cn("transition-transform duration-300", value.trim() && "scale-110")} />
                      </Button>
                    }
                  />
                  <TooltipContent>Gửi (Enter)</TooltipContent>
                </Tooltip>
              </div>
            </div>
          </TooltipProvider>
        </div>


      </div>
    </div>
  );
}
