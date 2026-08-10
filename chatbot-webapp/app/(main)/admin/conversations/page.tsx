"use client";

import { useEffect, useState, useMemo } from "react";
import { toast } from "sonner";
import {
  MessageSquare,
  RefreshCw,
  Zap,
  ShieldAlert,
  BookOpen,
  Clock,
  FileText,
  ChevronRight,
  Sparkles,
  CheckCircle2,
  Building2,
  Filter,
  Layers,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { conversationsApi, faqApi, tenantsApi } from "@/lib/api-client";
import { TenantItem } from "@/types/api";

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
  const [tenants, setTenants] = useState<TenantItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterTenantId, setFilterTenantId] = useState<string>("ALL");

  const [selectedConvId, setSelectedConvId] = useState<string | null>(null);
  const [selectedTenantId, setSelectedTenantId] = useState<string>("");
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [loadingDetail, setLoadingDetail] = useState(false);

  // FAQ Modal states
  const [faqModalOpen, setFaqModalOpen] = useState(false);
  const [faqSelectedTenants, setFaqSelectedTenants] = useState<string[]>([]);
  const [faqQuestion, setFaqQuestion] = useState("");
  const [faqAnswer, setFaqAnswer] = useState("");
  const [faqVariants, setFaqVariants] = useState("");
  const [faqCitations, setFaqCitations] = useState<any[]>([]);
  const [submittingFaq, setSubmittingFaq] = useState(false);

  // Load Tenants list
  const fetchTenants = async () => {
    try {
      const data = await tenantsApi.list();
      setTenants(data || []);
    } catch (err: any) {
      console.error("Failed to load tenants list:", err);
    }
  };

  // Load Conversations list
  const fetchConversations = async () => {
    setLoading(true);
    try {
      const tenantParam = filterTenantId !== "ALL" ? filterTenantId : undefined;
      const res = await conversationsApi.list(0, 50, tenantParam);
      setConversations(res.items || []);
    } catch (err: any) {
      toast.error("Không thể tải nhật ký hội thoại: " + (err?.message || "Lỗi server"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTenants();
  }, []);

  useEffect(() => {
    fetchConversations();
  }, [filterTenantId]);

  // Tenant lookup map by ID
  const tenantMap = useMemo(() => {
    const map = new Map<string, TenantItem>();
    tenants.forEach((t) => map.set(t.id, t));
    return map;
  }, [tenants]);

  const openConversationDetail = async (convId: string, tenantId: string) => {
    setSelectedConvId(convId);
    setSelectedTenantId(tenantId);
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

  const handleOpenFaqModal = (question: string, answer: string, citations?: any[], tenantId?: string) => {
    const targetTenant = tenantId || selectedTenantId || (tenants[0]?.id ?? "");
    setFaqSelectedTenants([targetTenant]);
    setFaqQuestion(question);
    setFaqAnswer(answer);
    setFaqVariants("");
    setFaqCitations(citations || []);
    setFaqModalOpen(true);
  };

  const toggleFaqTenantSelection = (tenantId: string) => {
    setFaqSelectedTenants((prev) => {
      if (prev.includes(tenantId)) {
        if (prev.length === 1) return prev; // Keep at least one selected
        return prev.filter((id) => id !== tenantId);
      } else {
        return [...prev, tenantId];
      }
    });
  };

  const handleCreateFaq = async () => {
    if (!faqQuestion.trim() || !faqAnswer.trim()) {
      toast.error("Câu hỏi và câu trả lời không được để trống!");
      return;
    }
    if (faqSelectedTenants.length === 0) {
      toast.error("Vui lòng chọn ít nhất 1 Công ty/Tenant!");
      return;
    }

    setSubmittingFaq(true);
    try {
      const variants = faqVariants
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);

      // Create FAQ entries for all selected tenants
      let successCount = 0;
      for (const tId of faqSelectedTenants) {
        await faqApi.create(tId, {
          question: faqQuestion.trim(),
          answer: faqAnswer.trim(),
          question_variants: variants,
          citations: faqCitations,
        });
        successCount++;
      }

      toast.success(
        `🎉 Đã tạo thành công FAQ cho ${successCount} Công ty! Phản hồi sẽ diễn ra O(1) tức thì từ Redis Cache.`
      );
      setFaqModalOpen(false);
    } catch (err: any) {
      toast.error("Không thể tạo FAQ: " + (err?.message || "Lỗi hệ thống"));
    } finally {
      setSubmittingFaq(false);
    }
  };

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-6 p-6">
      {/* Header & Filter Controls */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <MessageSquare className="h-6 w-6 text-primary" />
            Nhật ký Hỏi & Đáp (Admin Audit Dashboard)
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Quản lý hội thoại thực tế, giám sát chất lượng phản hồi và tạo FAQ trực tiếp cho từng Công ty/Tenant.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Tenant Filter Dropdown */}
          <div className="flex items-center gap-2">
            <Filter className="h-4 w-4 text-muted-foreground shrink-0" />
            <NativeSelect
              value={filterTenantId}
              onChange={(e) => setFilterTenantId(e.target.value)}
              className="w-56"
            >
              <NativeSelectOption value="ALL">🏢 Tất cả Công ty (Tenants)</NativeSelectOption>
              {tenants.map((t) => (
                <NativeSelectOption key={t.id} value={t.id}>
                  {t.name} ({t.slug})
                </NativeSelectOption>
              ))}
            </NativeSelect>
          </div>

          <Button onClick={fetchConversations} disabled={loading} variant="outline" size="sm" className="gap-2 shrink-0">
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} /> Làm mới
          </Button>
        </div>
      </div>

      {/* Conversations Table / Card List */}
      <Card className="p-0 overflow-hidden border border-border/80 shadow-sm">
        {loading ? (
          <div className="p-12 text-center text-sm text-muted-foreground">
            <RefreshCw className="h-5 w-5 animate-spin mx-auto mb-2 text-primary" />
            Đang tải nhật ký hội thoại...
          </div>
        ) : conversations.length === 0 ? (
          <div className="p-12 text-center text-sm text-muted-foreground">
            <MessageSquare className="h-8 w-8 mx-auto mb-3 text-muted-foreground/40" />
            Không có cuộc hội thoại nào cho bộ lọc này.
          </div>
        ) : (
          <div className="divide-y divide-border">
            {conversations.map((item) => {
              const tenantObj = tenantMap.get(item.tenant_id);
              const tenantDisplayName = tenantObj ? tenantObj.name : item.tenant_id;

              return (
                <div
                  key={item.id}
                  onClick={() => openConversationDetail(item.conversation_id, item.tenant_id)}
                  className="p-4 flex items-center justify-between hover:bg-muted/50 transition-colors cursor-pointer group"
                >
                  <div className="flex items-center gap-3.5 min-w-0">
                    <div className="size-9 rounded-lg bg-primary/10 flex items-center justify-center text-primary shrink-0 group-hover:scale-105 transition-transform">
                      <MessageSquare className="h-4.5 w-4.5" />
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        {/* Tenant Name Badge */}
                        <Badge variant="outline" className="bg-primary/5 text-primary border-primary/20 text-xs font-semibold gap-1">
                          <Building2 className="h-3 w-3" />
                          {tenantDisplayName}
                        </Badge>

                        <span className="font-mono text-xs text-muted-foreground font-medium truncate">
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

                  <div className="flex items-center gap-1 shrink-0 text-muted-foreground group-hover:text-primary transition-colors">
                    <span className="text-xs font-medium">Chi tiết</span>
                    <ChevronRight className="h-4 w-4 group-hover:translate-x-0.5 transition-transform" />
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Card>

      {/* Dialog Detail View */}
      <Dialog open={!!selectedConvId} onOpenChange={() => setSelectedConvId(null)}>
        <DialogContent className="max-w-3xl max-h-[85vh] flex flex-col rounded-2xl border border-border/80 shadow-2xl backdrop-blur-xl p-6 overflow-hidden">
          <DialogHeader className="shrink-0 pb-2">
            <DialogTitle className="flex items-center gap-2 text-base font-semibold">
              <MessageSquare className="h-4 w-4 text-primary" />
              Chi tiết Phiên Hỏi & Đáp
              {selectedTenantId && (
                <Badge variant="outline" className="ml-2 bg-primary/10 text-primary border-primary/20 text-xs font-semibold gap-1">
                  <Building2 className="h-3 w-3" />
                  {tenantMap.get(selectedTenantId)?.name || selectedTenantId}
                </Badge>
              )}
            </DialogTitle>
            <DialogDescription className="font-mono text-xs">
              ID Phiên: {selectedConvId}
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
            <div className="space-y-3.5 py-2 overflow-y-auto max-h-[60vh] pr-2.5 scrollbar-thin">
              {messages.map((msg, idx) => {
                const isUser = msg.role === "user";
                const prevUserMsg = messages
                  .slice(0, idx)
                  .reverse()
                  .find((m) => m.role === "user");

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
                      <div className="flex items-center gap-2 flex-wrap">
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

                      <div className="flex items-center gap-2">
                        {!isUser && (
                          <Button
                            size="sm"
                            variant="outline"
                            className="h-6 px-2.5 text-[11px] font-medium text-amber-600 hover:text-amber-700 dark:text-amber-400 border-amber-500/30 bg-amber-500/10 hover:bg-amber-500/20 gap-1.5 transition-colors"
                            onClick={() => handleOpenFaqModal(prevUserMsg?.content || "", msg.content, msg.citations, selectedTenantId)}
                          >
                            <Sparkles className="h-3 w-3" /> Biến thành FAQ
                          </Button>
                        )}

                        {msg.created_at && (
                          <span className="text-[11px] text-muted-foreground font-mono">
                            {new Date(msg.created_at).toLocaleTimeString("vi-VN")}
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Content */}
                    <div className="text-sm leading-relaxed text-foreground">
                      {isUser ? (
                        <div className="whitespace-pre-wrap font-medium">{msg.content}</div>
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

      {/* FAQ Promote Dialog */}
      <Dialog open={faqModalOpen} onOpenChange={setFaqModalOpen}>
        <DialogContent className="max-w-xl max-h-[85vh] flex flex-col rounded-2xl border border-border/80 shadow-2xl backdrop-blur-xl p-6 overflow-hidden">
          <DialogHeader className="shrink-0 pb-2">
            <DialogTitle className="flex items-center gap-2 text-base font-semibold text-amber-600 dark:text-amber-400">
              <Sparkles className="h-4.5 w-4.5" />
              Tạo FAQ từ Lượt trả lời này
            </DialogTitle>
            <DialogDescription className="text-xs">
              Lưu câu hỏi & phản hồi này thành FAQ chuẩn. Chọn công ty được áp dụng FAQ bên dưới.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2 text-sm overflow-y-auto max-h-[55vh] pr-2.5 scrollbar-thin">
            {/* Multi-tenant Selection Grid */}
            <div className="space-y-2">
              <Label className="text-xs font-semibold flex items-center justify-between">
                <span className="flex items-center gap-1.5">
                  <Building2 className="h-3.5 w-3.5 text-primary" />
                  Áp dụng cho Công ty (Tenants):
                </span>
                <span className="text-[11px] text-muted-foreground font-normal">
                  (Đã chọn {faqSelectedTenants.length} công ty)
                </span>
              </Label>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 p-3 rounded-xl border border-border/60 bg-muted/20">
                {tenants.map((t) => {
                  const isChecked = faqSelectedTenants.includes(t.id);
                  return (
                    <label
                      key={t.id}
                      onClick={() => toggleFaqTenantSelection(t.id)}
                      className={`flex items-center justify-between p-2.5 rounded-lg border text-xs font-medium cursor-pointer transition-all ${
                        isChecked
                          ? "bg-primary/10 border-primary text-primary shadow-xs"
                          : "bg-card border-border/60 hover:bg-muted/50 text-foreground"
                      }`}
                    >
                      <div className="flex items-center gap-2 truncate">
                        <Building2 className="h-3.5 w-3.5 shrink-0 opacity-70" />
                        <span className="truncate">{t.name}</span>
                      </div>
                      {isChecked && <CheckCircle2 className="h-4 w-4 text-primary shrink-0" />}
                    </label>
                  );
                })}
              </div>
            </div>

            <div className="space-y-1.5">
              <Label className="text-xs font-semibold">Câu hỏi chuẩn (User Question)</Label>
              <Input
                value={faqQuestion}
                onChange={(e) => setFaqQuestion(e.target.value)}
                placeholder="Nhập câu hỏi chuẩn..."
                className="text-xs font-medium"
              />
            </div>

            <div className="space-y-1.5">
              <Label className="text-xs font-semibold">Câu hỏi biến thể (Tùy chọn)</Label>
              <Input
                value={faqVariants}
                onChange={(e) => setFaqVariants(e.target.value)}
                placeholder="Các câu tương tự, phân cách bằng dấu phẩy (ví dụ: ai tạo file, ai là người viết...)"
                className="text-xs"
              />
            </div>

            <div className="space-y-1.5">
              <Label className="text-xs font-semibold">Câu trả lời chuẩn (AI Answer)</Label>
              <Textarea
                value={faqAnswer}
                onChange={(e) => setFaqAnswer(e.target.value)}
                rows={6}
                className="text-xs font-mono leading-relaxed resize-y max-h-48"
              />
            </div>
          </div>

          <DialogFooter className="gap-2 pt-3 border-t border-border/50 shrink-0 mt-2">
            <Button variant="ghost" size="sm" onClick={() => setFaqModalOpen(false)}>
              Hủy
            </Button>
            <Button
              size="sm"
              onClick={handleCreateFaq}
              disabled={submittingFaq}
              className="bg-amber-600 hover:bg-amber-700 text-white gap-1.5"
            >
              {submittingFaq ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle2 className="h-3.5 w-3.5" />}
              Lưu thành FAQ cho {faqSelectedTenants.length} Công ty
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
