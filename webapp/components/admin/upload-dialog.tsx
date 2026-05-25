"use client";

import { useState, useCallback, useRef } from "react";
import { useSession } from "next-auth/react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Upload, CheckCircle, AlertCircle, FileText } from "lucide-react";
import { documentsApi, ApiError } from "@/lib/api-client";
import { toast } from "sonner";

interface UploadItem {
  id: string;
  file: File;
  status: "uploading" | "processing" | "done" | "failed";
  progress: number;
  message: string;
  error: string | null;
  taskId: string | null;
}

interface UploadDialogProps {
  onUploaded: () => void;
}

const PROGRESS_POLL_MS = 1000;

function statusLabel(status: UploadItem["status"]): string {
  switch (status) {
    case "uploading":
      return "Đang tải lên";
    case "processing":
      return "Đang xử lý";
    case "done":
      return "Hoàn tất";
    case "failed":
      return "Thất bại";
    default:
      return "";
  }
}

export function UploadDialog({ onUploaded }: UploadDialogProps) {
  const { data: session } = useSession();
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<UploadItem[]>([]);
  const pollTimers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  const cancelAllPolling = useCallback(() => {
    pollTimers.current.forEach((timer) => clearTimeout(timer));
    pollTimers.current.clear();
  }, []);

  const resetState = useCallback(() => {
    cancelAllPolling();
    setItems([]);
  }, [cancelAllPolling]);

  const pollProgress = useCallback(
    (itemId: string, taskId: string) => {
      const poll = async () => {
        try {
          const status = await documentsApi.getStatus(taskId);

          setItems((prev) =>
            prev.map((item) =>
              item.id === itemId
                ? {
                    ...item,
                    progress: status.progress.percent,
                    message: status.status_message || status.stage || "",
                    status:
                      status.status === "ready"
                        ? "done"
                        : status.status === "failed"
                          ? "failed"
                          : "processing",
                    error: status.error,
                  }
                : item,
            ),
          );

          if (status.status === "ready") {
            setItems((prev) =>
              prev.map((item) =>
                item.id === itemId ? { ...item, progress: 100, message: "Hoàn tất!" } : item,
              ),
            );
            pollTimers.current.delete(itemId);
            onUploaded();
            return;
          }

          if (status.status === "failed") {
            pollTimers.current.delete(itemId);
            onUploaded();
            return;
          }

          pollTimers.current.set(itemId, setTimeout(() => poll(), PROGRESS_POLL_MS));
        } catch {
          setItems((prev) =>
            prev.map((item) =>
              item.id === itemId
                ? { ...item, status: "failed", error: "Lỗi khi kiểm tra tiến trình" }
                : item,
            ),
          );
          pollTimers.current.delete(itemId);
        }
      };
      poll();
    },
    [onUploaded],
  );

  const handleFileChange = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = e.target.files;
      if (!files || files.length === 0 || !session) return;

      const newItems: UploadItem[] = Array.from(files).map((file) => ({
        id: crypto.randomUUID(),
        file,
        status: "uploading",
        progress: 5,
        message: "Đang tải lên...",
        error: null,
        taskId: null,
      }));

      setItems((prev) => [...prev, ...newItems]);

      const uploadPromises = newItems.map(async (item) => {
        try {
          const result = await documentsApi.upload(item.file);
          onUploaded();

          setItems((prev) =>
            prev.map((i) =>
              i.id === item.id
                ? { ...i, status: "processing", progress: 10, message: "Đang xử lý...", taskId: result.task_id }
                : i,
            ),
          );

          pollProgress(item.id, result.task_id);
        } catch (err) {
          const msg = err instanceof ApiError ? err.detail : "Tải lên thất bại";
          setItems((prev) =>
            prev.map((i) => (i.id === item.id ? { ...i, status: "failed", error: msg } : i)),
          );
          toast.error(`${item.file.name}: ${msg}`);
        }
      });

      Promise.allSettled(uploadPromises);
      e.target.value = "";
    },
    [session, pollProgress, onUploaded],
  );

  const handleClose = useCallback(() => {
    cancelAllPolling();
    const anyDone = items.some((i) => i.status === "done");
    resetState();
    if (anyDone) onUploaded();
    setOpen(false);
  }, [cancelAllPolling, items, resetState, onUploaded]);

  const allDone = items.length > 0 && items.every((i) => i.status === "done" || i.status === "failed");
  const avgProgress = items.length > 0 ? Math.round(items.reduce((acc, i) => acc + i.progress, 0) / items.length) : 0;
  const doneCount = items.filter((i) => i.status === "done").length;
  const failedCount = items.filter((i) => i.status === "failed").length;
  const activeCount = items.filter((i) => i.status === "processing" || i.status === "uploading").length;
  const showAggregateProgress = items.length > 1;

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) handleClose();
      }}
    >
      <Button className="gap-2" onClick={() => setOpen(true)}>
        <Upload className="h-4 w-4" />
        Tải tài liệu lên
      </Button>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Tải tài liệu lên</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          {items.length > 0 && showAggregateProgress && (
            <div className="rounded-lg border bg-muted/30 p-3 space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="font-medium">Tiến trình tổng</span>
                <span className="tabular-nums">{avgProgress}%</span>
              </div>
              <Progress value={avgProgress} className="h-2" />
              <p className="text-xs text-muted-foreground">{`Đang xử lý: ${activeCount} • Hoàn tất: ${doneCount} • Lỗi: ${failedCount}`}</p>
            </div>
          )}

          {items.length === 0 ? (
            <div className="grid w-full max-w-sm items-center gap-1.5">
              <label
                htmlFor="file-upload"
                className="border-2 border-dashed rounded-lg p-8 text-center cursor-pointer hover:border-primary/50 transition-colors"
              >
                <Upload className="mx-auto h-8 w-8 text-muted-foreground mb-2" />
                <p className="text-sm text-muted-foreground">Click hoặc kéo thả file vào đây</p>
                <p className="text-xs text-muted-foreground mt-1">PDF, DOCX, XLSX, TXT, MD — chọn nhiều file để tải song song</p>
                <div className="mt-3 flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 p-2.5 text-left text-xs text-amber-800">
                  <FileText className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
                  <span>
                    <strong className="font-semibold">Nên dùng file .MD</strong> — không cần OCR, giữ nguyên cấu trúc heading,
                    tốc độ xử lý nhanh hơn và độ chính xác cao hơn so với PDF/DOCX.
                  </span>
                </div>
              </label>
              <input
                id="file-upload"
                type="file"
                className="hidden"
                accept=".pdf,.docx,.doc,.xlsx,.xls,.txt,.md"
                multiple
                onChange={handleFileChange}
              />
            </div>
          ) : (
            <div className="space-y-3 max-h-80 overflow-y-auto">
              {items.map((item) => (
                <div key={item.id} className="space-y-1.5 border rounded-lg p-3">
                  <div className="flex items-center gap-2">
                    {item.status === "done" && <CheckCircle className="h-4 w-4 text-green-500 shrink-0" />}
                    {item.status === "failed" && <AlertCircle className="h-4 w-4 text-destructive shrink-0" />}
                    {item.status !== "done" && item.status !== "failed" && (
                      <div className="h-4 w-4 border-2 border-primary border-t-transparent rounded-full animate-spin shrink-0" />
                    )}
                    <span className="text-sm font-medium truncate">{item.file.name}</span>
                    <span className="text-[11px] rounded px-1.5 py-0.5 bg-muted text-muted-foreground">{statusLabel(item.status)}</span>
                    <span className="text-xs text-muted-foreground ml-auto shrink-0">{item.progress}%</span>
                  </div>
                  <Progress value={item.progress} className="h-2" />
                  <p className="text-xs text-muted-foreground">
                    {item.error ? <span className="text-destructive">{item.error}</span> : item.message}
                  </p>
                </div>
              ))}
            </div>
          )}

          {items.length > 0 && showAggregateProgress && (
            <p className="text-xs text-muted-foreground text-center">
              {!allDone ? `Đang xử lý ${activeCount}/${items.length} file(s)` : `${doneCount}/${items.length} file(s) hoàn tất`}
            </p>
          )}

          {items.length > 0 && allDone && (
            <label
              htmlFor="file-upload-more"
              className="border-2 border-dashed rounded-lg p-4 text-center cursor-pointer hover:border-primary/50 transition-colors"
            >
              <p className="text-sm text-muted-foreground">+ Thêm file</p>
            </label>
          )}
          {items.length > 0 && allDone && (
            <input
              id="file-upload-more"
              type="file"
              className="hidden"
              accept=".pdf,.docx,.doc,.xlsx,.xls,.txt,.md"
              multiple
              onChange={handleFileChange}
            />
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
