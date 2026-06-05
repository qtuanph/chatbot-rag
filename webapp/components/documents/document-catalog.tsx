"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
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
      return "Chọn tenant ngay tại trang này trước khi làm việc với tài liệu.";
    }
    return "Chưa có tài liệu nào trong phạm vi hiện tại.";
  }, [readOnly, selectedTenantId, tenantOptions.length]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
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
              <div className="relative overflow-hidden">
                <Input
                  type="file"
                  multiple
                  onChange={handleUpload}
                  disabled={!canUpload || uploading}
                  className="absolute inset-0 cursor-pointer opacity-0"
                />
                <Button disabled={!canUpload || uploading}>
                  <FileUp className="mr-2 h-4 w-4" />
                  {uploading ? "Đang upload..." : "Upload tài liệu"}
                </Button>
              </div>
            ) : null}
            <Button variant="outline" onClick={loadDocuments} disabled={loading}>
              <RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} />
              Làm mới
            </Button>
          </div>
        </div>

        {hasRunningDocuments ? (
          <div className="rounded-lg border border-dashed border-primary/40 bg-primary/5 px-3 py-2 text-xs text-muted-foreground">
            Hệ thống đang xử lý tài liệu. Danh sách sẽ tự làm mới mỗi vài giây, anh không cần bấm F5 nữa.
          </div>
        ) : null}

        {loading ? (
          <div className="text-sm text-muted-foreground">Đang tải tài liệu...</div>
        ) : documents.length === 0 ? (
          <div className="rounded-lg border border-dashed p-6 text-sm text-muted-foreground">{emptyText}</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[980px]">
              <thead>
                <tr className="border-b border-muted">
                  <th className="py-2 pr-4 text-left text-xs font-medium text-muted-foreground">Tên file</th>
                  <th className="py-2 pr-4 text-left text-xs font-medium text-muted-foreground">Tenant</th>
                  <th className="py-2 pr-4 text-left text-xs font-medium text-muted-foreground">Trạng thái</th>
                  <th className="py-2 pr-4 text-left text-xs font-medium text-muted-foreground">Giai đoạn</th>
                  <th className="py-2 pr-4 text-right text-xs font-medium text-muted-foreground">Tiến độ</th>
                  <th className="py-2 pr-4 text-right text-xs font-medium text-muted-foreground">Kích thước</th>
                  <th className="py-2 pr-4 text-left text-xs font-medium text-muted-foreground">Cập nhật</th>
                  {!readOnly ? (
                    <th className="py-2 text-right text-xs font-medium text-muted-foreground">Thao tác</th>
                  ) : null}
                </tr>
              </thead>
              <tbody>
                {documents.map((document) => (
                  <tr key={document.document_id} className="border-b border-muted/50 last:border-0">
                    <td className="py-3 pr-4">
                      <div className="font-medium">{document.file_name}</div>
                      <div className="text-xs text-muted-foreground">
                        v{document.version} • {document.file_type}
                      </div>
                    </td>
                    <td className="py-3 pr-4 text-sm">{tenantNameMap.get(document.tenant_id) || document.tenant_id}</td>
                    <td className="py-3 pr-4 text-sm capitalize">{document.status}</td>
                    <td className="py-3 pr-4 text-sm capitalize">{document.stage}</td>
                    <td className="py-3 pr-4 text-right text-sm">{document.progress_percent}%</td>
                    <td className="py-3 pr-4 text-right text-sm">{formatNumber(document.file_size)} bytes</td>
                    <td className="py-3 pr-4 text-sm text-muted-foreground">{formatDateTimeVN(document.updated_at)}</td>
                    {!readOnly ? (
                      <td className="py-3 text-right">
                        <div className="flex justify-end gap-2">
                          {isRetryAvailable(document) ? (
                            <Tooltip>
                              <TooltipTrigger>
                                <Button size="icon" variant="outline" onClick={() => handleRetry(document.document_id)}>
                                  <RotateCcw className="h-4 w-4" />
                                </Button>
                              </TooltipTrigger>
                              <TooltipContent>Thử lại</TooltipContent>
                            </Tooltip>
                          ) : null}
                          {isRechunkAvailable(document) ? (
                            <Tooltip>
                              <TooltipTrigger>
                                <Button size="icon" variant="outline" onClick={() => handleRechunk(document.document_id)}>
                                  <WandSparkles className="h-4 w-4" />
                                </Button>
                              </TooltipTrigger>
                              <TooltipContent>Chia lại node</TooltipContent>
                            </Tooltip>
                          ) : null}
                          <Tooltip>
                            <TooltipTrigger>
                              <Button size="icon" variant="destructive" onClick={() => handleDelete(document.document_id)}>
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>Xóa tài liệu</TooltipContent>
                          </Tooltip>
                        </div>
                      </td>
                    ) : null}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
