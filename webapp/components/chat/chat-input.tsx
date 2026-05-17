"use client";

import { useState, useRef, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { SendHorizontal, Square, Brain } from "lucide-react";

interface ChatInputProps {
  onSend: (message: string, thinkingMode?: boolean) => void;
  onStop?: () => void;
  disabled?: boolean;
  streaming?: boolean;
  thinkingMode?: boolean;
  onThinkingToggle?: () => void;
}

export function ChatInput({ onSend, onStop, disabled, streaming, thinkingMode, onThinkingToggle }: ChatInputProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = useCallback(() => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed, thinkingMode);
    setValue("");
    textareaRef.current?.focus();
  }, [value, disabled, onSend, thinkingMode]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSubmit();
      }
    },
    [handleSubmit],
  );

  const isDisabled = disabled && !streaming;

  return (
    <div className="flex gap-2 p-4 border-t bg-background">
      {onThinkingToggle && (
        <Button
          size="icon"
          variant={thinkingMode ? "default" : "outline"}
          onClick={onThinkingToggle}
          title={thinkingMode ? "Thinking: BẬT" : "Thinking: TẮT"}
          className="shrink-0"
        >
          <Brain className={`h-4 w-4 ${thinkingMode ? "animate-pulse" : ""}`} />
        </Button>
      )}
      <Textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Nhập câu hỏi về tài liệu..."
        className="min-h-[44px] max-h-[200px] resize-none"
        rows={1}
        disabled={isDisabled}
      />
      {streaming ? (
        <Button
          size="icon"
          variant="destructive"
          onClick={onStop}
          title="Dừng phản hồi"
        >
          <Square className="h-4 w-4" />
        </Button>
      ) : (
        <Button
          size="icon"
          onClick={handleSubmit}
          disabled={!value.trim() || isDisabled}
        >
          <SendHorizontal className="h-4 w-4" />
        </Button>
      )}
    </div>
  );
}
