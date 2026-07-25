"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { MessageSquare, RefreshCw, Zap, ShieldAlert, Sparkles, BookOpen, Clock, FileText, ChevronRight, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
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
    <div className="space-y-6 p-6 max-w-7xl mx-auto">
      {/* Header Banner */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-blue-900/40 via-indigo-900/30 to-purple-900/40 border border-indigo-500/20 p-6 md:p-8 backdrop-blur-xl shadow-2xl">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 relative z-10">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/30 text-indigo-400 text-xs font-semibold uppercase tracking-wider mb-3">
              <Sparkles className="w-3.5 h-3.5" /> Admin Audit & KB Enhancement
            </div>
            <h1 className="text-2xl md:text-3xl font-heading font-bold text-foreground tracking-tight">
              Nhật ký Hỏi & Đáp (Admin Audit)
            </h1>
            <p className="text-sm text-muted-foreground mt-1 max-w-2xl">
              Danh sách các câu hỏi thực tế của người dùng. Admin sử dụng nhật ký này để phát hiện câu hỏi "Chưa đủ căn cứ" và bổ sung tài liệu mới vào Knowledge Base.
            </p>
          </div>

          <Button
            onClick={fetchConversations}
            disabled={loading}
            variant="outline"
            className="border-indigo-500/30 bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-300"
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${loading ? "animate-spin" : ""}`} /> Làm mới
          </Button>
        </div>
      </div>

      {/* Main Table List */}
      <div className="rounded-xl border border-border bg-card/60 backdrop-blur-md overflow-hidden shadow-lg">
        {loading ? (
          <div className="p-12 text-center text-muted-foreground">
            <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-indigo-400" />
            Đang tải nhật ký hội thoại...
          </div>
        ) : conversations.length === 0 ? (
          <div className="p-12 text-center text-muted-foreground">
            <MessageSquare className="w-10 h-10 mx-auto mb-3 text-muted-foreground/40" />
            Chưa có cuộc hội thoại nào được ghi nhận.
          </div>
        ) : (
          <div className="divide-y divide-border">
            {conversations.map((item) => (
              <div
                key={item.id}
                onClick={() => openConversationDetail(item.conversation_id)}
                className="p-4 md:p-5 flex items-center justify-between hover:bg-muted/40 transition-colors cursor-pointer group"
              >
                <div className="flex items-center gap-4">
                  <div className="w-10 h-10 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 group-hover:scale-105 transition-transform">
                    <MessageSquare className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-sm font-medium text-foreground">
                        {item.conversation_id.slice(0, 18)}...
                      </span>
                      <Badge variant="outline" className="text-xs bg-muted/50">
                        {item.message_count} tin nhắn
                      </Badge>
                    </div>
                    <div className="flex items-center gap-3 text-xs text-muted-foreground mt-1">
                      <span className="flex items-center gap-1">
                        <Clock className="w-3.5 h-3.5" />
                        Lần cuối: {item.last_message_at ? new Date(item.last_message_at).toLocaleString("vi-VN") : "N/A"}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <span className="text-xs text-indigo-400 font-medium opacity-0 group-hover:opacity-100 transition-opacity">
                    Xem chi tiết
                  </span>
                  <ChevronRight className="w-4 h-4 text-muted-foreground group-hover:translate-x-1 transition-transform" />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Dialog Detail View */}
      <Dialog open={!!selectedConvId} onOpenChange={() => setSelectedConvId(null)}>
        <DialogContent className="max-w-3xl max-h-[85vh] overflow-y-auto bg-card border-border">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-lg font-heading font-semibold">
              <MessageSquare className="w-5 h-5 text-indigo-400" />
              Chi tiết Cuộc hội thoại (Session Audit)
            </DialogTitle>
            <DialogDescription className="font-mono text-xs text-muted-foreground">
              ID: {selectedConvId}
            </DialogDescription>
          </DialogHeader>

          {loadingDetail ? (
            <div className="p-8 text-center text-muted-foreground">
              <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-indigo-400" />
              Đang tải tin nhắn...
            </div>
          ) : messages.length === 0 ? (
            <div className="p-8 text-center text-muted-foreground">Không có tin nhắn nào.</div>
          ) : (
            <div className="space-y-4 py-2">
              {messages.map((msg) => {
                const isUser = msg.role === "user";
                return (
                  <div
                    key={msg.id}
                    className={`p-4 rounded-xl border ${
                      isUser
                        ? "bg-muted/40 border-border ml-4"
                        : "bg-indigo-950/20 border-indigo-500/20 mr-4"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2 mb-2">
                      <div className="flex items-center gap-2">
                        <span
                          className={`text-xs font-semibold uppercase px-2 py-0.5 rounded ${
                            isUser ? "bg-muted text-muted-foreground" : "bg-indigo-500/20 text-indigo-300"
                          }`}
                        >
                          {isUser ? "Người dùng (User)" : "Trợ lý AI"}
                        </span>
                        {msg.is_cache_hit && (
                          <Badge variant="outline" className="text-[10px] bg-emerald-500/10 border-emerald-500/30 text-emerald-400">
                            <Zap className="w-3 h-3 mr-1" /> Cache HIT ({msg.cached_type || "L1"})
                          </Badge>
                        )}
                        {msg.no_answer && (
                          <Badge variant="outline" className="text-[10px] bg-amber-500/10 border-amber-500/30 text-amber-400">
                            <ShieldAlert className="w-3 h-3 mr-1" /> Cần bổ sung tài liệu
                          </Badge>
                        )}
                      </div>

                      {msg.created_at && (
                        <span className="text-[11px] text-muted-foreground">
                          {new Date(msg.created_at).toLocaleTimeString("vi-VN")}
                        </span>
                      )}
                    </div>

                    {/* Message Body */}
                    <div className="text-sm whitespace-pre-wrap leading-relaxed text-foreground">
                      {msg.content}
                    </div>

                    {/* Citations if available */}
                    {!isUser && msg.citations && msg.citations.length > 0 && (
                      <div className="mt-3 pt-2 border-t border-indigo-500/10">
                        <div className="text-xs font-medium text-indigo-300 mb-1 flex items-center gap-1">
                          <BookOpen className="w-3.5 h-3.5" /> Nguồn dẫn chứng ({msg.citations.length}):
                        </div>
                        <div className="flex flex-wrap gap-1.5">
                          {msg.citations.map((c, idx) => (
                            <Badge key={idx} variant="outline" className="text-[11px] bg-indigo-900/30 border-indigo-500/20">
                              <FileText className="w-3 h-3 mr-1" /> {c.title || "Tài liệu"} {c.page_range ? `(Trang ${c.page_range})` : ""}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Performance & Token usage stats */}
                    {!isUser && (
                      <div className="mt-3 text-[11px] text-muted-foreground/80 flex flex-wrap items-center gap-3 pt-2 border-t border-border/40">
                        {msg.model_name && <span>Model: <code className="text-foreground">{msg.model_name}</code></span>}
                        {msg.latency_ms !== undefined && <span>Độ trễ: <code className="text-foreground">{msg.latency_ms.toFixed(0)}ms</code></span>}
                        {msg.prompt_tokens !== undefined && (
                          <span>Tokens: <code className="text-foreground">{msg.prompt_tokens + (msg.completion_tokens || 0)}</code></span>
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
