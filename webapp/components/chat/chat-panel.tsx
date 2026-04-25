"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { useSession } from "next-auth/react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ChevronUp, MessageSquare, History, Plus, Loader2 } from "lucide-react";
import { ChatInput } from "@/components/chat/chat-input";
import { ChatMessage } from "@/components/chat/chat-message";
import { toast } from "sonner";
import { API_BASE, chatApi } from "@/lib/api-client";
import type { ChatMessage as ChatMessageType } from "@/types/chat";
import type { ChatSession, Citation, ChatStreamEvent } from "@/types/api";

const PAGE_SIZE = 20;

function formatRelativeTime(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const min = Math.floor(diff / 60000);
  const hour = Math.floor(diff / 3600000);
  const day = Math.floor(diff / 86400000);

  if (min < 1) return "Vừa xong";
  if (min < 60) return `${min} phút trước`;
  if (hour < 24) return `${hour} giờ trước`;
  if (day < 7) return `${day} ngày trước`;
  return new Date(dateStr).toLocaleDateString("vi-VN");
}

interface ChatPanelProps {
  sessionId: string | null;
  justCreatedSessionId: string | null;
  sessions: ChatSession[];
  sessionsLoading: boolean;
  onNewChat: () => void;
  onSelectSession: (sessionId: string) => void;
  onRefreshSessions: () => void;
  onSessionCreated?: (sessionId: string) => void;
  onSessionUpdate?: (sessionId: string, updates: Partial<ChatSession>) => void;
}

export function ChatPanel({
  sessionId,
  justCreatedSessionId,
  sessions,
  sessionsLoading,
  onNewChat,
  onSelectSession,
  onRefreshSessions,
  onSessionCreated,
  onSessionUpdate,
}: ChatPanelProps) {
  const { data: session } = useSession();
  const [messages, setMessages] = useState<ChatMessageType[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [restoring, setRestoring] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const scrollHeightRef = useRef(0);
  const abortRef = useRef<AbortController | null>(null);
  const [lastStats, setLastStats] = useState<{
    total_ms: number;
    ttft_ms: number | null;
    chunks: number;
    chars: number;
    prompt_tokens?: number;
    completion_tokens?: number;
    total_tokens?: number;
    estimated_cost_usd?: number;
  } | null>(null);

  // Active session display
  const activeSession = sessions.find((s) => s.session_id === sessionId);

  // Load messages when sessionId changes (skip for just-created sessions)
  useEffect(() => {
    if (!session || !sessionId) {
      setMessages([]);
      setHasMore(false);
      return;
    }

    // Skip loading for locally-created sessions — they have no messages yet
    if (sessionId === justCreatedSessionId) return;

    let cancelled = false;
    setRestoring(true);

    (async () => {
      try {
        const result = await chatApi.getMessages(sessionId, PAGE_SIZE, 0);
        if (cancelled) return;

        if (result.messages.length === 0) {
          setMessages([]);
          setHasMore(false);
        } else {
          setHasMore(result.has_more);
          setMessages(
            result.messages.map((m) => ({
              id: m.id,
              role: m.role,
              content: m.content,
              citations: m.citations?.length ? m.citations : undefined,
            })),
          );
        }
      } catch {
        // Silent fail
      } finally {
        if (!cancelled) setRestoring(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [session, sessionId]);

  // Abort SSE stream on unmount
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  // Auto-scroll to bottom (only for new messages, not for "load more")
  useEffect(() => {
    if (scrollRef.current && !loadingMore) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, streaming, loadingMore]);

  const handleLoadMore = useCallback(async () => {
    if (!sessionId || loadingMore) return;

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

      setMessages((prev) => [...olderMessages, ...prev]);
      setHasMore(result.has_more);

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
      setLastStats(null);

      // Abort previous stream if still running
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      try {
        // If no active session, create one first
        let sid = sessionId;
        if (!sid) {
          const newSession = await chatApi.createSession();
          sid = newSession.session_id;
          onSessionCreated?.(sid);
        }

        const res = await fetch(`${API_BASE}/chat/stream`, {
          method: "POST",
          signal: controller.signal,
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            query,
            session_id: sid,
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
                    if (!sessionId) {
                      onSessionCreated?.(event.session_id);
                    }
                    onSessionUpdate?.(event.session_id, {
                      title: query.slice(0, 80) + (query.length > 80 ? "..." : ""),
                    });
                  }
                  if ("citations" in event && event.citations) {
                    citations = event.citations;
                  }
                  if ("stats" in event && event.stats) {
                    setLastStats(event.stats);
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
    [session, sessionId, streaming, onSessionCreated, onSessionUpdate],
  );

  const handleSelectSession = useCallback(
    (id: string) => {
      onSelectSession(id);
      onRefreshSessions();
    },
    [onSelectSession, onRefreshSessions],
  );

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2 shrink-0 border-b">
        <div className="flex items-center gap-1.5 flex-1 min-w-0">
          <h2 className="text-sm font-medium text-muted-foreground truncate">
            {activeSession?.title === "Active chat" ? "Chat mới" : (activeSession?.title ?? "Chat mới")}
          </h2>
        </div>
        <div className="flex items-center gap-1">
          <Button variant="outline" size="sm" className="gap-1.5 h-8" onClick={onNewChat}>
            <Plus className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">Chat mới</span>
          </Button>

          <DropdownMenu>
            <DropdownMenuTrigger className="inline-flex items-center gap-1.5 h-8 px-3 text-sm border border-input rounded-md bg-background hover:bg-accent hover:text-accent-foreground">
              <History className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Lịch sử</span>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-72 max-h-80 overflow-y-auto">
              {sessionsLoading ? (
                <div className="flex items-center justify-center py-4">
                  <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                </div>
              ) : sessions.length === 0 ? (
                <div className="px-4 py-3 text-center text-sm text-muted-foreground">
                  Chưa có cuộc chat nào
                </div>
              ) : (
                sessions.map((s) => (
                  <DropdownMenuItem
                    key={s.session_id}
                    onClick={() => handleSelectSession(s.session_id)}
                    className="flex items-start gap-2 py-2 cursor-pointer"
                  >
                    <MessageSquare className="h-4 w-4 shrink-0 mt-0.5 text-muted-foreground" />
                    <div className="flex flex-col gap-0.5 min-w-0">
                      <span className="text-sm truncate">
                        {s.title === "Active chat" ? "Chat mới" : s.title}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {formatRelativeTime(s.updated_at)} · {s.message_count} tin nhắn
                      </span>
                    </div>
                  </DropdownMenuItem>
                ))
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 min-h-0 overflow-y-auto" ref={scrollRef}>
        {restoring ? (
          <div className="flex items-center justify-center h-full">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
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

      {/* Stats bar */}
      {lastStats && !streaming && (
        <div className="flex items-center justify-center gap-2 px-4 py-1.5 text-xs text-muted-foreground border-t bg-muted/30 flex-wrap">
          <span>{(lastStats.total_ms / 1000).toFixed(1)}s</span>
          <span className="text-border">|</span>
          {lastStats.ttft_ms != null && (
            <>
              <span>TTFT {(lastStats.ttft_ms / 1000).toFixed(1)}s</span>
              <span className="text-border">|</span>
            </>
          )}
          <span>{lastStats.chars} ký tự</span>
          {(lastStats.total_tokens ?? 0) > 0 && (
            <>
              <span className="text-border">|</span>
              <span>{(lastStats.total_tokens ?? 0).toLocaleString()} tokens</span>
              <span className="text-border">|</span>
              <span>${(lastStats.estimated_cost_usd ?? 0).toFixed(4)}</span>
            </>
          )}
        </div>
      )}

      {/* Input */}
      <ChatInput onSend={handleSend} disabled={streaming || restoring} />
    </div>
  );
}
