"use client";

import { useState, useCallback } from "react";
import { useSession } from "next-auth/react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Upload } from "lucide-react";
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

  const pollProgress = useCallback(
    async (id: string, token: string) => {
      const poll = async () => {
        try {
          const status = await documentsApi.getStatus(id, token);
          setProgress(status.progress.percent);
          setStatusMessage(status.status_message || status.stage || "");

          if (status.status === "ready") {
            setProgress(100);
            setStatusMessage("Hoàn tất!");
            setTimeout(() => {
              setOpen(false);
              setProgress(0);
              setStatusMessage("");
              onUploaded();
            }, 1000);
            return;
          }

          if (status.status === "failed") {
            toast.error(status.error || "Xử lý tài liệu thất bại");
            setUploading(false);
            return;
          }

          // Continue polling
          setTimeout(() => poll(), 2000);
        } catch {
          toast.error("Lỗi khi kiểm tra tiến trình");
          setUploading(false);
        }
      };
      poll();
    },
    [onUploaded],
  );

  const handleFileChange = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file || !session?.accessToken) return;

      setUploading(true);
      setProgress(5);
      setStatusMessage("Đang tải lên...");

      try {
        const result = await documentsApi.upload(file, session.accessToken);
        setProgress(10);
        setStatusMessage("Đang xử lý...");
        pollProgress(result.task_id, session.accessToken);
      } catch {
        toast.error("Tải lên thất bại. Vui lòng thử lại.");
        setUploading(false);
      }
    },
    [session, pollProgress],
  );

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <Button className="gap-2" onClick={() => setOpen(true)}>
        <Upload className="h-4 w-4" />
        Tải tài liệu lên
      </Button>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Tải tài liệu lên</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          {!uploading ? (
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
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
