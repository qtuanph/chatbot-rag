"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { FileUp, RefreshCw, RotateCcw, Trash2, WandSparkles } from "lucide-react";
import { toast } from "sonner";

import { documentsApi } from "@/lib/api-client";
import { formatDateTimeVN, formatNumber } from "@/lib/format";
import type { DocumentListResponse, DocumentSummary, TenantItem } from "@/types/api";
import { TenantSelect } from "@/components/tenants/tenant-select";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

interface DocumentCatalogProps {
  title: string;
  description: string;
  readOnly?: boolean;
  tenantOptions?: TenantItem[];
  selectedTenantId?: string | null;
  onSelectedTenantIdChange?: (tenantId: string) => void;
}

export function DocumentCatalog({
  title,
  description,
  readOnly = false,
  tenantOptions = [],
  selectedTenantId = null,
  onSelectedTenantIdChange,
}: DocumentCatalogProps) {
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

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
        const payload = JSON.parse(event.data) as DocumentListResponse;
        setDocuments(payload.items);
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
    <Card className="rounded-3xl border-border/60 shadow-sm">
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          {!readOnly && tenantOptions.length > 0 ? (
            <div className="flex min-w-[260px] items-center gap-2">
              <Label className="shrink-0">Tenant</Label>
              <TenantSelect
                tenants={tenantOptions}
                value={selectedTenantId}
                onValueChange={(tenantId) => onSelectedTenantIdChange?.(tenantId || "")}
                includeAll
                triggerClassName="w-[300px]"
              />
            </div>
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
                <Button
                  className="rounded-2xl"
                  disabled={!canUpload || uploading}
                  onClick={() => fileInputRef.current?.click()}
                >
                  <FileUp className="mr-2 h-4 w-4" />
                  {uploading ? "Đang upload..." : "Upload tài liệu"}
                </Button>
              </>
            ) : null}

            <Button className="rounded-2xl" variant="outline" onClick={loadDocuments} disabled={loading}>
              <RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} />
              Làm mới
            </Button>
          </div>
        </div>

        {!canUpload && !readOnly && tenantOptions.length > 0 ? (
          <div className="rounded-2xl border border-dashed border-border/80 bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
            Đang chọn <span className="font-medium">Tất cả tenant</span>. Hãy chọn một tenant cụ thể để bật upload tài liệu.
          </div>
        ) : null}

        {hasRunningDocuments ? (
          <div className="rounded-2xl border border-dashed border-primary/40 bg-primary/5 px-3 py-2 text-xs text-muted-foreground">
            Hệ thống đang xử lý tài liệu. Danh sách sẽ tự cập nhật realtime, anh không cần bấm F5 nữa.
          </div>
        ) : null}

        {loading ? (
          <div className="text-sm text-muted-foreground">Đang tải tài liệu...</div>
        ) : documents.length === 0 ? (
          <div className="rounded-2xl border border-dashed p-6 text-sm text-muted-foreground">{emptyText}</div>
        ) : (
          <Table className="min-w-[980px]">
            <TableHeader>
              <TableRow>
                <TableHead className="pr-4 text-xs text-muted-foreground">Tên file</TableHead>
                <TableHead className="pr-4 text-xs text-muted-foreground">Tenant</TableHead>
                <TableHead className="pr-4 text-xs text-muted-foreground">Trạng thái</TableHead>
                <TableHead className="pr-4 text-xs text-muted-foreground">Giai đoạn</TableHead>
                <TableHead className="pr-4 text-right text-xs text-muted-foreground">Tiến độ</TableHead>
                <TableHead className="pr-4 text-right text-xs text-muted-foreground">Kích thước</TableHead>
                <TableHead className="pr-4 text-xs text-muted-foreground">Cập nhật</TableHead>
                {!readOnly ? <TableHead className="text-right text-xs text-muted-foreground">Thao tác</TableHead> : null}
              </TableRow>
            </TableHeader>
            <TableBody>
              {documents.map((document) => (
                <TableRow key={document.document_id}>
                  <TableCell className="pr-4">
                    <div className="font-medium">{document.file_name}</div>
                    <div className="text-xs text-muted-foreground">
                      v{document.version} • {document.file_type}
                    </div>
                  </TableCell>
                  <TableCell className="pr-4 text-sm">{tenantNameMap.get(document.tenant_id) || "Không rõ tenant"}</TableCell>
                  <TableCell className="pr-4 text-sm capitalize">{document.status}</TableCell>
                  <TableCell className="pr-4 text-sm capitalize">{document.stage}</TableCell>
                  <TableCell className="pr-4 text-right text-sm">{document.progress_percent}%</TableCell>
                  <TableCell className="pr-4 text-right text-sm">{formatNumber(document.file_size)} bytes</TableCell>
                  <TableCell className="pr-4 text-sm text-muted-foreground">{formatDateTimeVN(document.updated_at)}</TableCell>
                  {!readOnly ? (
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-2">
                        {isRetryAvailable(document) ? (
                          <Tooltip>
                            <TooltipTrigger
                              render={
                                <Button size="icon" variant="outline" className="rounded-2xl" onClick={() => handleRetry(document.document_id)}>
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
                                <Button size="icon" variant="outline" className="rounded-2xl" onClick={() => handleRechunk(document.document_id)}>
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
                              <Button size="icon" variant="destructive" className="rounded-2xl" onClick={() => handleDelete(document.document_id)}>
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
      </CardContent>
    </Card>
  );
}
