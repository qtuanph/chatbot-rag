"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { useSession } from "next-auth/react";

import { Button } from "@/components/ui/button";
import { Plus, ChevronUp } from "lucide-react";
import { ChatInput } from "@/components/chat/chat-input";
import { ChatMessage } from "@/components/chat/chat-message";
import { toast } from "sonner";
import { API_BASE, chatApi } from "@/lib/api-client";
import type { ChatMessage as ChatMessageType } from "@/types/chat";
import type { Citation, ChatStreamEvent } from "@/types/api";

const PAGE_SIZE = 20;

export function ChatPanel() {
  const { data: session } = useSession();
  const [messages, setMessages] = useState<ChatMessageType[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [restoring, setRestoring] = useState(true);
  const [hasMore, setHasMore] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const scrollHeightRef = useRef(0);

  // Restore latest session messages from DB on mount (last PAGE_SIZE messages)
  useEffect(() => {
    if (!session) {
      const timer = setTimeout(() => {
        setRestoring(false);
      }, 0);
      return () => clearTimeout(timer);
    }

    let cancelled = false;

    (async () => {
      try {
        const sessions = await chatApi.getSessions();
        if (cancelled || sessions.length === 0) {
          setRestoring(false);
          return;
        }

        // Pick most recent session
        const latest = sessions[0];
        const result = await chatApi.getMessages(latest.session_id, PAGE_SIZE, 0);

        if (cancelled || result.messages.length === 0) {
          setRestoring(false);
          return;
        }

        setSessionId(latest.session_id);
        setHasMore(result.has_more);
        setMessages(
          result.messages.map((m) => ({
            id: m.id,
            role: m.role,
            content: m.content,
            citations: m.citations?.length ? m.citations : undefined,
          })),
        );
      } catch {
        // Silent fail — just start fresh
      } finally {
        if (!cancelled) setRestoring(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [session]);

  // Auto-scroll to bottom (only for new messages, not for "load more")
  useEffect(() => {
    if (scrollRef.current && !loadingMore) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, streaming, loadingMore]);

  const handleLoadMore = useCallback(async () => {
    if (!sessionId || loadingMore) return;

    // Save current scroll height to restore position after prepending
    if (scrollRef.current) {
      scrollHeightRef.current = scrollRef.current.scrollHeight;
    }
    setLoadingMore(true);

    try {
      const result = await chatApi.getMessages(sessionId, PAGE_SIZE, messages.length);
      const olderMessages = result.messages.map((m) => ({
        id: m.id,
        role: m.role,
        content: m.content,
        citations: m.citations?.length ? m.citations : undefined,
      }));

      // Prepend older messages
      setMessages((prev) => [...olderMessages, ...prev]);
      setHasMore(result.has_more);

      // Restore scroll position (keep user at same message)
      requestAnimationFrame(() => {
        if (scrollRef.current) {
          const newScrollHeight = scrollRef.current.scrollHeight;
          scrollRef.current.scrollTop = newScrollHeight - scrollHeightRef.current;
        }
      });
    } catch {
      toast.error("Lỗi tải thêm tin nhắn.");
    } finally {
      setLoadingMore(false);
    }
  }, [sessionId, messages.length, loadingMore]);

  const handleNewChat = useCallback(() => {
    setMessages([]);
    setSessionId(null);
    setHasMore(false);
  }, []);

  const handleSend = useCallback(
    async (query: string) => {
      if (!session || streaming) return;

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
        // SSE goes through Next.js proxy — no Bearer token exposed to browser
        const res = await fetch(`${API_BASE}/chat/stream`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
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
    [session, sessionId, streaming],
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

      {/* Messages — plain div for reliable scrolling */}
      <div className="flex-1 min-h-0 overflow-y-auto" ref={scrollRef}>
        {restoring ? (
          <div className="flex items-center justify-center h-full">
            <p className="text-sm text-muted-foreground">Đang tải lịch sử chat...</p>
          </div>
        ) : messages.length === 0 ? (
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
            {/* Load more button — only show if there are older messages */}
            {hasMore && (
              <div className="flex justify-center py-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleLoadMore}
                  disabled={loadingMore}
                  className="gap-1 text-muted-foreground"
                >
                  <ChevronUp className="h-4 w-4" />
                  {loadingMore ? "Đang tải..." : "Xem tin nhắn cũ hơn"}
                </Button>
              </div>
            )}
            {messages.map((msg, index) => (
              <ChatMessage
                key={msg.id}
                message={msg}
                isStreaming={streaming && index === messages.length - 1 && msg.role === "assistant"}
              />
            ))}
          </div>
        )}
      </div>

      {/* Input */}
      <ChatInput onSend={handleSend} disabled={streaming || restoring} />
    </div>
  );
}
