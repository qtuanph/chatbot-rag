"use client";

import { useState, useCallback, useRef } from "react";
import { useSession } from "next-auth/react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Upload, X, CheckCircle, AlertCircle } from "lucide-react";
import { documentsApi } from "@/lib/api-client";
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

  // Check if any item is still in progress
  const hasActive = items.some((i) => i.status === "uploading" || i.status === "processing");

  const pollProgress = useCallback((itemId: string, taskId: string) => {
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
                  status: status.status === "ready" ? "done" : status.status === "failed" ? "failed" : "processing",
                  error: status.error,
                }
              : item,
          ),
        );

        if (status.status === "ready") {
          // Final update then stop
          setItems((prev) =>
            prev.map((item) =>
              item.id === itemId ? { ...item, progress: 100, message: "Hoàn tất!" } : item,
            ),
          );
          pollTimers.current.delete(itemId);
          return;
        }

        if (status.status === "failed") {
          pollTimers.current.delete(itemId);
          return;
        }

        // Continue polling every 5 seconds
        pollTimers.current.set(itemId, setTimeout(() => poll(), 5000));
      } catch {
        setItems((prev) =>
          prev.map((item) =>
            item.id === itemId ? { ...item, status: "failed", error: "Lỗi khi kiểm tra tiến trình" } : item,
          ),
        );
        pollTimers.current.delete(itemId);
      }
    };
    poll();
  }, []);

  const handleFileChange = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = e.target.files;
      if (!files || files.length === 0 || !session) return;

      // Create upload items for all selected files
      const newItems: UploadItem[] = Array.from(files).map((file) => ({
        id: crypto.randomUUID(),
        file,
        status: "uploading" as const,
        progress: 5,
        message: "Đang tải lên...",
        error: null,
        taskId: null,
      }));

      setItems((prev) => [...prev, ...newItems]);

      // Upload all files in parallel
      const uploadPromises = newItems.map(async (item) => {
        try {
          const result = await documentsApi.upload(item.file);

          setItems((prev) =>
            prev.map((i) =>
              i.id === item.id
                ? { ...i, status: "processing", progress: 10, message: "Đang xử lý...", taskId: result.task_id }
                : i,
            ),
          );

          pollProgress(item.id, result.task_id);
        } catch {
          setItems((prev) =>
            prev.map((i) =>
              i.id === item.id
                ? { ...i, status: "failed", error: "Tải lên thất bại" }
                : i,
            ),
          );
          toast.error(`Tải lên thất bại: ${item.file.name}`);
        }
      });

      // Fire all uploads in parallel, don't await here to allow UI updates
      Promise.allSettled(uploadPromises);

      // Reset file input so the same files can be re-selected
      e.target.value = "";
    },
    [session, pollProgress],
  );

  const handleOpenChange = useCallback(
    (nextOpen: boolean) => {
      if (!nextOpen && hasActive) {
        // Don't close while uploads are active
        return;
      }
      setOpen(nextOpen);
      if (!nextOpen) {
        // Notify parent if any upload completed successfully
        const anyDone = items.some((i) => i.status === "done");
        resetState();
        if (anyDone) onUploaded();
      }
    },
    [hasActive, items, resetState, onUploaded],
  );

  const allDone = items.length > 0 && items.every((i) => i.status === "done" || i.status === "failed");

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <Button className="gap-2" onClick={() => setOpen(true)}>
        <Upload className="h-4 w-4" />
        Tải tài liệu lên
      </Button>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Tải tài liệu lên</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          {items.length === 0 ? (
            <div className="grid w-full max-w-sm items-center gap-1.5">
              <label
                htmlFor="file-upload"
                className="border-2 border-dashed rounded-lg p-8 text-center cursor-pointer hover:border-primary/50 transition-colors"
              >
                <Upload className="mx-auto h-8 w-8 text-muted-foreground mb-2" />
                <p className="text-sm text-muted-foreground">
                  Click hoặc kéo thả file vào đây
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                  PDF, DOCX, XLSX, TXT, MD — chọn nhiều file để tải song song
                </p>
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
                    <span className="text-xs text-muted-foreground ml-auto shrink-0">
                      {item.progress}%
                    </span>
                  </div>
                  <Progress value={item.progress} />
                  <p className="text-xs text-muted-foreground">
                    {item.error ? (
                      <span className="text-destructive">{item.error}</span>
                    ) : (
                      item.message
                    )}
                  </p>
                </div>
              ))}
            </div>
          )}

          {items.length > 0 && (
            <div className="flex justify-between items-center">
              {!allDone && (
                <p className="text-xs text-muted-foreground">
                  Đang xử lý {items.filter((i) => i.status === "processing" || i.status === "uploading").length}/{items.length} file(s)
                </p>
              )}
              {allDone && (
                <p className="text-xs text-muted-foreground">
                  {items.filter((i) => i.status === "done").length}/{items.length} file(s) hoàn tất
                </p>
              )}
              <div className="flex gap-2">
                {!allDone && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={cancelAllPolling}
                    className="gap-1"
                  >
                    <X className="h-3 w-3" />
                    Hủy
                  </Button>
                )}
                <Button
                  variant={allDone ? "default" : "outline"}
                  size="sm"
                  onClick={() => {
                    if (allDone) {
                      const anyDone = items.some((i) => i.status === "done");
                      resetState();
                      if (anyDone) onUploaded();
                      setOpen(false);
                    }
                  }}
                  disabled={!allDone}
                  className="gap-1"
                >
                  Đóng
                </Button>
              </div>
            </div>
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
