"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Copy, FileUp, Globe, MoreHorizontal, RefreshCw, RotateCcw, ShieldCheck, Trash2, WandSparkles } from "lucide-react";
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
import { Checkbox } from "@/components/ui/checkbox";
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
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
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
import { documentsApi } from "@/lib/api-client";
import { formatBytes, formatDateVN, formatDateTimeVN, formatNumber } from "@/lib/format";
import { DocumentListResponseSchema } from "@/lib/schemas";
import type { DocumentSummary, TenantBrief, TenantItem } from "@/types/api";

interface DocumentCatalogProps {
  readOnly?: boolean;
  tenantOptions?: TenantItem[];
  selectedTenantId?: string | null;
  initialDocuments?: DocumentSummary[];
}

export function DocumentCatalog({
  readOnly = false,
  tenantOptions = [],
  selectedTenantId = null,
  initialDocuments = [],
}: DocumentCatalogProps) {
  const [documents, setDocuments] = useState<DocumentSummary[]>(initialDocuments);
  const [loading, setLoading] = useState(initialDocuments.length === 0);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Access Permission Modal state
  const [accessDoc, setAccessDoc] = useState<DocumentSummary | null>(null);
  const [selectedTenantIds, setSelectedTenantIds] = useState<string[]>([]);
  const [savingAccess, setSavingAccess] = useState(false);

  // Delete confirmation state
  const [deletingDoc, setDeletingDoc] = useState<DocumentSummary | null>(null);

  const canUpload = !readOnly;
  const effectiveTenantId = selectedTenantId || undefined;

  const hasRunningDocuments = documents.some((document) =>
    ["queued", "processing", "retrying", "rechunking", "deleting"].includes((document.status || "").toLowerCase()) ||
    ["queued", "uploading", "chunking", "embedding", "indexing", "retrying", "rechunking", "deleting"].includes(
      (document.stage || "").toLowerCase(),
    ),
  );

  const isRetryAvailable = useCallback((document: DocumentSummary) => {
    const status = (document.status || "").toLowerCase();
    const stage = (document.stage || "").toLowerCase();
    return status === "failed" || stage === "failed";
  }, []);

  const isRechunkAvailable = useCallback((document: DocumentSummary) => {
    const status = (document.status || "").toLowerCase();
    return status === "ready";
  }, []);

  const loadDocuments = useCallback(async () => {
    try {
      setLoading(true);
      const result = await documentsApi.list(effectiveTenantId);
      setDocuments(result.items);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Không thể tải danh sách tài liệu";
      toast.error(message);
    } finally {
      setLoading(false);
    }
  }, [effectiveTenantId]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadDocuments();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadDocuments]);

  useEffect(() => {
    if (typeof EventSource === "undefined") {
      return;
    }

    const stream = documentsApi.streamList(effectiveTenantId);

    stream.addEventListener("documents", (event) => {
      try {
        const rawPayload = JSON.parse(event.data) as unknown;
        const parsedPayload = DocumentListResponseSchema.safeParse(rawPayload);
        if (!parsedPayload.success) {
          console.warn("Document SSE payload không hợp lệ");
          return;
        }

        setDocuments(parsedPayload.data.items);
        setLoading(false);
      } catch (error) {
        console.error("Không thể parse document stream payload", error);
      }
    });

    stream.onerror = () => {
      console.warn("Document SSE stream gặp lỗi tạm thời, trình duyệt sẽ tự reconnect.");
    };

    return () => {
      stream.close();
    };
  }, [effectiveTenantId]);

  const handleUpload = useCallback(
    async (event: React.ChangeEvent<HTMLInputElement>) => {
      const files = Array.from(event.target.files || []);
      if (files.length === 0) return;

      try {
        setUploading(true);
        for (const file of files) {
          await documentsApi.upload(file);
        }
        toast.success("Đã đưa tài liệu vào hàng chờ xử lý");
        await loadDocuments();
      } catch (error) {
        const message = error instanceof Error ? error.message : "Không thể upload tài liệu";
        toast.error(message);
      } finally {
        event.target.value = "";
        setUploading(false);
      }
    },
    [loadDocuments],
  );

  const handleDelete = useCallback(
    async (documentId: string) => {
      try {
        await documentsApi.delete(documentId);
        toast.success("Đã đưa tài liệu vào hàng chờ xóa");
        await loadDocuments();
      } catch (error) {
        const message = error instanceof Error ? error.message : "Không thể xóa tài liệu";
        toast.error(message);
      }
    },
    [loadDocuments],
  );

  const handleRetry = useCallback(
    async (documentId: string) => {
      try {
        await documentsApi.retry(documentId);
        toast.success("Đã đưa tài liệu vào hàng chờ retry");
        await loadDocuments();
      } catch (error) {
        const message = error instanceof Error ? error.message : "Không thể retry tài liệu";
        toast.error(message);
      }
    },
    [loadDocuments],
  );

  const handleRechunk = useCallback(
    async (documentId: string) => {
      try {
        await documentsApi.rechunk(documentId);
        toast.success("Đã đưa tài liệu vào hàng chờ rechunk");
        await loadDocuments();
      } catch (error) {
        const message = error instanceof Error ? error.message : "Không thể rechunk tài liệu";
        toast.error(message);
      }
    },
    [loadDocuments],
  );

  const openAccessModal = useCallback(async (document: DocumentSummary) => {
    setAccessDoc(document);
    try {
      const res = await documentsApi.getAccess(document.document_id);
      setSelectedTenantIds(res.tenants.map((t: TenantBrief) => t.id));
    } catch {
      setSelectedTenantIds((document.allowed_tenants || []).map((t: TenantBrief) => t.id));
    }
  }, []);

  const handleSaveAccess = useCallback(async () => {
    if (!accessDoc) return;
    try {
      setSavingAccess(true);
      await documentsApi.setAccess(accessDoc.document_id, selectedTenantIds);
      toast.success("Cập nhật phân quyền tài liệu thành công");
      setAccessDoc(null);
      await loadDocuments();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Không thể lưu phân quyền";
      toast.error(message);
    } finally {
      setSavingAccess(false);
    }
  }, [accessDoc, selectedTenantIds, loadDocuments]);

  const toggleTenantSelection = (tenantId: string) => {
    setSelectedTenantIds((prev) =>
      prev.includes(tenantId) ? prev.filter((id) => id !== tenantId) : [...prev, tenantId]
    );
  };

  const columns = useMemo(() => {
    const columnHelper = createColumnHelper<DataTableFeatures, DocumentSummary>();

    return columnHelper.columns([
      columnHelper.accessor("file_name", {
        meta: { title: "Tên file" },
        header: ({ column }) => <DataTableSortHeader column={column} title="Tên file" />,
        cell: ({ row }) => (
          <div>
            <div className="font-medium text-foreground text-xs">{row.original.file_name}</div>
            <div className="text-[11px] text-muted-foreground font-mono">
              v{row.original.version} • {row.original.file_type}
            </div>
          </div>
        ),
      }),
      columnHelper.accessor("allowed_tenants", {
        meta: { title: "Phân quyền" },
        header: ({ column }) => <DataTableSortHeader column={column} title="Phân quyền" />,
        cell: ({ row }) => {
          const tenants = row.original.allowed_tenants;
          if (!tenants || tenants.length === 0) {
            return (
              <Tooltip>
                <TooltipTrigger>
                  <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                    <Globe className="h-3.5 w-3.5 text-muted-foreground/70" /> Tất cả
                  </span>
                </TooltipTrigger>
                <TooltipContent>Tất cả các tenant đều có quyền truy cập</TooltipContent>
              </Tooltip>
            );
          }
          if (tenants.length === 1) {
            return (
              <Badge variant="secondary" className="text-[11px]">
                {tenants[0].name}
              </Badge>
            );
          }
          return (
            <Tooltip>
              <TooltipTrigger>
                <div className="flex items-center gap-1 cursor-default">
                  <Badge variant="secondary" className="text-[11px]">
                    {tenants[0].name}
                  </Badge>
                  <Badge variant="outline" className="text-[10px]">
                    +{tenants.length - 1}
                  </Badge>
                </div>
              </TooltipTrigger>
              <TooltipContent>
                {tenants.map((t) => t.name).join(", ")}
              </TooltipContent>
            </Tooltip>
          );
        },
      }),
      columnHelper.accessor("status", {
        meta: { title: "Trạng thái" },
        header: ({ column }) => <DataTableSortHeader column={column} title="Trạng thái" />,
        cell: ({ row }) => {
          const doc = row.original;
          return doc.status === "ready" ? (
            <Badge variant="outline" className="border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 gap-1.5 font-medium text-xs">
              <span className="pulse-dot-active" /> Sẵn sàng
            </Badge>
          ) : doc.status === "failed" ? (
            <Badge variant="destructive" className="text-xs">
              Thất bại
            </Badge>
          ) : (
            <Badge variant="outline" className="border-amber-500/30 bg-amber-500/10 text-amber-600 dark:text-amber-400 gap-1.5 font-medium text-xs">
              <span className="pulse-dot-amber" /> Đang nạp
            </Badge>
          );
        },
      }),
      columnHelper.accessor("stage", {
        meta: { title: "Giai đoạn" },
        header: ({ column }) => <DataTableSortHeader column={column} title="Giai đoạn" />,
        cell: ({ row }) => <span className="font-mono text-xs capitalize text-muted-foreground">{row.original.stage || "—"}</span>,
      }),
      columnHelper.accessor("progress_percent", {
        meta: { title: "Tiến độ" },
        header: ({ column }) => <DataTableSortHeader column={column} title="Tiến độ" />,
        cell: ({ row }) => {
          const doc = row.original;
          return (
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs font-medium">{doc.progress_percent}%</span>
              {doc.status !== "ready" && doc.status !== "failed" && (
                <Progress value={doc.progress_percent} className="w-16 h-1.5" />
              )}
            </div>
          );
        },
      }),
      columnHelper.accessor("file_size", {
        meta: { title: "Kích thước" },
        header: ({ column }) => <DataTableSortHeader column={column} title="Kích thước" />,
        cell: ({ row }) => (
          <Tooltip>
            <TooltipTrigger>
              <span className="font-mono text-xs cursor-default">{formatBytes(row.original.file_size)}</span>
            </TooltipTrigger>
            <TooltipContent>{formatNumber(row.original.file_size)} Bytes</TooltipContent>
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
          if (readOnly) return null;
          const document = row.original;
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
                    {tenantOptions.length > 0 && (
                      <DropdownMenuItem onClick={() => openAccessModal(document)}>
                        <ShieldCheck className="mr-2 h-4 w-4" /> Phân quyền công ty
                      </DropdownMenuItem>
                    )}
                    {isRetryAvailable(document) && (
                      <DropdownMenuItem onClick={() => handleRetry(document.document_id)}>
                        <RotateCcw className="mr-2 h-4 w-4" /> Thử lại nạp liệu
                      </DropdownMenuItem>
                    )}
                    {isRechunkAvailable(document) && (
                      <DropdownMenuItem onClick={() => handleRechunk(document.document_id)}>
                        <WandSparkles className="mr-2 h-4 w-4" /> Chia lại node (Rechunk)
                      </DropdownMenuItem>
                    )}
                    <DropdownMenuItem
                      onClick={() => {
                        void navigator.clipboard.writeText(document.document_id);
                        toast.success("Đã sao chép ID tài liệu");
                      }}
                    >
                      <Copy className="mr-2 h-4 w-4" /> Sao chép ID tài liệu
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem
                      className="text-destructive focus:text-destructive"
                      onClick={() => setDeletingDoc(document)}
                    >
                      <Trash2 className="mr-2 h-4 w-4" /> Xóa tài liệu
                    </DropdownMenuItem>
                  </DropdownMenuGroup>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          );
        },
      }),
    ]);
  }, [
    handleRechunk,
    handleRetry,
    isRechunkAvailable,
    isRetryAvailable,
    openAccessModal,
    readOnly,
    tenantOptions.length,
  ]);

  return (
    <TooltipProvider>
      <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="flex items-center gap-2">
          {!readOnly ? (
            <>
              <Input
                ref={fileInputRef}
                type="file"
                multiple
                onChange={handleUpload}
                disabled={readOnly || uploading}
                className="hidden"
              />
              <Button className="rounded-xl" disabled={!canUpload || uploading} onClick={() => fileInputRef.current?.click()}>
                <FileUp className="mr-2 h-4 w-4" />
                {uploading ? "Đang upload..." : "Upload tài liệu"}
              </Button>
            </>
          ) : null}

          <Button className="rounded-xl" variant="outline" onClick={loadDocuments} disabled={loading}>
            <RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            Làm mới
          </Button>
        </div>
      </div>

      {hasRunningDocuments ? (
        <div className="rounded-xl border border-dashed border-primary/40 bg-primary/5 px-3 py-2 text-xs text-muted-foreground">
          Hệ thống đang xử lý tài liệu. Danh sách sẽ tự cập nhật realtime.
        </div>
      ) : null}

      {loading && documents.length === 0 ? (
        <div className="space-y-3 py-4">
          <Skeleton className="h-10 w-full rounded-xl" />
          <Skeleton className="h-16 w-full rounded-xl" />
          <Skeleton className="h-16 w-full rounded-xl" />
          <Skeleton className="h-16 w-full rounded-xl" />
        </div>
      ) : (
        <DataTable
          columns={columns}
          data={documents}
          searchKey="file_name"
          searchPlaceholder="Lọc theo tên file..."
          enablePagination
          enableColumnVisibility
          emptyMessage={
            <div className="py-6 text-center">
              <p className="text-sm font-medium">Chưa có tài liệu nào</p>
              <p className="text-xs text-muted-foreground mt-1">
                Tải lên tài liệu PDF, DOCX hoặc TXT để bắt đầu phân tích và tạo cơ sở tri thức RAG cho Chatbot.
              </p>
            </div>
          }
        />
      )}

      {/* Tenant Access Dialog */}
      <Dialog open={!!accessDoc} onOpenChange={(open) => !open && setAccessDoc(null)}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>Phân quyền tài liệu</DialogTitle>
            <DialogDescription>
              Chọn các công ty (Tenant) được phép truy cập và tra cứu thông tin từ tài liệu <span className="font-semibold">{accessDoc?.file_name}</span>.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-3 py-4">
            {tenantOptions.length === 0 ? (
              <p className="text-xs text-muted-foreground">Chưa có công ty nào trong hệ thống.</p>
            ) : (
              tenantOptions.map((tenant) => {
                const isChecked = selectedTenantIds.includes(tenant.id);
                return (
                  <div key={tenant.id} className="flex items-center space-x-3 rounded-lg border p-3">
                    <Checkbox
                      id={`tenant-${tenant.id}`}
                      checked={isChecked}
                      onCheckedChange={() => toggleTenantSelection(tenant.id)}
                    />
                    <label
                      htmlFor={`tenant-${tenant.id}`}
                      className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 cursor-pointer flex-1"
                    >
                      {tenant.name}
                    </label>
                  </div>
                );
              })
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setAccessDoc(null)} disabled={savingAccess}>
              Hủy
            </Button>
            <Button onClick={handleSaveAccess} disabled={savingAccess}>
              {savingAccess ? "Đang lưu..." : "Lưu phân quyền"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Alert Dialog */}
      <AlertDialog open={!!deletingDoc} onOpenChange={(open) => !open && setDeletingDoc(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Xác nhận xóa tài liệu</AlertDialogTitle>
            <AlertDialogDescription>
              Bạn có chắc chắn muốn xóa tài liệu <span className="font-semibold text-foreground">{deletingDoc?.file_name}</span>? 
              Hành động này sẽ thực hiện quy trình xóa nghiêm ngặt (Hard Delete): xóa vector embeddings, dọn dẹp các phân đoạn tri thức và tệp đính kèm.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Hủy</AlertDialogCancel>
            <AlertDialogAction
              className={buttonVariants({ variant: "destructive" })}
              onClick={async () => {
                if (deletingDoc) {
                  await handleDelete(deletingDoc.document_id);
                  setDeletingDoc(null);
                }
              }}
            >
              Xóa tài liệu
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      </div>
    </TooltipProvider>
  );
}
