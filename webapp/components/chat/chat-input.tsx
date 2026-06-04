"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Brain, SendHorizontal, Sparkles, Square } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

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
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const resizeTextarea = useCallback(() => {
    if (!textareaRef.current) return;
    textareaRef.current.style.height = "0px";
    textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 220)}px`;
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
      if (textareaRef.current) {
        textareaRef.current.style.height = "0px";
      }
      textareaRef.current?.focus();
    });
  }, [disabled, onSend, thinkingMode, value]);

  return (
    <div className="border-t border-border/60 bg-background/95 px-4 py-4 backdrop-blur supports-[backdrop-filter]:bg-background/75">
      <div className="mx-auto w-full max-w-5xl">
        <div className="rounded-[28px] border border-border/70 bg-card/95 p-3 shadow-lg shadow-black/5">
          <div className="flex items-end gap-3">
            {onThinkingToggle ? (
              <Button
                size="icon"
                variant={thinkingMode ? "default" : "outline"}
                onClick={onThinkingToggle}
                className="h-11 w-11 shrink-0 rounded-2xl"
                title={thinkingMode ? "Đang bật chế độ suy luận sâu" : "Đang tắt chế độ suy luận sâu"}
              >
                <Brain className={`h-4 w-4 ${thinkingMode ? "animate-pulse" : ""}`} />
              </Button>
            ) : null}

            <div className="flex-1">
              <Textarea
                ref={textareaRef}
                value={value}
                onChange={(event) => setValue(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    handleSubmit();
                  }
                }}
                placeholder="Nhập câu hỏi về tài liệu, quy trình, hướng dẫn sử dụng..."
                className="min-h-[56px] resize-none border-0 bg-transparent px-1 py-2 text-sm leading-7 shadow-none focus-visible:ring-0"
                disabled={disabled && !streaming}
              />
              <div className="flex flex-col gap-2 px-1 pt-2 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <Sparkles className="h-3.5 w-3.5" />
                  <span>Enter để gửi • Shift + Enter để xuống dòng</span>
                </div>
                <div className="text-xs text-muted-foreground">
                  {streaming ? "AI đang trả lời..." : "Chat chỉ lưu trong phiên đang mở"}
                </div>
              </div>
            </div>

            {streaming ? (
              <Button size="icon" variant="destructive" onClick={onStop} className="h-11 w-11 shrink-0 rounded-2xl" title="Dừng phản hồi">
                <Square className="h-4 w-4" />
              </Button>
            ) : (
              <Button
                size="icon"
                onClick={handleSubmit}
                disabled={!value.trim() || disabled}
                className="h-11 w-11 shrink-0 rounded-2xl"
              >
                <SendHorizontal className="h-4 w-4" />
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
