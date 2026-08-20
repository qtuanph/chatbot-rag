"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Columns, FileUp, RefreshCw, RotateCcw, ShieldCheck, Trash2, WandSparkles } from "lucide-react";
import { toast } from "sonner";

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
import { DropdownMenu, DropdownMenuCheckboxItem, DropdownMenuContent, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { documentsApi } from "@/lib/api-client";
import { formatDateTimeVN, formatNumber } from "@/lib/format";
import { DocumentListResponseSchema } from "@/lib/schemas";
import type { DocumentSummary, TenantBrief, TenantItem } from "@/types/api";

const TABLE_COLUMNS = ["Tên file", "Phân quyền", "Trạng thái", "Giai đoạn", "Tiến độ", "Kích thước", "Cập nhật"];

interface DocumentCatalogProps {
  readOnly?: boolean;
  tenantOptions?: TenantItem[];
  selectedTenantId?: string | null;
}

export function DocumentCatalog({
  readOnly = false,
  tenantOptions = [],
  selectedTenantId = null,
}: DocumentCatalogProps) {
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [visibleColumns, setVisibleColumns] = useState<Record<string, boolean>>(
    TABLE_COLUMNS.reduce((acc, col) => ({ ...acc, [col]: true }), {})
  );

  // Access Permission Modal state
  const [accessDoc, setAccessDoc] = useState<DocumentSummary | null>(null);
  const [selectedTenantIds, setSelectedTenantIds] = useState<string[]>([]);
  const [savingAccess, setSavingAccess] = useState(false);

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

  return (
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

          <DropdownMenu>
            <DropdownMenuTrigger className={buttonVariants({ variant: "outline", className: "h-9" })}>
              <Columns className="mr-2 h-4 w-4" /> Cột hiển thị
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              {TABLE_COLUMNS.map((col) => (
                <DropdownMenuCheckboxItem
                  key={col}
                  checked={visibleColumns[col]}
                  onCheckedChange={(val) => setVisibleColumns((prev) => ({ ...prev, [col]: val }))}
                >
                  {col}
                </DropdownMenuCheckboxItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>

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

      {loading ? (
        <div className="text-sm text-muted-foreground">Đang tải tài liệu...</div>
      ) : documents.length === 0 ? (
        <div className="rounded-xl border border-dashed p-6 text-sm text-muted-foreground">Chưa có tài liệu nào.</div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              {visibleColumns["Tên file"] && <TableHead className="pr-4 text-xs text-muted-foreground">Tên file</TableHead>}
              {visibleColumns["Phân quyền"] && <TableHead className="pr-4 text-xs text-muted-foreground">Phân quyền công ty</TableHead>}
              {visibleColumns["Trạng thái"] && <TableHead className="pr-4 text-xs text-muted-foreground">Trạng thái</TableHead>}
              {visibleColumns["Giai đoạn"] && <TableHead className="pr-4 text-xs text-muted-foreground">Giai đoạn</TableHead>}
              {visibleColumns["Tiến độ"] && <TableHead className="pr-4 text-right text-xs text-muted-foreground">Tiến độ</TableHead>}
              {visibleColumns["Kích thước"] && <TableHead className="pr-4 text-right text-xs text-muted-foreground">Kích thước</TableHead>}
              {visibleColumns["Cập nhật"] && <TableHead className="pr-4 text-xs text-muted-foreground">Cập nhật</TableHead>}
              {!readOnly ? <TableHead className="text-right text-xs text-muted-foreground">Thao tác</TableHead> : null}
            </TableRow>
          </TableHeader>
          <TableBody>
            {documents.map((document) => (
              <TableRow key={document.document_id}>
                {visibleColumns["Tên file"] && (
                  <TableCell className="pr-4">
                    <div className="font-medium">{document.file_name}</div>
                    <div className="text-xs text-muted-foreground">
                      v{document.version} • {document.file_type}
                    </div>
                  </TableCell>
                )}
                {visibleColumns["Phân quyền"] && (
                  <TableCell className="pr-4 text-sm">
                    <div className="flex flex-wrap items-center gap-1.5">
                      {document.allowed_tenants && document.allowed_tenants.length > 0 ? (
                        document.allowed_tenants.map((t) => (
                          <Badge key={t.id} variant="secondary" className="text-xs">
                            {t.name}
                          </Badge>
                        ))
                      ) : (
                        <span className="text-xs italic text-muted-foreground">Chưa phân quyền</span>
                      )}
                      {!readOnly && tenantOptions.length > 0 ? (
                        <Tooltip>
                          <TooltipTrigger
                            render={
                              <Button
                                size="icon"
                                variant="ghost"
                                className="h-6 w-6 rounded-lg"
                                onClick={() => openAccessModal(document)}
                              >
                                <ShieldCheck className="h-3.5 w-3.5" />
                              </Button>
                            }
                          />
                          <TooltipContent>Phân quyền công ty</TooltipContent>
                        </Tooltip>
                      ) : null}
                    </div>
                  </TableCell>
                )}
                {visibleColumns["Trạng thái"] && (
                  <TableCell className="pr-4 text-sm">
                    {document.status === "ready" ? (
                      <Badge variant="outline" className="border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 gap-1.5 font-medium text-xs">
                        <span className="pulse-dot-active" /> Sẵn sàng
                      </Badge>
                    ) : document.status === "failed" ? (
                      <Badge variant="destructive" className="text-xs">
                        Thất bại
                      </Badge>
                    ) : (
                      <Badge variant="outline" className="border-amber-500/30 bg-amber-500/10 text-amber-600 dark:text-amber-400 gap-1.5 font-medium text-xs">
                        <span className="pulse-dot-amber" /> Đang nạp
                      </Badge>
                    )}
                  </TableCell>
                )}
                {visibleColumns["Giai đoạn"] && (
                  <TableCell className="pr-4 text-xs font-mono capitalize text-muted-foreground">
                    {document.stage || "—"}
                  </TableCell>
                )}
                {visibleColumns["Tiến độ"] && (
                  <TableCell className="pr-4 text-right text-sm">
                    <div className="flex items-center justify-end gap-2">
                      <span className="font-mono text-xs font-medium">{document.progress_percent}%</span>
                      {document.status !== "ready" && document.status !== "failed" && (
                        <div className="w-12 h-1.5 bg-muted rounded-full overflow-hidden">
                          <div
                            className="h-full bg-primary transition-all duration-300 rounded-full"
                            style={{ width: `${document.progress_percent}%` }}
                          />
                        </div>
                      )}
                    </div>
                  </TableCell>
                )}
                {visibleColumns["Kích thước"] && <TableCell className="pr-4 text-right text-xs font-mono">{formatNumber(document.file_size)} B</TableCell>}
                {visibleColumns["Cập nhật"] && <TableCell className="pr-4 text-xs text-muted-foreground">{formatDateTimeVN(document.updated_at)}</TableCell>}
                {!readOnly ? (
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-2">
                      {isRetryAvailable(document) ? (
                        <Tooltip>
                          <TooltipTrigger
                            render={
                              <Button size="icon" variant="outline" className="rounded-xl" onClick={() => handleRetry(document.document_id)}>
                                <RotateCcw className="h-4 w-4" />
                              </Button>
                            }
                          />
                          <TooltipContent>Thử lại</TooltipContent>
                        </Tooltip>
                      ) : null}

                      {isRechunkAvailable(document) ? (
                        <Tooltip>
                          <TooltipTrigger
                            render={
                              <Button size="icon" variant="outline" className="rounded-xl" onClick={() => handleRechunk(document.document_id)}>
                                <WandSparkles className="h-4 w-4" />
                              </Button>
                            }
                          />
                          <TooltipContent>Chia lại node</TooltipContent>
                        </Tooltip>
                      ) : null}

                      <Tooltip>
                        <TooltipTrigger
                          render={
                            <Button size="icon" variant="destructive" className="rounded-xl" onClick={() => handleDelete(document.document_id)}>
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          }
                        />
                        <TooltipContent>Xóa tài liệu</TooltipContent>
                      </Tooltip>
                    </div>
                  </TableCell>
                ) : null}
              </TableRow>
            ))}
          </TableBody>
        </Table>
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
    </div>
  );
}
