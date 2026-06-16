"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowUp, Brain, StopCircle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
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
    <div className="bg-background/95 px-4 pt-3 pb-4 backdrop-blur supports-[backdrop-filter]:bg-background/80">
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
                          canSend ? "shadow-[0_4px_14px_-4px_rgba(1,56,123,0.5)]" : "bg-muted text-muted-foreground/60 shadow-none",
                        )}
                      >
                        <ArrowUp />
                      </Button>
                    }
                  />
                  <TooltipContent>Gửi (Enter)</TooltipContent>
                </Tooltip>
              </div>
            </div>
          </TooltipProvider>
        </div>

        <div className="mt-2 flex items-center justify-center gap-2 px-1 text-[11px] text-muted-foreground/80">
          <Badge variant="outline" className="rounded-full px-2 py-0.5 font-normal">
            Enter để gửi
          </Badge>
          <Separator orientation="vertical" className="h-3" />
          <Badge variant="outline" className="rounded-full px-2 py-0.5 font-normal">
            Shift + Enter để xuống dòng
          </Badge>
          <Separator orientation="vertical" className="h-3" />
          <Badge variant="secondary" className="rounded-full px-2 py-0.5 font-normal">
            Stateless
          </Badge>
        </div>
      </div>
    </div>
  );
}
