"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSession } from "next-auth/react";
import { RefreshCw } from "lucide-react";
import { toast } from "sonner";

import { ChatInput } from "@/components/chat/chat-input";
import { ChatMessage as ChatBubble } from "@/components/chat/chat-message";
import { TenantSelect } from "@/components/tenants/tenant-select";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { chatApi, tenantsApi } from "@/lib/api-client";
import type { ChatStreamEvent, ChatUsage, TenantItem, TenantSetting } from "@/types/api";
import type { ChatMessage } from "@/types/chat";

const MAX_CONTEXT_MESSAGES = 6;

function createMessage(role: "user" | "assistant", content: string): ChatMessage {
  return {
    id: crypto.randomUUID(),
    role,
    content,
    citations: [],
  };
}

function createWelcomeMessage(setting: TenantSetting | null): ChatMessage | null {
  const content = setting?.welcome_message?.trim();
  if (!content) return null;

  return {
    id: crypto.randomUUID(),
    role: "assistant",
    content,
    citations: [],
    kind: "welcome",
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
  const activeAssistantIdRef = useRef<string | null>(null);
  const pendingStreamTextRef = useRef("");
  const flushTimerRef = useRef<number | null>(null);
  const isPlatformAdmin = session?.role === "platform_admin";

  const effectiveTenantId = useMemo(() => {
    if (isPlatformAdmin) return selectedTenantId || null;
    return session?.tenantId || null;
  }, [isPlatformAdmin, selectedTenantId, session?.tenantId]);

  const loadPlatformTenants = useCallback(async () => {
    const rows = await tenantsApi.list();
    setTenantOptions(rows);
    setSelectedTenantId((current) => {
      if (current && rows.some((tenant) => tenant.id === current)) return current;
      if (rows.length > 0) return rows[0].id;
      return "";
    });
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
      if (flushTimerRef.current !== null) {
        window.clearTimeout(flushTimerRef.current);
        flushTimerRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: streaming ? "auto" : "smooth", block: "end" });
  }, [messages, streaming]);

  useEffect(() => {
    if (previousTenantIdRef.current === undefined) {
      previousTenantIdRef.current = effectiveTenantId;
      return;
    }

    if (previousTenantIdRef.current !== effectiveTenantId) {
      previousTenantIdRef.current = effectiveTenantId;
      controllerRef.current?.abort();
      controllerRef.current = null;
      activeAssistantIdRef.current = null;
      pendingStreamTextRef.current = "";
      if (flushTimerRef.current !== null) {
        window.clearTimeout(flushTimerRef.current);
        flushTimerRef.current = null;
      }
      setMessages([]);
      setUsage(null);
      setStreaming(false);
    }
  }, [effectiveTenantId]);

  const visibleMessages = useMemo(() => {
    if (messages.length > 0) return messages;
    if (loadingTenantContext || !effectiveTenantId) return messages;

    const welcomeMessage = createWelcomeMessage(tenantSetting);
    return welcomeMessage ? [welcomeMessage] : messages;
  }, [effectiveTenantId, loadingTenantContext, messages, tenantSetting]);

  const flushPendingStreamText = useCallback(() => {
    const assistantId = activeAssistantIdRef.current;
    const pendingText = pendingStreamTextRef.current;
    if (!assistantId || !pendingText) return;

    pendingStreamTextRef.current = "";
    setMessages((current) =>
      current.map((message) =>
        message.id === assistantId ? { ...message, content: `${message.content}${pendingText}` } : message,
      ),
    );
  }, []);

  const scheduleStreamFlush = useCallback(() => {
    if (flushTimerRef.current !== null) return;

    flushTimerRef.current = window.setTimeout(() => {
      flushTimerRef.current = null;
      flushPendingStreamText();
    }, 33);
  }, [flushPendingStreamText]);

  const resetConversation = useCallback(() => {
    controllerRef.current?.abort();
    controllerRef.current = null;
    activeAssistantIdRef.current = null;
    pendingStreamTextRef.current = "";
    if (flushTimerRef.current !== null) {
      window.clearTimeout(flushTimerRef.current);
      flushTimerRef.current = null;
    }
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
      activeAssistantIdRef.current = assistantId;
      pendingStreamTextRef.current = "";

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

      const contextMessages = nextMessages
        .filter((message) => message.kind !== "welcome")
        .slice(-MAX_CONTEXT_MESSAGES)
        .map((message) => ({
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
                pendingStreamTextRef.current += event.chunk;
                scheduleStreamFlush();
              }
              continue;
            }

            if ("error" in event && event.error) {
              throw new Error(event.error);
            }

            if (flushTimerRef.current !== null) {
              window.clearTimeout(flushTimerRef.current);
              flushTimerRef.current = null;
            }
            flushPendingStreamText();
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
        if (flushTimerRef.current !== null) {
          window.clearTimeout(flushTimerRef.current);
          flushTimerRef.current = null;
        }
        flushPendingStreamText();
        controllerRef.current = null;
        activeAssistantIdRef.current = null;
        pendingStreamTextRef.current = "";
        setStreaming(false);
      }
    },
    [effectiveTenantId, flushPendingStreamText, messages, scheduleStreamFlush],
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
    <div className="relative grid h-full min-h-0 grid-rows-[1fr,auto] bg-gradient-to-b from-background via-background to-muted/20">
      <div className="absolute top-4 right-4 left-4 z-20 mx-auto max-w-4xl">
        <div className="flex w-full items-center justify-between gap-3 rounded-2xl border border-white/10 bg-background/60 px-4 py-2 shadow-sm backdrop-blur-xl supports-[backdrop-filter]:bg-background/40">
          <div className="min-w-0 flex-1">
            <h2 className="truncate text-sm font-semibold tracking-tight">
              {tenantSetting?.chatbot_display_name || "Trợ lý AI Thông minh"}
            </h2>
          </div>

          <div className="flex shrink-0 items-center gap-2">
            {isPlatformAdmin ? (
              <TenantSelect
                tenants={tenantOptions}
                value={selectedTenantId}
                onValueChange={(tenantId) => setSelectedTenantId(tenantId || "")}
                placeholder="Chọn tenant"
                triggerClassName="h-8 min-w-[200px] rounded-lg bg-background/50 text-sm shadow-none border-border/50"
              />
            ) : null}
            <Button variant="ghost" size="icon" onClick={resetConversation} title="Tạo chat mới" className="rounded-xl hover:bg-background/80">
              <RefreshCw className="size-4 text-muted-foreground" />
            </Button>
          </div>
        </div>
      </div>

      <ScrollArea className="min-h-0 pt-20">
        <div className="mx-auto flex w-full max-w-3xl flex-col pb-6">
          {visibleMessages.length === 0 ? (
            <div className="mx-4 mt-24 flex flex-col items-center justify-center gap-6 text-center">
              <div className="relative flex h-24 w-24 items-center justify-center rounded-3xl bg-gradient-to-br from-primary/20 to-primary/5 p-4 shadow-[0_0_60px_-15px_rgba(var(--primary),0.5)]">
                <div className="absolute inset-0 rounded-3xl border border-primary/20 backdrop-blur-3xl" />
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src="/icons/icon-192x192.png" alt="AI Avatar" className="relative z-10 h-12 w-12 object-contain opacity-80 mix-blend-luminosity" />
              </div>
              <div className="space-y-2">
                <h1 className="bg-gradient-to-br from-foreground to-foreground/70 bg-clip-text text-3xl font-bold tracking-tight text-transparent">
                  {loadingTenantContext
                    ? "Đang kết nối..."
                    : isPlatformAdmin && !effectiveTenantId
                      ? "Chào mừng Quản trị viên"
                      : "Xin chào, tôi có thể giúp gì cho bạn?"}
                </h1>
                <p className="mx-auto max-w-md text-base text-muted-foreground/80">
                  {loadingTenantContext
                    ? "Hệ thống đang tải ngữ cảnh của Tenant..."
                    : isPlatformAdmin && !effectiveTenantId
                      ? "Vui lòng chọn một Tenant ở góc trên bên phải để bắt đầu trải nghiệm trợ lý AI riêng biệt của họ."
                      : "Tôi là trợ lý AI thông minh được huấn luyện dựa trên tài liệu của bạn. Hãy đặt câu hỏi!"}
                </p>
              </div>
            </div>
          ) : (
            <div className="space-y-1">
              {visibleMessages.map((message, index) => (
                <ChatBubble
                  key={message.id}
                  message={message}
                  isStreaming={streaming && index === visibleMessages.length - 1 && message.role === "assistant"}
                  isThinking={streaming && index === visibleMessages.length - 1 && message.role === "assistant"}
                  usage={index === visibleMessages.length - 1 && message.role === "assistant" ? usage : null}
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

      <div className="z-10 pb-6 pt-2">
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
