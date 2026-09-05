"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useSession } from "next-auth/react";
import { Check, Edit2, Plus, RefreshCw, Trash2, MoreHorizontal, Copy } from "lucide-react";
import { toast } from "sonner";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { FieldDescription } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { TenantSelect } from "@/components/tenants/tenant-select";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  DataTable,
  DataTableSortHeader,
  createColumnHelper,
  type DataTableFeatures,
} from "@/components/ui/data-table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { faqApi, tenantsApi } from "@/lib/api-client";
import { formatDateVN, formatDateTimeVN } from "@/lib/format";
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
  initialFaqs?: FaqItem[];
  initialEscalations?: EscalationItem[];
}

export function FaqManager({
  selectedTenantId = null,
  tenantOptions = [],
  initialFaqs = [],
  initialEscalations = [],
}: FaqManagerProps) {
  const { data: session } = useSession();
  const isPlatformAdmin = session?.role === "platform_admin";

  const [activeTenantId, setActiveTenantId] = useState<string | null>(selectedTenantId || (tenantOptions[0]?.id ?? null));
  const [tenant, setTenant] = useState<TenantItem | null>(null);
  const [faqs, setFaqs] = useState<FaqItem[]>(initialFaqs);
  const [escalations, setEscalations] = useState<EscalationItem[]>(initialEscalations);
  const [loading, setLoading] = useState(initialFaqs.length === 0 && initialEscalations.length === 0);

  const [modalMode, setModalMode] = useState<ModalMode>(null);
  const [selectedFaq, setSelectedFaq] = useState<FaqItem | null>(null);
  const [selectedEscalation, setSelectedEscalation] = useState<EscalationItem | null>(null);
  const [form, setForm] = useState<FaqForm>(EMPTY_FORM);
  const [variantInput, setVariantInput] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // Delete confirmation state
  const [deletingFaq, setDeletingFaq] = useState<FaqItem | null>(null);

  useEffect(() => {
    if (tenantOptions.length > 0 && !activeTenantId) {
      setActiveTenantId(tenantOptions[0].id);
    }
  }, [tenantOptions, activeTenantId]);

  const loadData = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      let targetTenantId = activeTenantId || selectedTenantId;
      if (!targetTenantId) {
        if (isPlatformAdmin) {
          if (!silent) setLoading(false);
          return;
        }
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
      if (!silent) {
        const message = error instanceof Error ? error.message : "Không thể tải danh sách FAQ";
        toast.error(message);
      }
    } finally {
      if (!silent) setLoading(false);
    }
  }, [activeTenantId, selectedTenantId, tenantOptions, isPlatformAdmin]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  // Real-time silent background polling
  useEffect(() => {
    const interval = setInterval(() => {
      if (document.visibilityState === "visible") {
        void loadData(true);
      }
    }, 10000);

    return () => clearInterval(interval);
  }, [loadData]);


  const openCreate = useCallback(() => {
    setForm(EMPTY_FORM);
    setVariantInput("");
    setSelectedFaq(null);
    setSelectedEscalation(null);
    setModalMode("create");
  }, []);

  const openEdit = useCallback((faq: FaqItem) => {
    setSelectedFaq(faq);
    setForm({ question: faq.question, answer: faq.answer, question_variants: faq.question_variants ?? [] });
    setVariantInput("");
    setModalMode("edit");
  }, []);

  const openPromote = useCallback((esc: EscalationItem) => {
    setSelectedEscalation(esc);
    setForm({ question: esc.question, answer: esc.answer ?? "", question_variants: [] });
    setVariantInput("");
    setModalMode("promote");
  }, []);

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
    try {
      await faqApi.delete(faqId);
      toast.success("Đã xóa FAQ và xóa khỏi cache");
      setDeletingFaq(null);
      void loadData();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Không thể xóa FAQ";
      toast.error(message);
    }
  }, [loadData]);

  const handleRejectEscalation = useCallback(async (_escId: string) => {
    try {
      // TODO: implement reject escalation endpoint
      toast.error("Chức năng chưa được hỗ trợ");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Không thể từ chối câu hỏi";
      toast.error(message);
    }
  }, []);

  const modalTitle =
    modalMode === "create" ? "Thêm bài FAQ mới" :
    modalMode === "edit" ? "Chỉnh sửa bài FAQ" :
    "Duyệt câu hỏi thành FAQ";

  const submitLabel = modalMode === "create" ? "Tạo & Xuất bản" : modalMode === "edit" ? "Lưu thay đổi" : "Duyệt & Xuất bản";

  const faqColumns = useMemo(() => {
    const columnHelper = createColumnHelper<DataTableFeatures, FaqItem>();

    return columnHelper.columns([
      columnHelper.accessor("question", {
        meta: { title: "Câu hỏi chính" },
        header: ({ column }) => <DataTableSortHeader column={column} title="Câu hỏi chính" />,
        cell: ({ row }) => <span className="font-medium text-xs text-foreground">{row.original.question}</span>,
      }),
      columnHelper.accessor("question_variants", {
        meta: { title: "Biến thể" },
        header: ({ column }) => <DataTableSortHeader column={column} title="Biến thể" />,
        cell: ({ row }) => {
          const variants = row.original.question_variants ?? [];
          if (variants.length === 0) {
            return <span className="text-muted-foreground text-xs">—</span>;
          }
          if (variants.length === 1) {
            return (
              <Badge variant="secondary" className="text-[11px] max-w-[160px] truncate">
                {variants[0]}
              </Badge>
            );
          }
          return (
            <Tooltip>
              <TooltipTrigger>
                <div className="flex items-center gap-1 cursor-default">
                  <Badge variant="secondary" className="text-[11px] max-w-[140px] truncate">
                    {variants[0]}
                  </Badge>
                  <Badge variant="outline" className="text-[10px]">
                    +{variants.length - 1}
                  </Badge>
                </div>
              </TooltipTrigger>
              <TooltipContent className="max-w-xs">
                {variants.join(" • ")}
              </TooltipContent>
            </Tooltip>
          );
        },
      }),
      columnHelper.accessor("answer", {
        meta: { title: "Câu trả lời" },
        header: ({ column }) => <DataTableSortHeader column={column} title="Câu trả lời" />,
        cell: ({ row }) => (
          <Tooltip>
            <TooltipTrigger>
              <p className="line-clamp-1 text-xs text-muted-foreground max-w-xs cursor-default">{row.original.answer}</p>
            </TooltipTrigger>
            <TooltipContent className="max-w-md whitespace-pre-wrap text-xs">
              {row.original.answer}
            </TooltipContent>
          </Tooltip>
        ),
      }),
      columnHelper.accessor("updated_at", {
        meta: { title: "Cập nhật" },
        header: ({ column }) => <DataTableSortHeader column={column} title="Cập nhật" />,
        cell: ({ row }) => (
          <Tooltip>
            <TooltipTrigger>
              <span className="text-xs text-muted-foreground font-mono cursor-default">{formatDateVN(row.original.updated_at)}</span>
            </TooltipTrigger>
            <TooltipContent>{formatDateTimeVN(row.original.updated_at)}</TooltipContent>
          </Tooltip>
        ),
      }),
      columnHelper.display({
        id: "actions",
        enableHiding: false,
        cell: ({ row }) => {
          const faq = row.original;
          return (
            <div className="flex justify-end">
              <DropdownMenu>
                <DropdownMenuTrigger
                  render={
                    <Button variant="ghost" className="h-8 w-8 p-0">
                      <span className="sr-only">Mở menu</span>
                      <MoreHorizontal className="h-4 w-4" />
                    </Button>
                  }
                />
                <DropdownMenuContent align="end">
                  <DropdownMenuGroup>
                    <DropdownMenuItem onClick={() => openEdit(faq)}>
                      <Edit2 className="mr-2 h-4 w-4" /> Chỉnh sửa
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      onClick={() => {
                        void navigator.clipboard.writeText(faq.question);
                        toast.success("Đã sao chép câu hỏi");
                      }}
                    >
                      <Copy className="mr-2 h-4 w-4" /> Sao chép câu hỏi
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem
                      className="text-destructive focus:text-destructive"
                      onClick={() => setDeletingFaq(faq)}
                    >
                      <Trash2 className="mr-2 h-4 w-4" /> Xóa bài FAQ
                    </DropdownMenuItem>
                  </DropdownMenuGroup>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          );
        },
      }),
    ]);
  }, [openEdit]);

  const escalationColumns = useMemo(() => {
    const columnHelper = createColumnHelper<DataTableFeatures, EscalationItem>();

    return columnHelper.columns([
      columnHelper.accessor("question", {
        meta: { title: "Câu hỏi người dùng" },
        header: ({ column }) => <DataTableSortHeader column={column} title="Câu hỏi của người dùng" />,
        cell: ({ row }) => <span className="font-medium text-xs text-foreground">{row.original.question}</span>,
      }),
      columnHelper.accessor("created_at", {
        meta: { title: "Thời gian" },
        header: ({ column }) => <DataTableSortHeader column={column} title="Thời gian" />,
        cell: ({ row }) => (
          <Tooltip>
            <TooltipTrigger>
              <span className="text-xs text-muted-foreground font-mono cursor-default">{formatDateVN(row.original.created_at)}</span>
            </TooltipTrigger>
            <TooltipContent>{formatDateTimeVN(row.original.created_at)}</TooltipContent>
          </Tooltip>
        ),
      }),
      columnHelper.display({
        id: "actions",
        enableHiding: false,
        cell: ({ row }) => {
          const esc = row.original;
          return (
            <div className="flex justify-end">
              <DropdownMenu>
                <DropdownMenuTrigger
                  render={
                    <Button variant="ghost" className="h-8 w-8 p-0">
                      <span className="sr-only">Mở menu</span>
                      <MoreHorizontal className="h-4 w-4" />
                    </Button>
                  }
                />
                <DropdownMenuContent align="end">
                  <DropdownMenuGroup>
                    <DropdownMenuItem onClick={() => openPromote(esc)}>
                      <Check className="mr-2 h-4 w-4 text-emerald-600" /> Duyệt thành FAQ
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      onClick={() => {
                        void navigator.clipboard.writeText(esc.question);
                        toast.success("Đã sao chép câu hỏi");
                      }}
                    >
                      <Copy className="mr-2 h-4 w-4" /> Sao chép câu hỏi
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem
                      className="text-destructive focus:text-destructive"
                      onClick={() => handleRejectEscalation(esc.id)}
                    >
                      <Trash2 className="mr-2 h-4 w-4" /> Từ chối câu hỏi
                    </DropdownMenuItem>
                  </DropdownMenuGroup>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          );
        },
      }),
    ]);
  }, [handleRejectEscalation, openPromote]);

  return (
    <TooltipProvider>
      <div className="flex flex-col gap-6">
        {/* Header */}
        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div>
            <h1 className="text-2xl font-bold">Quản lý FAQ &amp; Hỗ trợ</h1>
            <p className="text-sm text-muted-foreground">
              Câu hỏi được duyệt sẽ phản hồi tức thì, tiết kiệm chi phí — bỏ qua toàn bộ pipeline LLM.
            </p>
          </div>
        <div className="flex items-center gap-2">
          {tenantOptions.length > 0 && (
            <TenantSelect
              tenants={tenantOptions}
              value={activeTenantId}
              onValueChange={(val) => setActiveTenantId(val || (tenantOptions[0]?.id ?? null))}
              className="w-56"
            />
          )}
          <Button className="rounded-xl" variant="outline" onClick={() => loadData(false)} disabled={loading}>
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
          {loading && faqs.length === 0 ? (
            <div className="space-y-3 py-4">
              <Skeleton className="h-10 w-full rounded-xl" />
              <Skeleton className="h-16 w-full rounded-xl" />
              <Skeleton className="h-16 w-full rounded-xl" />
            </div>
          ) : (
            <DataTable
              columns={faqColumns}
              data={faqs}
              searchKey="question"
              searchPlaceholder="Lọc theo câu hỏi FAQ..."
              enablePagination
              enableColumnVisibility
              emptyMessage={
                <div className="py-6 text-center">
                  <p className="text-sm font-medium">Chưa có bài FAQ nào</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    Bấm &quot;Thêm FAQ mới&quot; để tạo các câu hỏi và câu trả lời chuẩn cho doanh nghiệp.
                  </p>
                </div>
              }
            />
          )}
        </TabsContent>

        {/* Tab 2: Open Escalations */}
        <TabsContent value="escalations" className="mt-4">
          {loading && escalations.length === 0 ? (
            <div className="space-y-3 py-4">
              <Skeleton className="h-10 w-full rounded-xl" />
              <Skeleton className="h-14 w-full rounded-xl" />
              <Skeleton className="h-14 w-full rounded-xl" />
            </div>
          ) : (
            <DataTable
              columns={escalationColumns}
              data={escalations}
              searchKey="question"
              searchPlaceholder="Lọc theo câu hỏi người dùng..."
              enablePagination
              enableColumnVisibility
              emptyMessage="Không có câu hỏi nào đang chờ duyệt."
            />
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
              <FieldDescription>Nhập câu hỏi chuẩn mà khách hàng/người dùng thường thắc mắc.</FieldDescription>
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
              <FieldDescription>Các câu hỏi tương đương giúp AI khớp câu trả lời nhanh chính xác hơn.</FieldDescription>
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
              <FieldDescription>Nội dung câu trả lời chính thức. Hệ thống sẽ trả về ngay trong ~20ms mà không tốn chi phí gọi LLM.</FieldDescription>
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

      {/* Delete FAQ Confirmation Alert Dialog */}
      <AlertDialog open={!!deletingFaq} onOpenChange={(open) => !open && setDeletingFaq(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Xác nhận xóa FAQ</AlertDialogTitle>
            <AlertDialogDescription>
              Bạn có chắc chắn muốn xóa bài FAQ <span className="font-semibold text-foreground">&quot;{deletingFaq?.question}&quot;</span>?
              Hành động này sẽ gỡ câu hỏi khỏi danh mục tri thức và tự động dọn sạch cache FAQ trong bộ nhớ Redis.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Hủy</AlertDialogCancel>
            <AlertDialogAction
              className={buttonVariants({ variant: "destructive" })}
              onClick={async () => {
                if (deletingFaq) {
                  await handleDelete(deletingFaq.id);
                }
              }}
            >
              Xóa FAQ
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      </div>
    </TooltipProvider>
  );
}
