"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Columns, FileUp, RefreshCw, RotateCcw, Trash2, WandSparkles } from "lucide-react";
import { toast } from "sonner";

import { TenantSelect } from "@/components/tenants/tenant-select";
import { Button, buttonVariants } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuCheckboxItem, DropdownMenuContent, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Field, FieldContent, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { documentsApi } from "@/lib/api-client";
import { formatDateTimeVN, formatNumber } from "@/lib/format";
import { DocumentListResponseSchema } from "@/lib/schemas";
import type { DocumentListResponse, DocumentSummary, TenantItem } from "@/types/api";

const TABLE_COLUMNS = ["Tên file", "Tenant", "Trạng thái", "Giai đoạn", "Tiến độ", "Kích thước", "Cập nhật"];

interface DocumentCatalogProps {
  readOnly?: boolean;
  tenantOptions?: TenantItem[];
  selectedTenantId?: string | null;
  onSelectedTenantIdChange?: (tenantId: string) => void;
}

export function DocumentCatalog({
  readOnly = false,
  tenantOptions = [],
  selectedTenantId = null,
  onSelectedTenantIdChange,
}: DocumentCatalogProps) {
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [visibleColumns, setVisibleColumns] = useState<Record<string, boolean>>(
    TABLE_COLUMNS.reduce((acc, col) => ({ ...acc, [col]: true }), {})
  );

  const canUpload = !readOnly && !!selectedTenantId;
  const effectiveTenantId = selectedTenantId || undefined;
  const tenantNameMap = useMemo(
    () => new Map(tenantOptions.map((tenant) => [tenant.id, tenant.name])),
    [tenantOptions],
  );

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
      if (!selectedTenantId || files.length === 0) return;

      try {
        setUploading(true);
        for (const file of files) {
          await documentsApi.upload(file, selectedTenantId);
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
    [loadDocuments, selectedTenantId],
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

  const emptyText = useMemo(() => {
    if (!selectedTenantId && tenantOptions.length > 0 && !readOnly) {
      return "Đang ở chế độ tất cả tenant. Hãy chọn một tenant cụ thể nếu anh muốn upload tài liệu mới.";
    }
    return "Chưa có tài liệu nào trong phạm vi hiện tại.";
  }, [readOnly, selectedTenantId, tenantOptions.length]);

  return (
    <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          {!readOnly && tenantOptions.length > 0 ? (
            <Field orientation="horizontal" className="min-w-[260px] items-center gap-3">
              <FieldLabel>Tenant</FieldLabel>
              <FieldContent>
                <TenantSelect
                  tenants={tenantOptions}
                  value={selectedTenantId}
                  onValueChange={(tenantId) => onSelectedTenantIdChange?.(tenantId || "")}
                  includeAll
                  triggerClassName="w-[300px]"
                />
              </FieldContent>
            </Field>
          ) : null}

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

        {!canUpload && !readOnly && tenantOptions.length > 0 ? (
          <div className="rounded-xl border border-dashed border-border/80 bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
            Đang chọn <span className="font-medium">Tất cả tenant</span>. Hãy chọn một tenant cụ thể để bật upload tài liệu.
          </div>
        ) : null}

        {hasRunningDocuments ? (
          <div className="rounded-xl border border-dashed border-primary/40 bg-primary/5 px-3 py-2 text-xs text-muted-foreground">
            Hệ thống đang xử lý tài liệu. Danh sách sẽ tự cập nhật realtime, anh không cần bấm F5 nữa.
          </div>
        ) : null}

        {loading ? (
          <div className="text-sm text-muted-foreground">Đang tải tài liệu...</div>
        ) : documents.length === 0 ? (
          <div className="rounded-xl border border-dashed p-6 text-sm text-muted-foreground">{emptyText}</div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                {visibleColumns["Tên file"] && <TableHead className="pr-4 text-xs text-muted-foreground">Tên file</TableHead>}
                {visibleColumns["Tenant"] && <TableHead className="pr-4 text-xs text-muted-foreground">Tenant</TableHead>}
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
                  {visibleColumns["Tenant"] && <TableCell className="pr-4 text-sm">{tenantNameMap.get(document.tenant_id) || "Không rõ tenant"}</TableCell>}
                  {visibleColumns["Trạng thái"] && <TableCell className="pr-4 text-sm capitalize">{document.status}</TableCell>}
                  {visibleColumns["Giai đoạn"] && <TableCell className="pr-4 text-sm capitalize">{document.stage}</TableCell>}
                  {visibleColumns["Tiến độ"] && <TableCell className="pr-4 text-right text-sm">{document.progress_percent}%</TableCell>}
                  {visibleColumns["Kích thước"] && <TableCell className="pr-4 text-right text-sm">{formatNumber(document.file_size)} bytes</TableCell>}
                  {visibleColumns["Cập nhật"] && <TableCell className="pr-4 text-sm text-muted-foreground">{formatDateTimeVN(document.updated_at)}</TableCell>}
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
    </div>
  );
}
