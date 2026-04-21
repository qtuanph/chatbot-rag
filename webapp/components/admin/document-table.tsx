"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Progress } from "@/components/ui/progress";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  Eye,
  Trash2,
  FileText,
  RefreshCw,
  AlertCircle,
  ExternalLink,
  Loader2,
} from "lucide-react";
import { documentsApi } from "@/lib/api-client";
import { toast } from "sonner";
import { UploadDialog } from "@/components/admin/upload-dialog";
import type { DocumentSummary } from "@/types/api";

function statusVariant(status: string) {
  switch (status) {
    case "ready":
      return "bg-green-500/15 text-green-700 dark:text-green-400";
    case "processing":
    case "pending":
      return "bg-blue-500/15 text-blue-700 dark:text-blue-400";
    case "failed":
      return "bg-red-500/15 text-red-700 dark:text-red-400";
    default:
      return "bg-gray-500/15 text-gray-700 dark:text-gray-400";
  }
}

function statusLabel(status: string) {
  switch (status) {
    case "ready":
      return "Hoàn tất";
    case "processing":
      return "Đang xử lý";
    case "pending":
      return "Chờ xử lý";
    case "failed":
      return "Lỗi";
    default:
      return status;
  }
}

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

const POLL_INTERVAL = 3000;

export function DocumentTable() {
  const { data: session } = useSession();
  const router = useRouter();
  const [docs, setDocs] = useState<DocumentSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [retryingId, setRetryingId] = useState<string | null>(null);

  // Progress dialog state
  const [viewDoc, setViewDoc] = useState<DocumentSummary | null>(null);
  const [viewProgress, setViewProgress] = useState(0);
  const [viewStatus, setViewStatus] = useState<string>("");
  const [viewMessage, setViewMessage] = useState<string>("");
  const viewPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchDocs = useCallback(async () => {
    if (!session?.accessToken) return;
    try {
      const result = await documentsApi.list(session.accessToken);
      setDocs(result.items);
    } catch {
      toast.error("Không thể tải danh sách tài liệu");
    } finally {
      setLoading(false);
    }
  }, [session?.accessToken]);

  useEffect(() => {
    fetchDocs();
  }, [fetchDocs]);

  // Auto-poll when any document is processing/pending
  useEffect(() => {
    const hasActive = docs.some(
      (d) => d.status === "processing" || d.status === "pending",
    );

    if (hasActive && !pollingRef.current) {
      pollingRef.current = setInterval(fetchDocs, POLL_INTERVAL);
    } else if (!hasActive && pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }

    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
    };
  }, [docs, fetchDocs]);

  // Progress dialog polling
  useEffect(() => {
    if (!viewDoc || !session?.accessToken) return;

    const pollView = async () => {
      try {
        const detail = await documentsApi.get(
          viewDoc.document_id,
          session.accessToken!,
        );
        setViewProgress(detail.progress_percent);
        setViewStatus(detail.status);
        setViewMessage(detail.status_message || detail.parse_error || "");

        if (detail.status === "ready" || detail.status === "failed") {
          if (viewPollRef.current) {
            clearInterval(viewPollRef.current);
            viewPollRef.current = null;
          }
          fetchDocs();
        }
      } catch {
        // Silently ignore polling errors
      }
    };

    pollView();

    if (viewDoc.status !== "ready" && viewDoc.status !== "failed") {
      viewPollRef.current = setInterval(pollView, 2000);
    }

    return () => {
      if (viewPollRef.current) {
        clearInterval(viewPollRef.current);
        viewPollRef.current = null;
      }
    };
  }, [viewDoc?.document_id, session?.accessToken, fetchDocs]);

  const handleView = useCallback(
    (doc: DocumentSummary) => {
      if (doc.status === "ready") {
        router.push(`/admin/documents/${doc.document_id}`);
        return;
      }
      setViewDoc(doc);
      setViewProgress(doc.progress_percent);
      setViewStatus(doc.status);
      setViewMessage(doc.status_message || "");
    },
    [router],
  );

  const handleCloseView = useCallback(() => {
    if (viewPollRef.current) {
      clearInterval(viewPollRef.current);
      viewPollRef.current = null;
    }
    setViewDoc(null);
  }, []);

  const handleDelete = useCallback(
    async (id: string) => {
      if (!session?.accessToken) return;
      try {
        await documentsApi.delete(id, session.accessToken);
        toast.success("Đã xếp hàng xóa tài liệu");
        setDeleteTarget(null);
        fetchDocs();
      } catch {
        toast.error("Xóa thất bại");
      }
    },
    [session?.accessToken, fetchDocs],
  );

  const handleRetry = useCallback(
    async (id: string) => {
      if (!session?.accessToken) return;
      setRetryingId(id);
      try {
        await documentsApi.retry(id, session.accessToken);
        toast.success("Đã xếp hàng xử lý lại tài liệu");
        handleCloseView();
        fetchDocs();
      } catch {
        toast.error("Không thể xử lý lại. Vui lòng thử lại.");
      } finally {
        setRetryingId(null);
      }
    },
    [session?.accessToken, fetchDocs, handleCloseView],
  );

  if (loading) {
    return (
      <div className="space-y-3">
        {[...Array(3)].map((_, i) => (
          <Skeleton key={i} className="h-12" />
        ))}
      </div>
    );
  }

  return (
    <TooltipProvider>
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold">Tài liệu</h2>
            <p className="text-sm text-muted-foreground">
              {docs.length} tài liệu
            </p>
          </div>
          <UploadDialog onUploaded={fetchDocs} />
        </div>

        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Tên file</TableHead>
                <TableHead>Loại</TableHead>
                <TableHead>Dung lượng</TableHead>
                <TableHead>Trạng thái</TableHead>
                <TableHead>Tiến trình</TableHead>
                <TableHead>Ngày tạo</TableHead>
                <TableHead className="text-right">Thao tác</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {docs.length === 0 ? (
                <TableRow>
                  <TableCell
                    colSpan={7}
                    className="text-center py-8 text-muted-foreground"
                  >
                    <FileText className="mx-auto h-8 w-8 mb-2" />
                    Chưa có tài liệu nào
                  </TableCell>
                </TableRow>
              ) : (
                docs.map((doc) => (
                  <TableRow key={doc.document_id}>
                    <TableCell className="font-medium max-w-[200px] truncate">
                      {doc.file_name}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {doc.file_type?.split("/").pop()?.toUpperCase() || "—"}
                    </TableCell>
                    <TableCell>{formatSize(doc.file_size)}</TableCell>
                    <TableCell>
                      <div className="flex flex-col gap-1">
                        <Badge
                          variant="outline"
                          className={statusVariant(doc.status)}
                        >
                          {statusLabel(doc.status)}
                        </Badge>
                        {doc.status === "failed" && doc.status_message && (
                          <Tooltip>
                            <TooltipTrigger
                              className="flex items-center gap-1 text-xs text-destructive cursor-help"
                            >
                              <AlertCircle className="h-3 w-3 shrink-0" />
                              <span className="truncate max-w-[150px]">
                                {doc.status_message}
                              </span>
                            </TooltipTrigger>
                            <TooltipContent side="bottom" className="max-w-xs">
                              <p>{doc.status_message}</p>
                            </TooltipContent>
                          </Tooltip>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      {doc.status === "processing" ||
                      doc.status === "pending" ? (
                        <div className="w-20">
                          <Progress
                            value={doc.progress_percent}
                            className="h-2"
                          />
                          <p className="text-xs text-muted-foreground mt-0.5">
                            {doc.progress_percent}%
                          </p>
                        </div>
                      ) : doc.status === "failed" ? (
                        <span className="text-xs text-destructive">
                          Thất bại
                        </span>
                      ) : (
                        <span className="text-xs text-muted-foreground">—</span>
                      )}
                    </TableCell>
                    <TableCell className="text-muted-foreground text-xs">
                      {new Date(doc.created_at).toLocaleDateString("vi-VN")}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex gap-1 justify-end">
                        {doc.status === "failed" && (
                          <Tooltip>
                            <TooltipTrigger
                              render={
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  disabled={retryingId === doc.document_id}
                                />
                              }
                              onClick={() => handleRetry(doc.document_id)}
                            >
                              <RefreshCw
                                className={`h-4 w-4 ${retryingId === doc.document_id ? "animate-spin" : ""}`}
                              />
                            </TooltipTrigger>
                            <TooltipContent>Xử lý lại</TooltipContent>
                          </Tooltip>
                        )}
                        <Tooltip>
                          <TooltipTrigger
                            render={
                              <Button variant="ghost" size="icon" />
                            }
                            onClick={() => handleView(doc)}
                          >
                            <Eye className="h-4 w-4" />
                          </TooltipTrigger>
                          <TooltipContent>
                            {doc.status === "ready"
                              ? "Xem chi tiết"
                              : "Xem tiến trình"}
                          </TooltipContent>
                        </Tooltip>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => setDeleteTarget(doc.document_id)}
                        >
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>

        {/* Delete confirm dialog */}
        <Dialog open={!!deleteTarget} onOpenChange={() => setDeleteTarget(null)}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Xác nhận xóa</DialogTitle>
            </DialogHeader>
            <p className="text-sm text-muted-foreground">
              Bạn có chắc muốn xóa tài liệu này? Hành động này không thể hoàn
              tác.
            </p>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setDeleteTarget(null)}
              >
                Hủy
              </Button>
              <Button
                variant="destructive"
                onClick={() => deleteTarget && handleDelete(deleteTarget)}
              >
                Xóa
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Progress/Status view dialog */}
        <Dialog
          open={!!viewDoc}
          onOpenChange={(open) => !open && handleCloseView()}
        >
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{viewDoc?.file_name || "Tài liệu"}</DialogTitle>
              <DialogDescription>
                {viewStatus === "ready"
                  ? "Tài liệu đã xử lý hoàn tất"
                  : viewStatus === "failed"
                    ? "Xử lý tài liệu thất bại"
                    : "Đang xử lý tài liệu"}
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4 py-2">
              {/* Progress bar for active documents */}
              {(viewStatus === "processing" || viewStatus === "pending") && (
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className="flex items-center gap-2">
                      <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
                      Đang xử lý...
                    </span>
                    <span className="font-mono">{viewProgress}%</span>
                  </div>
                  <Progress value={viewProgress} />
                  {viewMessage && (
                    <p className="text-xs text-muted-foreground">
                      {viewMessage}
                    </p>
                  )}
                </div>
              )}

              {/* Success state */}
              {viewStatus === "ready" && (
                <div className="text-center space-y-3 py-4">
                  <div className="mx-auto w-12 h-12 rounded-full bg-green-500/15 flex items-center justify-center">
                    <FileText className="h-6 w-6 text-green-600" />
                  </div>
                  <p className="text-sm text-muted-foreground">
                    Tài liệu sẵn sàng để sử dụng
                  </p>
                </div>
              )}

              {/* Error state */}
              {viewStatus === "failed" && (
                <div className="space-y-3">
                  <div className="rounded-md bg-destructive/10 p-3">
                    <div className="flex items-start gap-2">
                      <AlertCircle className="h-4 w-4 text-destructive shrink-0 mt-0.5" />
                      <div className="space-y-1">
                        <p className="text-sm font-medium text-destructive">
                          Xử lý thất bại
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {viewMessage || "Đã xảy ra lỗi không xác định"}
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>

            <DialogFooter>
              {viewStatus === "failed" && viewDoc && (
                <Button
                  variant="outline"
                  onClick={() => handleRetry(viewDoc.document_id)}
                  disabled={retryingId === viewDoc.document_id}
                  className="gap-2"
                >
                  <RefreshCw
                    className={`h-4 w-4 ${retryingId === viewDoc.document_id ? "animate-spin" : ""}`}
                  />
                  Xử lý lại
                </Button>
              )}
              {viewStatus === "ready" && viewDoc && (
                <Button
                  onClick={() => {
                    handleCloseView();
                    router.push(`/admin/documents/${viewDoc.document_id}`);
                  }}
                  className="gap-2"
                >
                  <ExternalLink className="h-4 w-4" />
                  Xem chi tiết
                </Button>
              )}
              <Button variant="outline" onClick={handleCloseView}>
                Đóng
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </TooltipProvider>
  );
}
