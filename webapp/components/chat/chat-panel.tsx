"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { useSession } from "next-auth/react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { Plus } from "lucide-react";
import { ChatInput } from "@/components/chat/chat-input";
import { ChatMessage } from "@/components/chat/chat-message";
import { toast } from "sonner";
import { API_BASE } from "@/lib/api-client";
import type { ChatMessage as ChatMessageType } from "@/types/chat";
import type { Citation, ChatStreamEvent } from "@/types/api";

export function ChatPanel() {
  const { data: session } = useSession();
  const [messages, setMessages] = useState<ChatMessageType[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, streaming]);

  const handleNewChat = useCallback(() => {
    setMessages([]);
    setSessionId(null);
  }, []);

  const handleSend = useCallback(
    async (query: string) => {
      if (!session?.accessToken || streaming) return;

      const userMsg: ChatMessageType = {
        id: crypto.randomUUID(),
        role: "user",
        content: query,
      };
      const assistantId = crypto.randomUUID();
      setMessages((prev) => [
        ...prev,
        userMsg,
        { id: assistantId, role: "assistant", content: "" },
      ]);
      setStreaming(true);

      try {
        const res = await fetch(`${API_BASE}/chat/stream`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${session.accessToken}`,
          },
          body: JSON.stringify({
            query,
            session_id: sessionId,
          }),
        });

        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`);
        }

        const reader = res.body?.getReader();
        if (!reader) throw new Error("No response body");

        const decoder = new TextDecoder();
        let fullText = "";
        let citations: Citation[] = [];
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            const jsonStr = line.slice(6).trim();
            if (!jsonStr) continue;

            try {
              const event: ChatStreamEvent = JSON.parse(jsonStr);

              if (event.done) {
                if ("error" in event && event.error) {
                  setMessages((prev) =>
                    prev.map((m) =>
                      m.id === assistantId
                        ? { ...m, content: event.error! }
                        : m,
                    ),
                  );
                } else {
                  if ("session_id" in event && event.session_id) {
                    setSessionId(event.session_id);
                  }
                  if ("citations" in event && event.citations) {
                    citations = event.citations;
                  }
                  setMessages((prev) =>
                    prev.map((m) =>
                      m.id === assistantId
                        ? { ...m, content: fullText, citations }
                        : m,
                    ),
                  );
                }
              } else {
                fullText += event.chunk;
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantId
                      ? { ...m, content: fullText }
                      : m,
                  ),
                );
              }
            } catch {
              // Skip malformed JSON
            }
          }
        }
      } catch {
        toast.error("Lỗi kết nối. Vui lòng thử lại.");
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? { ...m, content: "Lỗi khi gửi tin nhắn. Vui lòng thử lại." }
              : m,
          ),
        );
      } finally {
        setStreaming(false);
      }
    },
    [session?.accessToken, sessionId, streaming],
  );

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between border-b px-4 py-2">
        <h2 className="text-sm font-medium text-muted-foreground">
          {sessionId ? "Phiên chat" : "Chat mới"}
        </h2>
        <Button
          variant="ghost"
          size="sm"
          onClick={handleNewChat}
          disabled={streaming}
          className="gap-1"
        >
          <Plus className="h-4 w-4" />
          Chat mới
        </Button>
      </div>

      {/* Messages */}
      <ScrollArea className="flex-1" ref={scrollRef}>
        {messages.length === 0 ? (
          <div className="flex items-center justify-center h-full text-center p-8">
            <div className="space-y-2">
              <p className="text-2xl font-semibold">Xin chào!</p>
              <p className="text-muted-foreground max-w-md">
                Hỏi tôi bất kỳ điều gì về tài liệu đã tải lên hệ thống.
              </p>
            </div>
          </div>
        ) : (
          <div className="py-4 space-y-1">
            {messages.map((msg, index) => (
              <ChatMessage
                key={msg.id}
                message={msg}
                isStreaming={streaming && index === messages.length - 1 && msg.role === "assistant"}
              />
            ))}
          </div>
        )}
      </ScrollArea>

      {/* Input */}
      <ChatInput onSend={handleSend} disabled={streaming} />
    </div>
  );
}
