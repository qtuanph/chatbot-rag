"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { MessageSquare, RefreshCw, Zap, ShieldAlert, BookOpen, Clock, FileText, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { conversationsApi } from "@/lib/api-client";

interface ConversationItem {
  id: string;
  tenant_id: string;
  conversation_id: string;
  started_at?: string | null;
  last_message_at?: string | null;
  message_count: number;
}

interface ConversationMessage {
  id: string;
  role: string;
  content: string;
  model_name?: string | null;
  prompt_tokens?: number;
  completion_tokens?: number;
  latency_ms?: number;
  cost_micros_vnd?: number;
  is_cache_hit?: boolean;
  cached_type?: string | null;
  citations?: Array<{ document_id: string; title?: string | null; page_range?: string | null }>;
  no_answer?: boolean;
  created_at?: string | null;
}

export default function AdminConversationsPage() {
  const [conversations, setConversations] = useState<ConversationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedConvId, setSelectedConvId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [loadingDetail, setLoadingDetail] = useState(false);

  const fetchConversations = async () => {
    setLoading(true);
    try {
      const res = await conversationsApi.list(0, 50);
      setConversations(res.items || []);
    } catch (err: any) {
      toast.error("Không thể tải nhật ký hội thoại: " + (err?.message || "Lỗi server"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchConversations();
  }, []);

  const openConversationDetail = async (convId: string) => {
    setSelectedConvId(convId);
    setLoadingDetail(true);
    try {
      const res = await conversationsApi.getMessages(convId);
      setMessages(res.messages || []);
    } catch (err: any) {
      toast.error("Không thể tải nội dung chi tiết: " + (err?.message || "Lỗi server"));
    } finally {
      setLoadingDetail(false);
    }
  };

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Nhật ký Hỏi & Đáp (Admin Audit)</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Theo dõi các câu hỏi thực tế của người dùng để phát hiện nội dung "Chưa đủ căn cứ" và nâng cấp Knowledge Base.
          </p>
        </div>
        <Button onClick={fetchConversations} disabled={loading} variant="outline" size="sm" className="gap-2">
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} /> Làm mới
        </Button>
      </div>

      {/* Main List */}
      <Card className="p-0 overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-sm text-muted-foreground">
            <RefreshCw className="h-5 w-5 animate-spin mx-auto mb-2 text-primary" />
            Đang tải nhật ký hội thoại...
          </div>
        ) : conversations.length === 0 ? (
          <div className="p-12 text-center text-sm text-muted-foreground">
            <MessageSquare className="h-8 w-8 mx-auto mb-3 text-muted-foreground/50" />
            Chưa có cuộc hội thoại nào được ghi nhận.
          </div>
        ) : (
          <div className="divide-y divide-border">
            {conversations.map((item) => (
              <div
                key={item.id}
                onClick={() => openConversationDetail(item.conversation_id)}
                className="p-4 flex items-center justify-between hover:bg-muted/50 transition-colors cursor-pointer group"
              >
                <div className="flex items-center gap-3.5 min-w-0">
                  <div className="size-9 rounded-lg bg-muted flex items-center justify-center text-muted-foreground shrink-0 group-hover:text-primary transition-colors">
                    <MessageSquare className="h-4 w-4" />
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-sm font-semibold truncate">
                        {item.conversation_id}
                      </span>
                      <Badge variant="secondary" className="text-[10px] h-4 font-mono">
                        {item.message_count} tin nhắn
                      </Badge>
                    </div>
                    <div className="flex items-center gap-3 text-xs text-muted-foreground mt-1">
                      <span className="flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        Lần cuối: {item.last_message_at ? new Date(item.last_message_at).toLocaleString("vi-VN") : "N/A"}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-1 shrink-0 text-muted-foreground group-hover:text-foreground transition-colors">
                  <span className="text-xs font-medium">Chi tiết</span>
                  <ChevronRight className="h-4 w-4 group-hover:translate-x-0.5 transition-transform" />
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Dialog Detail View */}
      <Dialog open={!!selectedConvId} onOpenChange={() => setSelectedConvId(null)}>
        <DialogContent className="max-w-3xl max-h-[85vh] overflow-y-auto rounded-2xl border border-border/80 shadow-2xl backdrop-blur-xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-base font-semibold">
              <MessageSquare className="h-4 w-4 text-primary" />
              Chi tiết Phiên Hỏi & Đáp
            </DialogTitle>
            <DialogDescription className="font-mono text-xs">
              ID: {selectedConvId}
            </DialogDescription>
          </DialogHeader>

          {loadingDetail ? (
            <div className="p-8 text-center text-sm text-muted-foreground">
              <RefreshCw className="h-5 w-5 animate-spin mx-auto mb-2 text-primary" />
              Đang tải tin nhắn...
            </div>
          ) : messages.length === 0 ? (
            <div className="p-8 text-center text-sm text-muted-foreground">Không có tin nhắn nào.</div>
          ) : (
            <div className="space-y-3.5 py-2">
              {messages.map((msg) => {
                const isUser = msg.role === "user";
                return (
                  <div
                    key={msg.id}
                    className={`p-4 rounded-xl border text-sm ${
                      isUser
                        ? "bg-muted/30 border-border/50 ml-6"
                        : "bg-card border-border/80 mr-6 shadow-sm"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2 mb-2.5">
                      <div className="flex items-center gap-2">
                        <Badge
                          variant={isUser ? "outline" : "default"}
                          className="text-[10px] h-4 font-semibold uppercase tracking-wider"
                        >
                          {isUser ? "User" : "AI"}
                        </Badge>

                        {msg.is_cache_hit && (
                          <Badge variant="outline" className="text-[10px] h-4 bg-primary/10 border-primary/20 text-primary font-medium">
                            <Zap className="h-3 w-3 mr-1" /> Cache HIT ({msg.cached_type || "L1"})
                          </Badge>
                        )}
                        {msg.no_answer && (
                          <Badge variant="destructive" className="text-[10px] h-4">
                            <ShieldAlert className="h-3 w-3 mr-1" /> Chưa đủ căn cứ
                          </Badge>
                        )}
                      </div>

                      {msg.created_at && (
                        <span className="text-[11px] text-muted-foreground font-mono">
                          {new Date(msg.created_at).toLocaleTimeString("vi-VN")}
                        </span>
                      )}
                    </div>

                    {/* Content */}
                    <div className="text-sm leading-relaxed text-foreground">
                      {isUser ? (
                        <div className="whitespace-pre-wrap">{msg.content}</div>
                      ) : (
                        <div className="prose prose-sm dark:prose-invert max-w-none space-y-2 [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5 [&_h1]:text-base [&_h2]:text-base [&_h3]:text-sm [&_h1]:font-semibold [&_h2]:font-semibold [&_h3]:font-semibold [&_p]:my-1.5 [&_li]:my-0.5 [&_code]:bg-muted [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:rounded [&_code]:font-mono [&_code]:text-xs [&_pre]:bg-muted/80 [&_pre]:p-3 [&_pre]:rounded-lg [&_table]:border-collapse [&_table]:w-full [&_th]:border [&_th]:border-border [&_th]:p-2 [&_td]:border [&_td]:border-border [&_td]:p-2">
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>
                            {msg.content}
                          </ReactMarkdown>
                        </div>
                      )}
                    </div>

                    {/* Citations */}
                    {!isUser && msg.citations && msg.citations.length > 0 && (
                      <div className="mt-3 pt-2 border-t border-border/50">
                        <div className="text-xs font-medium text-muted-foreground mb-1.5 flex items-center gap-1">
                          <BookOpen className="h-3.5 w-3.5" /> Dẫn chứng ({msg.citations.length}):
                        </div>
                        <div className="flex flex-wrap gap-1.5">
                          {msg.citations.map((c, idx) => (
                            <Badge key={idx} variant="secondary" className="text-[11px] font-normal">
                              <FileText className="h-3 w-3 mr-1" /> {c.title || "Tài liệu"} {c.page_range ? `(Trang ${c.page_range})` : ""}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Stats */}
                    {!isUser && (
                      <div className="mt-2.5 text-[11px] text-muted-foreground flex flex-wrap items-center gap-3 pt-2 border-t border-border/40 font-mono">
                        {msg.model_name && <span>Model: {msg.model_name}</span>}
                        {msg.latency_ms !== undefined && <span>Độ trễ: {msg.latency_ms.toFixed(0)}ms</span>}
                        {msg.prompt_tokens !== undefined && (
                          <span>Tokens: {msg.prompt_tokens + (msg.completion_tokens || 0)}</span>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
