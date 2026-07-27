"use client";

import { useCallback, useEffect, useState } from "react";
import { ArrowRight, Edit2, HelpCircle, Plus, RefreshCw, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { faqApi, tenantsApi } from "@/lib/api-client";
import { formatDateTimeVN } from "@/lib/format";
import type { EscalationItem, FaqItem, FaqCreateRequest, TenantItem } from "@/types/api";

type ModalMode = "create" | "edit" | "promote" | null;

interface FaqForm {
  question: string;
  answer: string;
  question_variants: string[];
}

const EMPTY_FORM: FaqForm = { question: "", answer: "", question_variants: [] };

interface FaqManagerProps {
  selectedTenantId?: string | null;
  tenantOptions?: TenantItem[];
}

export function FaqManager({ selectedTenantId = null, tenantOptions = [] }: FaqManagerProps) {
  const [activeTenantId, setActiveTenantId] = useState<string | null>(selectedTenantId);
  const [tenant, setTenant] = useState<TenantItem | null>(null);
  const [faqs, setFaqs] = useState<FaqItem[]>([]);
  const [escalations, setEscalations] = useState<EscalationItem[]>([]);
  const [loading, setLoading] = useState(true);

  const [modalMode, setModalMode] = useState<ModalMode>(null);
  const [selectedFaq, setSelectedFaq] = useState<FaqItem | null>(null);
  const [selectedEscalation, setSelectedEscalation] = useState<EscalationItem | null>(null);
  const [form, setForm] = useState<FaqForm>(EMPTY_FORM);
  const [variantInput, setVariantInput] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (tenantOptions.length > 0 && !activeTenantId) {
      setActiveTenantId(tenantOptions[0].id);
    }
  }, [tenantOptions, activeTenantId]);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      let targetTenantId = activeTenantId || selectedTenantId;
      if (!targetTenantId) {
        const myTenant = await tenantsApi.getMyTenant();
        setTenant(myTenant);
        targetTenantId = myTenant?.id || null;
      } else {
        const found = tenantOptions.find((t) => t.id === targetTenantId);
        setTenant(found || ({ id: targetTenantId } as TenantItem));
      }
      if (targetTenantId) {
        const [faqList, escList] = await Promise.all([
          faqApi.list(targetTenantId),
          faqApi.listEscalations(targetTenantId),
        ]);
        setFaqs(faqList);
        setEscalations(escList);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Không thể tải danh sách FAQ";
      toast.error(message);
    } finally {
      setLoading(false);
    }
  }, [activeTenantId, selectedTenantId, tenantOptions]);

  useEffect(() => {
    const timer = window.setTimeout(() => { void loadData(); }, 0);
    return () => window.clearTimeout(timer);
  }, [loadData]);

  const openCreate = () => {
    setForm(EMPTY_FORM);
    setVariantInput("");
    setSelectedFaq(null);
    setSelectedEscalation(null);
    setModalMode("create");
  };

  const openEdit = (faq: FaqItem) => {
    setSelectedFaq(faq);
    setForm({ question: faq.question, answer: faq.answer, question_variants: faq.question_variants ?? [] });
    setVariantInput("");
    setModalMode("edit");
  };

  const openPromote = (esc: EscalationItem) => {
    setSelectedEscalation(esc);
    setForm({ question: esc.question, answer: esc.answer ?? "", question_variants: [] });
    setVariantInput("");
    setModalMode("promote");
  };

  const closeModal = () => {
    setModalMode(null);
    setSelectedFaq(null);
    setSelectedEscalation(null);
  };

  const addVariant = () => {
    const v = variantInput.trim();
    if (v && !form.question_variants.includes(v)) {
      setForm((prev) => ({ ...prev, question_variants: [...prev.question_variants, v] }));
    }
    setVariantInput("");
  };

  const removeVariant = (idx: number) =>
    setForm((prev) => ({ ...prev, question_variants: prev.question_variants.filter((_, i) => i !== idx) }));

  const handleSubmit = useCallback(async () => {
    if (!form.question.trim() || !form.answer.trim()) {
      toast.error("Vui lòng điền đầy đủ câu hỏi và câu trả lời");
      return;
    }
    if (!tenant?.id) return;
    setSubmitting(true);
    try {
      const payload: FaqCreateRequest = {
        question: form.question.trim(),
        answer: form.answer.trim(),
        question_variants: form.question_variants,
      };

      if (modalMode === "create") {
        await faqApi.create(tenant.id, payload);
        toast.success("Đã tạo FAQ mới và đồng bộ cache thành công");
      } else if (modalMode === "edit" && selectedFaq) {
        await faqApi.update(selectedFaq.id, payload);
        toast.success("Đã cập nhật FAQ và làm mới cache thành công");
      } else if (modalMode === "promote" && selectedEscalation) {
        await faqApi.promoteEscalation(selectedEscalation.id, payload);
        toast.success("Đã duyệt câu hỏi thành FAQ chính thức");
      }
      closeModal();
      void loadData();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Thao tác thất bại";
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  }, [form, tenant, modalMode, selectedFaq, selectedEscalation, loadData]);

  const handleDelete = useCallback(async (faqId: string) => {
    if (!confirm("Bạn có chắc chắn muốn xóa bài FAQ này? Câu trả lời nhanh sẽ bị gỡ khỏi cache ngay lập tức.")) return;
    try {
      await faqApi.delete(faqId);
      toast.success("Đã xóa FAQ và xóa khỏi cache");
      void loadData();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Không thể xóa FAQ";
      toast.error(message);
    }
  }, [loadData]);

  const modalTitle =
    modalMode === "create" ? "Thêm bài FAQ mới" :
    modalMode === "edit" ? "Chỉnh sửa bài FAQ" :
    "Duyệt câu hỏi thành FAQ";

  const submitLabel = modalMode === "create" ? "Tạo & Xuất bản" : modalMode === "edit" ? "Lưu thay đổi" : "Duyệt & Xuất bản";

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <h1 className="text-2xl font-bold">Quản lý FAQ &amp; Hỗ trợ</h1>
          <p className="text-sm text-muted-foreground">
            Câu hỏi được duyệt sẽ trả lời tức thì (&lt;1ms, không tốn chi phí AI) — bỏ qua toàn bộ pipeline LLM.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {tenantOptions.length > 0 && (
            <select
              className="h-9 rounded-xl border bg-background px-3 py-1 text-sm font-medium shadow-sm"
              value={activeTenantId || ""}
              onChange={(e) => setActiveTenantId(e.target.value)}
            >
              {tenantOptions.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          )}
          <Button className="rounded-xl" variant="outline" onClick={loadData} disabled={loading}>
            <RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            Làm mới
          </Button>
          <Button className="rounded-xl" onClick={openCreate}>
            <Plus className="mr-2 h-4 w-4" /> Thêm FAQ mới
          </Button>
        </div>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="published">
        <TabsList>
          <TabsTrigger value="published">
            FAQ đã xuất bản ({faqs.length})
          </TabsTrigger>
          <TabsTrigger value="escalations">
            Câu hỏi chờ duyệt ({escalations.length})
          </TabsTrigger>
        </TabsList>

        {/* Tab 1: Published FAQs */}
        <TabsContent value="published" className="mt-4">
          {loading ? (
            <div className="text-sm text-muted-foreground">Đang tải danh sách FAQ...</div>
          ) : faqs.length === 0 ? (
            <div className="flex flex-col items-center gap-3 rounded-xl border border-dashed p-8 text-center">
              <HelpCircle className="h-8 w-8 text-muted-foreground/50" />
              <div>
                <p className="text-sm font-medium">Chưa có bài FAQ nào được xuất bản</p>
                <p className="text-xs text-muted-foreground">Bấm &quot;Thêm FAQ mới&quot; để tạo câu hỏi thường gặp.</p>
              </div>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="pr-4 text-xs text-muted-foreground">Câu hỏi chính</TableHead>
                  <TableHead className="pr-4 text-xs text-muted-foreground">Câu hỏi biến thể</TableHead>
                  <TableHead className="pr-4 text-xs text-muted-foreground">Câu trả lời</TableHead>
                  <TableHead className="pr-4 text-xs text-muted-foreground">Cập nhật</TableHead>
                  <TableHead className="text-right text-xs text-muted-foreground">Thao tác</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {faqs.map((faq) => (
                  <TableRow key={faq.id}>
                    <TableCell className="pr-4 font-medium">{faq.question}</TableCell>
                    <TableCell className="pr-4">
                      <div className="flex flex-wrap gap-1">
                        {(faq.question_variants ?? []).length > 0 ? (
                          (faq.question_variants ?? []).map((v, idx) => (
                            <Badge key={idx} variant="secondary" className="text-xs">
                              {v}
                            </Badge>
                          ))
                        ) : (
                          <span className="text-xs italic text-muted-foreground">Không có</span>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="max-w-xs pr-4">
                      <p className="line-clamp-2 text-sm text-muted-foreground">{faq.answer}</p>
                    </TableCell>
                    <TableCell className="pr-4 text-sm text-muted-foreground">
                      {formatDateTimeVN(faq.updated_at)}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-2">
                        <Tooltip>
                          <TooltipTrigger
                            render={
                              <Button
                                size="icon"
                                variant="outline"
                                className="rounded-xl"
                                onClick={() => openEdit(faq)}
                              >
                                <Edit2 className="h-4 w-4" />
                              </Button>
                            }
                          />
                          <TooltipContent>Chỉnh sửa FAQ</TooltipContent>
                        </Tooltip>
                        <Tooltip>
                          <TooltipTrigger
                            render={
                              <Button
                                size="icon"
                                variant="destructive"
                                className="rounded-xl"
                                onClick={() => handleDelete(faq.id)}
                              >
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            }
                          />
                          <TooltipContent>Xóa FAQ</TooltipContent>
                        </Tooltip>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </TabsContent>

        {/* Tab 2: Open Escalations */}
        <TabsContent value="escalations" className="mt-4">
          {loading ? (
            <div className="text-sm text-muted-foreground">Đang tải câu hỏi chờ duyệt...</div>
          ) : escalations.length === 0 ? (
            <div className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">
              Không có câu hỏi nào đang chờ duyệt.
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="pr-4 text-xs text-muted-foreground">Câu hỏi của người dùng</TableHead>
                  <TableHead className="pr-4 text-xs text-muted-foreground">Thời gian</TableHead>
                  <TableHead className="text-right text-xs text-muted-foreground">Thao tác</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {escalations.map((esc) => (
                  <TableRow key={esc.id}>
                    <TableCell className="pr-4 font-medium">{esc.question}</TableCell>
                    <TableCell className="pr-4 text-sm text-muted-foreground">
                      {formatDateTimeVN(esc.created_at)}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        size="sm"
                        variant="outline"
                        className="rounded-xl"
                        onClick={() => openPromote(esc)}
                      >
                        Duyệt thành FAQ
                        <ArrowRight className="ml-1.5 h-3.5 w-3.5" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </TabsContent>
      </Tabs>

      {/* Dialog: Create / Edit / Promote */}
      <Dialog open={!!modalMode} onOpenChange={(open) => !open && closeModal()}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>{modalTitle}</DialogTitle>
            <DialogDescription>
              Nhập câu hỏi chuẩn và câu trả lời chính thức. Thêm các biến thể câu hỏi để tăng tỷ lệ khớp tự động.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 py-2">
            <div className="grid gap-2">
              <Label htmlFor="faq-question">Câu hỏi chính</Label>
              <Input
                id="faq-question"
                placeholder="Ví dụ: Quy trình xin nghỉ phép như thế nào?"
                value={form.question}
                onChange={(e) => setForm((prev) => ({ ...prev, question: e.target.value }))}
              />
            </div>

            <div className="grid gap-2">
              <Label>Câu hỏi biến thể (tùy chọn)</Label>
              <div className="flex gap-2">
                <Input
                  placeholder="Nhập biến thể rồi nhấn Thêm hoặc Enter"
                  value={variantInput}
                  onChange={(e) => setVariantInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      addVariant();
                    }
                  }}
                />
                <Button type="button" variant="outline" className="shrink-0" onClick={addVariant}>
                  Thêm
                </Button>
              </div>
              {form.question_variants.length > 0 && (
                <div className="flex flex-wrap gap-1 pt-1">
                  {form.question_variants.map((v, idx) => (
                    <Badge
                      key={idx}
                      variant="secondary"
                      className="cursor-pointer text-xs"
                      onClick={() => removeVariant(idx)}
                    >
                      {v} ×
                    </Badge>
                  ))}
                </div>
              )}
            </div>

            <div className="grid gap-2">
              <Label htmlFor="faq-answer">Câu trả lời chính thức</Label>
              <Textarea
                id="faq-answer"
                rows={4}
                placeholder="Nhập nội dung hướng dẫn đầy đủ, chính xác..."
                value={form.answer}
                onChange={(e) => setForm((prev) => ({ ...prev, answer: e.target.value }))}
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={closeModal} disabled={submitting}>
              Hủy
            </Button>
            <Button onClick={handleSubmit} disabled={submitting}>
              {submitting ? "Đang lưu..." : submitLabel}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
