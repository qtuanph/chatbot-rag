"use client";

import { useEffect, useState, useMemo } from "react";
import { useSession } from "next-auth/react";
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
  Check,
  Building,
  Filter,
  Bot,
  User,
  Cpu,
  Brain,
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
import { TenantItem, Citation } from "@/types/api";

export interface ConversationItem {
  id: string;
  tenant_id: string;
  conversation_id: string;
  started_at?: string | null;
  last_message_at?: string | null;
  message_count: number;
}

export interface ConversationMessage {
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

interface ConversationAuditManagerProps {
  initialTenants?: TenantItem[];
  initialConversations?: ConversationItem[];
}

export function ConversationAuditManager({
  initialTenants = [],
  initialConversations = [],
}: ConversationAuditManagerProps) {
  const { data: session } = useSession();
  const isPlatformAdmin = session?.role === "platform_admin";

  const [conversations, setConversations] = useState<ConversationItem[]>(initialConversations);
  const [tenants, setTenants] = useState<TenantItem[]>(initialTenants);
  const [loading, setLoading] = useState(initialConversations.length === 0);
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
  const [faqCitations, setFaqCitations] = useState<Citation[]>([]);
  const [submittingFaq, setSubmittingFaq] = useState(false);

  // Load Tenants list
  const fetchTenants = async () => {
    if (!isPlatformAdmin) return;
    try {
      const data = await tenantsApi.list();
      setTenants(data || []);
    } catch (err: unknown) {
      console.error("Failed to load tenants list:", err);
    }
  };

  // Load Conversations list
  const fetchConversations = async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const tenantParam = filterTenantId !== "ALL" ? filterTenantId : undefined;
      const res = await conversationsApi.list(0, 50, tenantParam);
      setConversations(res.items || []);
    } catch (err: unknown) {
      if (!silent) {
        const msg = err instanceof Error ? err.message : "Lỗi kết nối";
        toast.error("Không thể tải nhật ký hội thoại: " + msg);
      }
    } finally {
      if (!silent) setLoading(false);
    }
  };

  useEffect(() => {
    if (isPlatformAdmin && tenants.length === 0) {
      void fetchTenants();
    }
  }, [isPlatformAdmin, tenants.length]);

  useEffect(() => {
    void fetchConversations();
  }, [filterTenantId]);

  // Real-time silent background polling for new incoming conversations
  useEffect(() => {
    const interval = setInterval(() => {
      if (document.visibilityState === "visible") {
        void fetchConversations(true);
      }
    }, 6000);

    return () => clearInterval(interval);
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
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Lỗi kết nối";
      toast.error("Không thể tải nội dung chi tiết: " + msg);
    } finally {
      setLoadingDetail(false);
    }
  };

  const handleOpenFaqModal = (question: string, answer: string, citations?: Citation[], tenantId?: string) => {
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
        if (prev.length === 1) return prev;
        return prev.filter((id) => id !== tenantId);
      } else {
        return [...prev, tenantId];
      }
    });
  };

  const handleCreateFaq = async () => {
    if (!faqQuestion.trim() || !faqAnswer.trim()) {
      toast.error("Câu hỏi và câu trả lời không được để trống.");
      return;
    }
    if (faqSelectedTenants.length === 0) {
      toast.error("Vui lòng chọn ít nhất 1 công ty/tenant.");
      return;
    }

    setSubmittingFaq(true);
    try {
      const variants = faqVariants
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);

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

      toast.success(`Đã tạo thành công FAQ cho ${successCount} công ty. Phản hồi sẽ được xử lý qua Redis Cache.`);
      setFaqModalOpen(false);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Lỗi hệ thống";
      toast.error("Không thể tạo FAQ: " + msg);
    } finally {
      setSubmittingFaq(false);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      {/* Header & Filter Controls */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <Brain className="h-6 w-6 text-primary shrink-0" />
            Nhật ký Hội thoại & Audit AI
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Quản lý lịch sử tương tác người dùng, giám sát độ trễ AI và khởi tạo FAQ từ các phản hồi chuẩn hóa.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Tenant Filter Dropdown (Platform Admin only) */}
          {isPlatformAdmin && (
            <div className="flex items-center gap-2">
              <Filter className="h-4 w-4 text-muted-foreground shrink-0" />
              <NativeSelect
                value={filterTenantId}
                onChange={(e) => setFilterTenantId(e.target.value)}
                className="w-56"
              >
                <NativeSelectOption value="ALL">Tất cả công ty (Tenants)</NativeSelectOption>
                {tenants.map((t) => (
                  <NativeSelectOption key={t.id} value={t.id}>
                    {t.name} ({t.slug})
                  </NativeSelectOption>
                ))}
              </NativeSelect>
            </div>
          )}

          <Button onClick={() => fetchConversations(false)} disabled={loading} variant="outline" size="sm" className="gap-2 shrink-0">
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} /> Làm mới
          </Button>
        </div>
      </div>

      {/* Conversations List Card */}
      <Card className="p-0 overflow-hidden border border-border shadow-none">
        {loading && conversations.length === 0 ? (
          <div className="p-12 text-center text-sm text-muted-foreground">
            <RefreshCw className="h-5 w-5 animate-spin mx-auto mb-2 text-primary" />
            Đang tải dữ liệu hội thoại...
          </div>
        ) : conversations.length === 0 ? (
          <div className="p-12 text-center text-sm text-muted-foreground">
            Không tìm thấy cuộc hội thoại nào cho bộ lọc đã chọn.
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
                  className="p-4 flex items-center justify-between hover:bg-muted/40 transition-colors cursor-pointer group"
                >
                  <div className="flex items-center gap-3.5 min-w-0">
                    <div className="size-9 rounded-md bg-muted flex items-center justify-center text-muted-foreground shrink-0">
                      <MessageSquare className="h-4 w-4" />
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <Badge variant="outline" className="text-xs font-semibold gap-1">
                          <Building className="h-3 w-3" />
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
                        <span className="flex items-center gap-1 font-mono">
                          <Clock className="h-3 w-3" />
                          Thời gian: {item.last_message_at ? new Date(item.last_message_at).toLocaleString("vi-VN") : "N/A"}
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-1 shrink-0 text-muted-foreground group-hover:text-foreground transition-colors">
                    <span className="text-xs font-medium">Chi tiết</span>
                    <ChevronRight className="h-4 w-4" />
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Card>

      {/* Dialog Detail View */}
      <Dialog open={!!selectedConvId} onOpenChange={() => setSelectedConvId(null)}>
        <DialogContent className="max-w-3xl max-h-[85vh] flex flex-col rounded-xl border border-border shadow-lg p-6 overflow-hidden">
          <DialogHeader className="shrink-0 pb-2">
            <DialogTitle className="flex items-center gap-2 text-base font-semibold">
              Chi tiết Phiên Hội thoại
              {selectedTenantId && (
                <Badge variant="outline" className="ml-2 text-xs font-semibold gap-1">
                  <Building className="h-3 w-3" />
                  {tenantMap.get(selectedTenantId)?.name || selectedTenantId}
                </Badge>
              )}
            </DialogTitle>
            <DialogDescription className="font-mono text-xs">
              Mã phiên: {selectedConvId}
            </DialogDescription>
          </DialogHeader>

          {loadingDetail ? (
            <div className="p-8 text-center text-sm text-muted-foreground">
              <RefreshCw className="h-5 w-5 animate-spin mx-auto mb-2 text-primary" />
              Đang tải danh sách tin nhắn...
            </div>
          ) : messages.length === 0 ? (
            <div className="p-8 text-center text-sm text-muted-foreground">Không có tin nhắn nào trong phiên này.</div>
          ) : (
            <div className="space-y-3.5 py-2 overflow-y-auto max-h-[60vh] pr-2 scrollbar-thin">
              {messages.map((msg, idx) => {
                const isUser = msg.role === "user";
                const prevUserMsg = messages
                  .slice(0, idx)
                  .reverse()
                  .find((m) => m.role === "user");

                return (
                  <div
                    key={msg.id}
                    className={`p-4 rounded-lg border text-sm ${
                      isUser ? "bg-muted/30 border-border/50 ml-6" : "bg-card border-border mr-6"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2 mb-2.5">
                      <div className="flex items-center gap-2 flex-wrap">
                        <Badge
                          variant={isUser ? "outline" : "default"}
                          className="text-[10px] h-4.5 font-semibold uppercase tracking-wider gap-1"
                        >
                          {isUser ? (
                            <>
                              <User className="h-3 w-3" /> User
                            </>
                          ) : (
                            <>
                              <Bot className="h-3 w-3" /> AI Assistant
                            </>
                          )}
                        </Badge>

                        {msg.is_cache_hit && (
                          <Badge variant="outline" className="text-[10px] h-4.5 font-medium gap-1 bg-amber-500/10 text-amber-600 border-amber-500/30">
                            <Zap className="h-3 w-3 text-amber-500" /> Cache HIT ({msg.cached_type || "L1"})
                          </Badge>
                        )}
                        {msg.no_answer && (
                          <Badge variant="destructive" className="text-[10px] h-4.5 gap-1">
                            <ShieldAlert className="h-3 w-3" /> Chưa đủ căn cứ
                          </Badge>
                        )}
                      </div>

                      <div className="flex items-center gap-2">
                        {!isUser && (
                          <Button
                            size="sm"
                            variant="outline"
                            className="h-6 px-2.5 text-[11px] font-medium gap-1 text-primary border-primary/30 hover:bg-primary/10 transition-colors"
                            onClick={() => handleOpenFaqModal(prevUserMsg?.content || "", msg.content, msg.citations, selectedTenantId)}
                          >
                            <Sparkles className="h-3.5 w-3.5 text-primary" /> Tạo FAQ từ AI
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
                          <BookOpen className="h-3.5 w-3.5 text-muted-foreground" /> Dẫn chứng ({msg.citations.length}):
                        </div>
                        <div className="flex flex-wrap gap-1.5">
                          {msg.citations.map((c, cIdx) => (
                            <Badge key={cIdx} variant="secondary" className="text-[11px] font-normal gap-1">
                              <FileText className="h-3 w-3" /> {c.title || "Tài liệu"} {c.page_range ? `(Trang ${c.page_range})` : ""}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Stats */}
                    {!isUser && (
                      <div className="mt-2.5 text-[11px] text-muted-foreground flex flex-wrap items-center gap-4 pt-2 border-t border-border/40 font-mono">
                        {msg.model_name && (
                          <span className="flex items-center gap-1">
                            <Cpu className="h-3 w-3 text-primary" /> Mô hình: {msg.model_name}
                          </span>
                        )}
                        {msg.latency_ms !== undefined && (
                          <span className="flex items-center gap-1">
                            <Clock className="h-3 w-3" /> Độ trễ: {msg.latency_ms.toFixed(0)}ms
                          </span>
                        )}
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
        <DialogContent className="max-w-xl max-h-[85vh] flex flex-col rounded-xl border border-border shadow-lg p-6 overflow-hidden">
          <DialogHeader className="shrink-0 pb-2">
            <DialogTitle className="text-base font-semibold flex items-center gap-2">
              <Sparkles className="h-4.5 w-4.5 text-primary" />
              Tạo FAQ từ Phản hồi AI
            </DialogTitle>
            <DialogDescription className="text-xs">
              Chuẩn hóa phản hồi của AI thành FAQ. Yêu cầu trùng khớp sẽ được xử lý qua Redis Cache.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2 text-sm overflow-y-auto max-h-[55vh] pr-2 scrollbar-thin">
            {/* Multi-tenant Selection Grid */}
            <div className="space-y-2">
              <Label className="text-xs font-semibold flex items-center justify-between">
                <span className="flex items-center gap-1.5">
                  <Building className="h-3.5 w-3.5 text-primary" />
                  Áp dụng cho các công ty (Tenants):
                </span>
                <span className="text-[11px] text-muted-foreground font-normal">
                  (Đã chọn {faqSelectedTenants.length} đơn vị)
                </span>
              </Label>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 p-3 rounded-lg border border-border bg-muted/20">
                {tenants.map((t) => {
                  const isChecked = faqSelectedTenants.includes(t.id);
                  return (
                    <label
                      key={t.id}
                      onClick={() => toggleFaqTenantSelection(t.id)}
                      className={`flex items-center justify-between p-2.5 rounded border text-xs font-medium cursor-pointer transition-all ${
                        isChecked
                          ? "bg-primary/10 border-primary text-primary"
                          : "bg-card border-border hover:bg-muted/50 text-foreground"
                      }`}
                    >
                      <div className="flex items-center gap-2 truncate">
                        <Building className="h-3.5 w-3.5 shrink-0 opacity-70" />
                        <span className="truncate">{t.name}</span>
                      </div>
                      {isChecked && <Check className="h-4 w-4 text-primary shrink-0" />}
                    </label>
                  );
                })}
              </div>
            </div>

            <div className="space-y-1.5">
              <Label className="text-xs font-semibold">Câu hỏi chuẩn</Label>
              <Input
                value={faqQuestion}
                onChange={(e) => setFaqQuestion(e.target.value)}
                placeholder="Nhập câu hỏi chuẩn hóa..."
                className="text-xs font-medium"
              />
            </div>

            <div className="space-y-1.5">
              <Label className="text-xs font-semibold">Biến thể câu hỏi (Phân cách bằng dấu phẩy)</Label>
              <Input
                value={faqVariants}
                onChange={(e) => setFaqVariants(e.target.value)}
                placeholder="Ví dụ: ai tao file, ai viet tai lieu..."
                className="text-xs"
              />
            </div>

            <div className="space-y-1.5">
              <Label className="text-xs font-semibold">Câu trả lời chuẩn từ AI</Label>
              <Textarea
                value={faqAnswer}
                onChange={(e) => setFaqAnswer(e.target.value)}
                rows={6}
                className="text-xs font-mono leading-relaxed resize-y max-h-48"
              />
            </div>
          </div>

          <DialogFooter className="gap-2 pt-3 border-t border-border shrink-0 mt-2">
            <Button variant="ghost" size="sm" onClick={() => setFaqModalOpen(false)}>
              Hủy
            </Button>
            <Button size="sm" onClick={handleCreateFaq} disabled={submittingFaq} className="gap-1.5">
              {submittingFaq ? (
                <RefreshCw className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Sparkles className="h-3.5 w-3.5" />
              )}
              Lưu FAQ cho {faqSelectedTenants.length} công ty
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
