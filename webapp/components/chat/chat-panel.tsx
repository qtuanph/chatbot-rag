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
import { analyticsApi, chatApi } from "@/lib/api-client";
import type { ChatMessage as ChatMessageType } from "@/types/chat";
import type { ChatSession, Citation, ChatStreamDone, AnalyticsStats } from "@/types/api";

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
  const [thinkingMode, setThinkingMode] = useState(false);
  const [isThinking, setIsThinking] = useState(false);
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
  const [userStats, setUserStats] = useState<AnalyticsStats | null>(null);

  // Fetch user analytics stats once per mount
  useEffect(() => {
    if (!session) return;
    analyticsApi.getStats().then(setUserStats).catch(() => {});
  }, [session]);

  // Active session display
  const activeSession = sessions.find((s) => s.session_id === sessionId);

  // Load messages when sessionId changes (skip for just-created sessions)
  useEffect(() => {
    let cancelled = false;

    (async () => {
      if (!session || !sessionId) {
        setMessages([]);
        setHasMore(false);
        setRestoring(false);
        return;
      }

      // Skip loading for locally-created sessions — they have no messages yet
      if (sessionId === justCreatedSessionId) return;

      setRestoring(true);

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
              feedback: m.feedback,
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
  }, [session, sessionId, justCreatedSessionId]);

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
        feedback: m.feedback,
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
    async (query: string, thinking?: boolean) => {
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

      abortRef.current?.abort();
      let fullText = "";
      const citations: Citation[] = [];

      try {
        let sid = sessionId;
        let isNewSession = false;
        if (!sid) {
          const newSession = await chatApi.createSession();
          sid = newSession.session_id;
          isNewSession = true;
          onSessionCreated?.(sid!);
        }

        const { controller, fetchStream } = chatApi.chatStream(query, sid, thinking ?? thinkingMode);
        abortRef.current = controller;

        const response = await fetchStream;
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        const reader = response.body?.getReader();
        if (!reader) throw new Error("No response body");

        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed || !trimmed.startsWith("data: ")) continue;

            try {
              const data = JSON.parse(trimmed.slice(6));
              if (data.error) {
                setMessages((prev) =>
                  prev.map((m) => m.id === assistantId ? { ...m, content: data.error } : m)
                );
                reader.cancel();
                return;
              }
              if (data.thinking !== undefined) {
                // Thinking status update during retrieval
                setIsThinking(data.thinking);
                continue;
              }
              if (data.done) {
                if (data.session_id && isNewSession) {
                  onSessionUpdate?.(data.session_id, { title: query.slice(0, 80) + (query.length > 80 ? "..." : "") });
                }
                if (data.citations) {
                  data.citations.forEach((c: Citation) => {
                    if (!citations.find((ec) => ec.document_id === c.document_id)) citations.push(c);
                  });
                }
                if (data.stats) setLastStats(data.stats);
                const doneEvent = data as ChatStreamDone;
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantId ? { ...m, id: doneEvent.message_id || m.id, content: fullText, citations } : m
                  ),
                );
              } else {
                fullText += data.chunk || "";
                setMessages((prev) => prev.map((m) => m.id === assistantId ? { ...m, content: fullText } : m));
              }
            } catch { /* skip malformed SSE events */ }
          }
        }
      } catch (err: unknown) {
        if (err instanceof DOMException && err.name === "AbortError") return;
        toast.error("Lỗi kết nối. Vui lòng thử lại.");
        setMessages((prev) =>
          prev.map((m) => m.id === assistantId ? { ...m, content: "Lỗi khi gửi tin nhắn. Vui lòng thử lại." } : m)
        );
      } finally {
        setStreaming(false);
        onRefreshSessions();
      }
    },
    [session, sessionId, streaming, onSessionCreated, onSessionUpdate, onRefreshSessions],
  );

  const handleStop = useCallback(() => {
      abortRef.current?.abort();
    }, []);

  const handleSelectSession = useCallback(
    (id: string) => {
      onSelectSession(id);
      onRefreshSessions();
    },
    [onSelectSession, onRefreshSessions],
  );

  return (
    <div className="flex h-full min-h-0 flex-col overscroll-none">
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
              ) : sessions.filter((s) => s.message_count > 0).length === 0 ? (
                <div className="px-4 py-3 text-center text-sm text-muted-foreground">
                  Chưa có cuộc chat nào
                </div>
              ) : (
                sessions
                  .filter((s) => s.message_count > 0)
                  .map((s) => (
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
      <div className="flex-1 min-h-0 overflow-y-auto overscroll-contain" ref={scrollRef}>
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
              {userStats && userStats.total_messages > 0 && (
                <p className="text-xs text-muted-foreground mt-2">
                  Bạn đã dùng {userStats.total_messages.toLocaleString()} tin nhắn
                  {" \u00B7 "}
                  {userStats.total_tokens.toLocaleString()} tokens
                  {userStats.estimated_cost_usd > 0 && (
                    <>
                      {" \u00B7 "}
                      ${userStats.estimated_cost_usd.toFixed(4)}
                    </>
                  )}
                </p>
              )}
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
                isThinking={isThinking && index === messages.length - 1 && msg.role === "assistant"}
                stats={index === messages.length - 1 && msg.role === "assistant" && !streaming ? lastStats : undefined}
              />
            ))}
          </div>
        )}
      </div>

      {/* Input */}
      <ChatInput
        onSend={handleSend}
        onStop={handleStop}
        disabled={streaming || restoring}
        streaming={streaming}
        thinkingMode={thinkingMode}
        onThinkingToggle={() => setThinkingMode((prev) => !prev)}
      />
    </div>
  );
}
