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
import { Upload, X } from "lucide-react";
import { documentsApi } from "@/lib/api-client";
import { toast } from "sonner";

interface UploadDialogProps {
  onUploaded: () => void;
}

export function UploadDialog({ onUploaded }: UploadDialogProps) {
  const { data: session } = useSession();
  const [open, setOpen] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [statusMessage, setStatusMessage] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const cancelledRef = useRef(false);

  const cancelPolling = useCallback(() => {
    cancelledRef.current = true;
    if (pollTimerRef.current) {
      clearTimeout(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  }, []);

  const resetState = useCallback(() => {
    setUploading(false);
    setProgress(0);
    setStatusMessage("");
    setErrorMessage(null);
    cancelledRef.current = false;
  }, []);

  const pollProgress = useCallback(
    async (id: string, token: string) => {
      cancelledRef.current = false;

      const poll = async () => {
        if (cancelledRef.current) return;

        try {
          const status = await documentsApi.getStatus(id, token);
          setProgress(status.progress.percent);
          setStatusMessage(status.status_message || status.stage || "");

          if (status.status === "ready") {
            setProgress(100);
            setStatusMessage("Hoàn tất!");
            setTimeout(() => {
              setOpen(false);
              resetState();
              onUploaded();
            }, 1000);
            return;
          }

          if (status.status === "failed") {
            const msg = status.error || "Xử lý tài liệu thất bại";
            setErrorMessage(msg);
            toast.error(msg);
            setUploading(false);
            return;
          }

          // Continue polling
          pollTimerRef.current = setTimeout(() => poll(), 2000);
        } catch {
          toast.error("Lỗi khi kiểm tra tiến trình");
          setUploading(false);
        }
      };
      poll();
    },
    [onUploaded, resetState],
  );

  const handleFileChange = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file || !session?.accessToken) return;

      setUploading(true);
      setProgress(5);
      setStatusMessage("Đang tải lên...");
      setErrorMessage(null);

      try {
        const result = await documentsApi.upload(file, session.accessToken);
        setProgress(10);
        setStatusMessage("Đang xử lý...");
        pollProgress(result.task_id, session.accessToken);
      } catch {
        toast.error("Tải lên thất bại. Vui lòng thử lại.");
        setUploading(false);
      }

      // Reset file input so the same file can be re-selected
      e.target.value = "";
    },
    [session, pollProgress],
  );

  const handleCancel = useCallback(() => {
    cancelPolling();
    resetState();
  }, [cancelPolling, resetState]);

  const handleOpenChange = useCallback(
    (nextOpen: boolean) => {
      if (!nextOpen && uploading) {
        // Don't close while uploading — user must cancel first
        return;
      }
      setOpen(nextOpen);
      if (!nextOpen) {
        cancelPolling();
        resetState();
      }
    },
    [uploading, cancelPolling, resetState],
  );

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
          {!uploading && !errorMessage ? (
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
                  PDF, DOCX, XLSX, TXT, MD (tối đa 50MB)
                </p>
              </label>
              <input
                id="file-upload"
                type="file"
                className="hidden"
                accept=".pdf,.docx,.doc,.xlsx,.xls,.txt,.md"
                onChange={handleFileChange}
              />
            </div>
          ) : (
            <div className="space-y-3">
              <Progress value={progress} />
              <p className="text-sm text-muted-foreground">{statusMessage}</p>
              <p className="text-xs text-muted-foreground">{progress}%</p>
              {errorMessage && (
                <p className="text-sm text-destructive">{errorMessage}</p>
              )}
              <div className="flex justify-end gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleCancel}
                  className="gap-1"
                >
                  <X className="h-3 w-3" />
                  {errorMessage ? "Đóng" : "Hủy"}
                </Button>
                {errorMessage && (
                  <Button
                    size="sm"
                    onClick={() => {
                      resetState();
                      // Re-trigger file input click
                      document.getElementById("file-upload")?.click();
                    }}
                    className="gap-1"
                  >
                    <Upload className="h-3 w-3" />
                    Tải lại
                  </Button>
                )}
              </div>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
