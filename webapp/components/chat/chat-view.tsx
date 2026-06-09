"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSession } from "next-auth/react";
import { Building2, RefreshCw } from "lucide-react";
import { toast } from "sonner";

import { ChatInput } from "@/components/chat/chat-input";
import { ChatMessage as ChatBubble } from "@/components/chat/chat-message";
import { TenantSelect } from "@/components/tenants/tenant-select";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { chatApi, tenantsApi } from "@/lib/api-client";
import type { ChatStreamEvent, ChatUsage, TenantItem, TenantSetting } from "@/types/api";
import type { ChatMessage } from "@/types/chat";

const MAX_CONTEXT_MESSAGES = 8;

function createMessage(role: "user" | "assistant", content: string): ChatMessage {
  return {
    id: crypto.randomUUID(),
    role,
    content,
    citations: [],
  };
}

export function ChatView() {
  const { data: session } = useSession();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [thinkingMode, setThinkingMode] = useState(false);
  const [usage, setUsage] = useState<ChatUsage | null>(null);
  const [feedbackByMessageId, setFeedbackByMessageId] = useState<Record<string, "like" | "dislike">>({});
  const [feedbackSubmittingId, setFeedbackSubmittingId] = useState<string | null>(null);
  const [tenantOptions, setTenantOptions] = useState<TenantItem[]>([]);
  const [selectedTenantId, setSelectedTenantId] = useState<string>("");
  const [tenantSetting, setTenantSetting] = useState<TenantSetting | null>(null);
  const [loadingTenantContext, setLoadingTenantContext] = useState(true);
  const controllerRef = useRef<AbortController | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const previousTenantIdRef = useRef<string | null | undefined>(undefined);
  const isPlatformAdmin = session?.role === "platform_admin";

  const effectiveTenantId = useMemo(() => {
    if (isPlatformAdmin) return selectedTenantId || null;
    return session?.tenantId || null;
  }, [isPlatformAdmin, selectedTenantId, session?.tenantId]);

  const loadPlatformTenants = useCallback(async () => {
    const rows = await tenantsApi.list();
    setTenantOptions(rows);
    setSelectedTenantId((current) => (current && rows.some((tenant) => tenant.id === current) ? current : ""));
  }, []);

  const loadTenantContext = useCallback(async () => {
    if (!session) return;

    setLoadingTenantContext(true);
    try {
      if (isPlatformAdmin) {
        await loadPlatformTenants();
        if (!selectedTenantId) {
          setTenantSetting(null);
          return;
        }
        const setting = await tenantsApi.getSettings(selectedTenantId);
        setTenantSetting(setting);
      } else {
        const setting = await tenantsApi.getMySettings();
        setTenantSetting(setting);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Không thể tải cấu hình tenant";
      toast.error(message);
    } finally {
      setLoadingTenantContext(false);
    }
  }, [isPlatformAdmin, loadPlatformTenants, selectedTenantId, session]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadTenantContext();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadTenantContext]);

  useEffect(() => {
    return () => {
      controllerRef.current?.abort();
      controllerRef.current = null;
    };
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  useEffect(() => {
    if (previousTenantIdRef.current === undefined) {
      previousTenantIdRef.current = effectiveTenantId;
      return;
    }

    if (previousTenantIdRef.current !== effectiveTenantId) {
      previousTenantIdRef.current = effectiveTenantId;
      controllerRef.current?.abort();
      controllerRef.current = null;
      setMessages([]);
      setUsage(null);
      setStreaming(false);
    }
  }, [effectiveTenantId]);

  const resetConversation = useCallback(() => {
    controllerRef.current?.abort();
    controllerRef.current = null;
    setMessages([]);
    setUsage(null);
    setStreaming(false);
    setFeedbackByMessageId({});
  }, []);

  const sendMessage = useCallback(
    async (content: string, nextThinkingMode?: boolean) => {
      if (!effectiveTenantId) {
        toast.error("Chưa có tenant để chat thử");
        return;
      }

      const nextMessages = [...messages, createMessage("user", content)];
      const assistantId = crypto.randomUUID();

      setMessages([
        ...nextMessages,
        {
          id: assistantId,
          role: "assistant",
          content: "",
          citations: [],
        },
      ]);
      setUsage(null);
      setStreaming(true);

      const contextMessages = nextMessages.slice(-MAX_CONTEXT_MESSAGES).map((message) => ({
        role: message.role,
        content: message.content,
      }));

      const { controller, fetchStream } = chatApi.chatStream(content, contextMessages, {
        tenantId: effectiveTenantId,
        thinkingMode: nextThinkingMode,
      });

      controllerRef.current = controller;

      try {
        const response = await fetchStream;
        if (!response.ok || !response.body) {
          throw new Error("Không thể mở stream chat");
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const events = buffer.split("\n\n");
          buffer = events.pop() || "";

          for (const rawEvent of events) {
            const line = rawEvent.split("\n").find((item) => item.trim().startsWith("data: "));
            if (!line) continue;

            const payload = line.replace(/^data:\s*/, "");
            const event = JSON.parse(payload) as ChatStreamEvent;

            if (!event.done) {
              if ("chunk" in event && event.chunk) {
                setMessages((current) =>
                  current.map((message) =>
                    message.id === assistantId ? { ...message, content: `${message.content}${event.chunk}` } : message,
                  ),
                );
              }
              continue;
            }

            if ("error" in event && event.error) {
              throw new Error(event.error);
            }

            setMessages((current) =>
              current.map((message) =>
                message.id === assistantId
                  ? {
                      ...message,
                      citations: event.citations || [],
                    }
                  : message,
              ),
            );
            setUsage(event.stats || null);
          }
        }
      } catch (error) {
        if ((error as Error).name !== "AbortError") {
          const message = error instanceof Error ? error.message : "Có lỗi khi chat";
          toast.error(message);
          setMessages((current) => current.filter((message) => message.id !== assistantId));
        }
      } finally {
        controllerRef.current = null;
        setStreaming(false);
      }
    },
    [effectiveTenantId, messages],
  );

  const handleFeedback = useCallback(
    async (messageId: string, feedbackType: "like" | "dislike") => {
      if (!effectiveTenantId) {
        toast.error("Chưa có tenant để ghi nhận đánh giá");
        return;
      }

      const assistantIndex = messages.findIndex((message) => message.id === messageId && message.role === "assistant");
      if (assistantIndex < 0) return;

      const assistantMessage = messages[assistantIndex];
      const queryText =
        [...messages.slice(0, assistantIndex)]
          .reverse()
          .find((message) => message.role === "user" && message.content.trim())?.content || "";

      if (!queryText.trim() || !assistantMessage.content.trim()) {
        toast.error("Chưa đủ dữ liệu để gửi đánh giá");
        return;
      }

      try {
        setFeedbackSubmittingId(messageId);
        await chatApi.submitFeedback({
          tenant_id: effectiveTenantId,
          feedback_type: feedbackType,
          query_text: queryText,
          assistant_answer: assistantMessage.content,
          citations: assistantMessage.citations || [],
          metadata: {
            source: "internal_chat",
            assistant_message_id: messageId,
          },
        });
        setFeedbackByMessageId((current) => ({ ...current, [messageId]: feedbackType }));
        toast.success(feedbackType === "like" ? "Đã ghi nhận phản hồi tốt" : "Đã ghi nhận phản hồi chưa tốt");
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "Không thể gửi đánh giá");
      } finally {
        setFeedbackSubmittingId((current) => (current === messageId ? null : current));
      }
    },
    [effectiveTenantId, messages],
  );

  return (
    <div className="grid h-full min-h-0 grid-rows-[auto,minmax(0,1fr),auto] bg-background">
      <div className="sticky top-0 z-10 border-b border-border/40 bg-background/80 px-4 py-3 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="mx-auto flex w-full max-w-3xl items-center justify-between gap-3">
          <div className="flex min-w-0 items-center gap-3">
            <div className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-primary to-[#084ea4] text-primary-foreground shadow-[0_4px_14px_-6px_rgba(1,56,123,0.5)]">
              <span className="text-xs font-bold tracking-tight">SSE</span>
            </div>
            <div className="min-w-0">
              <h2 className="truncate text-sm font-semibold tracking-tight">{tenantSetting?.chatbot_display_name || "Chat thử"}</h2>
              <p className="truncate text-xs text-muted-foreground">
                {tenantSetting?.welcome_message || "Hỏi nhanh theo tài liệu của tenant hiện tại."}
              </p>
            </div>
          </div>

          <div className="flex shrink-0 items-center gap-2">
            {isPlatformAdmin ? (
              <div className="flex h-9 items-center gap-1.5 rounded-full border border-border/60 bg-background/80 px-2.5 text-sm transition-colors hover:border-border">
                <Building2 className="size-3.5 text-muted-foreground" />
                <TenantSelect
                  tenants={tenantOptions}
                  value={selectedTenantId}
                  onValueChange={(tenantId) => setSelectedTenantId(tenantId || "")}
                  placeholder="Chọn tenant"
                  triggerClassName="h-7 border-0 bg-transparent px-0 text-xs shadow-none focus:ring-0"
                />
              </div>
            ) : null}
            <Button variant="outline" size="sm" onClick={resetConversation} className="h-9 rounded-full" title="Tạo chat mới">
              <RefreshCw data-icon="inline-start" />
              Chat mới
            </Button>
          </div>
        </div>
      </div>

      <ScrollArea className="min-h-0">
        <div className="mx-auto flex w-full max-w-3xl flex-col py-6">
          {messages.length === 0 ? (
            <div className="mx-4 mt-12 flex flex-col items-center gap-3 px-6 text-center">
              <div className="flex size-12 items-center justify-center rounded-2xl bg-gradient-to-br from-primary to-[#084ea4] text-primary-foreground shadow-[0_8px_24px_-10px_rgba(1,56,123,0.5)]">
                <span className="text-sm font-bold tracking-tight">SSE</span>
              </div>
              <div className="space-y-1">
                <div className="text-lg font-semibold tracking-tight text-foreground">
                  {loadingTenantContext
                    ? "Đang tải cấu hình..."
                    : isPlatformAdmin && !effectiveTenantId
                      ? "Chọn tenant để bắt đầu"
                      : "Bắt đầu một cuộc trò chuyện mới"}
                </div>
                <p className="mx-auto max-w-md text-sm leading-6 text-muted-foreground">
                  {loadingTenantContext
                    ? "Vui lòng chờ một chút."
                    : isPlatformAdmin && !effectiveTenantId
                      ? "Chọn tenant ở góc trên bên phải trước khi gửi câu hỏi."
                      : "Hỏi ngắn gọn, AI sẽ tự dùng tài liệu phù hợp để trả lời."}
                </p>
              </div>
            </div>
          ) : (
            <div className="space-y-1">
              {messages.map((message, index) => (
                <ChatBubble
                  key={message.id}
                  message={message}
                  isStreaming={streaming && index === messages.length - 1 && message.role === "assistant"}
                  isThinking={streaming && index === messages.length - 1 && message.role === "assistant"}
                  usage={index === messages.length - 1 && message.role === "assistant" ? usage : null}
                  feedback={feedbackByMessageId[message.id] || null}
                  feedbackDisabled={feedbackSubmittingId === message.id}
                  onFeedback={message.role === "assistant" ? handleFeedback : undefined}
                />
              ))}
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
      </ScrollArea>

      <div className="sticky bottom-0 z-10">
        <Separator />
        <ChatInput
          onSend={sendMessage}
          onStop={() => controllerRef.current?.abort()}
          disabled={loadingTenantContext || !effectiveTenantId}
          streaming={streaming}
          thinkingMode={thinkingMode}
          onThinkingToggle={() => setThinkingMode((current) => !current)}
        />
      </div>
    </div>
  );
}
