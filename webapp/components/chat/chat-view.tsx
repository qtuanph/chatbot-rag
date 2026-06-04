"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSession } from "next-auth/react";
import { Building2, RefreshCw, ShieldCheck, Sparkles } from "lucide-react";
import { toast } from "sonner";

import { chatApi, tenantsApi } from "@/lib/api-client";
import type { ChatStreamEvent, ChatUsage, TenantItem, TenantSetting } from "@/types/api";
import type { ChatMessage } from "@/types/chat";
import { ChatInput } from "@/components/chat/chat-input";
import { ChatMessage as ChatBubble } from "@/components/chat/chat-message";
import { TenantSelect } from "@/components/tenants/tenant-select";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

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

      const contextMessages = nextMessages
        .slice(-MAX_CONTEXT_MESSAGES)
        .map((message) => ({ role: message.role, content: message.content }));

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

  return (
    <div className="grid h-full min-h-0 grid-rows-[auto,minmax(0,1fr),auto] bg-[radial-gradient(circle_at_top,rgba(59,130,246,0.08),transparent_32%),linear-gradient(to_bottom,rgba(255,255,255,0.96),rgba(255,255,255,1))] dark:bg-[radial-gradient(circle_at_top,rgba(59,130,246,0.14),transparent_28%),linear-gradient(to_bottom,rgba(9,9,11,0.98),rgba(9,9,11,1))]">
      <div className="sticky top-0 z-10 border-b border-border/60 bg-background/85 px-4 py-4 backdrop-blur supports-[backdrop-filter]:bg-background/70">
        <div className="mx-auto flex w-full max-w-6xl flex-col gap-4">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="outline" className="rounded-full px-3 py-1 text-[11px] uppercase tracking-wide">
                  Chat nội bộ
                </Badge>
                <Badge variant="secondary" className="rounded-full px-3 py-1 text-[11px]">
                  Stateless
                </Badge>
                {thinkingMode ? (
                  <Badge className="rounded-full px-3 py-1 text-[11px]">
                    Suy luận sâu
                  </Badge>
                ) : null}
              </div>
              <div>
                <h2 className="text-2xl font-semibold tracking-tight">
                  {tenantSetting?.chatbot_display_name || "Chat thử theo tenant"}
                </h2>
                <p className="mt-1 max-w-3xl text-sm leading-6 text-muted-foreground">
                  {tenantSetting?.welcome_message || "Trò chuyện với trợ lý nội bộ theo đúng tài liệu và instruction của tenant đang chọn."}
                </p>
              </div>
            </div>

            <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
              {isPlatformAdmin ? (
                <div className="flex min-w-[320px] items-center gap-2 rounded-2xl border border-border/70 bg-card/80 px-3 py-2 shadow-sm">
                  <Building2 className="h-4 w-4 text-muted-foreground" />
                  <TenantSelect
                    tenants={tenantOptions}
                    value={selectedTenantId}
                    onValueChange={(tenantId) => setSelectedTenantId(tenantId || "")}
                    placeholder="Chọn tenant để chat thử"
                    triggerClassName="border-0 bg-transparent px-0 shadow-none focus:ring-0"
                  />
                </div>
              ) : null}
              <Button variant="outline" onClick={resetConversation} className="rounded-2xl">
                <RefreshCw className="mr-2 h-4 w-4" />
                Làm mới hội thoại
              </Button>
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-3">
            <div className="rounded-2xl border border-border/60 bg-card/80 px-4 py-3 shadow-sm">
              <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                <ShieldCheck className="h-3.5 w-3.5" />
                Phạm vi
              </div>
              <div className="mt-2 text-sm font-medium">
                {isPlatformAdmin ? (effectiveTenantId ? "Đang test đúng tenant đã chọn" : "Chưa chọn tenant để test") : "Chỉ trong tenant của bạn"}
              </div>
            </div>
            <div className="rounded-2xl border border-border/60 bg-card/80 px-4 py-3 shadow-sm">
              <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                <Sparkles className="h-3.5 w-3.5" />
                Hành vi
              </div>
              <div className="mt-2 text-sm font-medium">Ngữ cảnh được bơm từ tài liệu và instruction tenant</div>
            </div>
            <div className="rounded-2xl border border-border/60 bg-card/80 px-4 py-3 shadow-sm">
              <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Lưu trữ</div>
              <div className="mt-2 text-sm font-medium">Không lưu lịch sử sau khi đóng hoặc làm mới</div>
            </div>
          </div>
        </div>
      </div>

      <div className="min-h-0 overflow-y-auto">
        <div className="mx-auto flex w-full max-w-6xl flex-col py-6">
          {messages.length === 0 ? (
            <Card className="mx-4 mt-4 border-border/60 bg-card/90 shadow-xl shadow-black/5">
              <CardHeader>
                <CardTitle>Bắt đầu một cuộc trò chuyện mới</CardTitle>
                <CardDescription>
                  {loadingTenantContext
                    ? "Đang tải cấu hình tenant..."
                    : isPlatformAdmin && !effectiveTenantId
                      ? "Hãy chọn tenant ở khung bên trên trước khi gửi câu hỏi."
                      : "Anh có thể hỏi về quy trình, tài liệu hướng dẫn, câu hỏi nghiệp vụ và để AI trả lời theo đúng ngữ cảnh tenant."}
                </CardDescription>
              </CardHeader>
              <CardContent className="grid gap-3 text-sm text-muted-foreground md:grid-cols-3">
                <div className="rounded-2xl border border-border/60 bg-background/80 p-4">
                  <div className="font-medium text-foreground">Theo ngữ cảnh tenant</div>
                  <p className="mt-1 leading-6">Tài liệu, instruction và giới hạn sử dụng đều được áp đúng theo tenant hiện tại.</p>
                </div>
                <div className="rounded-2xl border border-border/60 bg-background/80 p-4">
                  <div className="font-medium text-foreground">Không có history DB</div>
                  <p className="mt-1 leading-6">Hội thoại chỉ tồn tại trong phiên trình duyệt đang mở để nhẹ hơn và an toàn hơn.</p>
                </div>
                <div className="rounded-2xl border border-border/60 bg-background/80 p-4">
                  <div className="font-medium text-foreground">Có trích dẫn rõ ràng</div>
                  <p className="mt-1 leading-6">Khi AI dùng tài liệu, phần tham khảo sẽ hiện ngay dưới câu trả lời để anh kiểm tra nhanh.</p>
                </div>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-1">
              {messages.map((message, index) => (
                <ChatBubble
                  key={message.id}
                  message={message}
                  isStreaming={streaming && index === messages.length - 1 && message.role === "assistant"}
                  isThinking={streaming && index === messages.length - 1 && message.role === "assistant"}
                  usage={index === messages.length - 1 && message.role === "assistant" ? usage : null}
                />
              ))}
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
      </div>

      <div className="sticky bottom-0 z-10">
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
