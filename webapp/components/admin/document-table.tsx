"use client";

import { useEffect, useState, useCallback } from "react";
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
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Eye, Trash2, FileText } from "lucide-react";
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

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function DocumentTable() {
  const { data: session } = useSession();
  const router = useRouter();
  const [docs, setDocs] = useState<DocumentSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);

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
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">Tài liệu</h2>
          <p className="text-sm text-muted-foreground">{docs.length} tài liệu</p>
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
                <TableCell colSpan={7} className="text-center py-8 text-muted-foreground">
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
                    <Badge variant="outline" className={statusVariant(doc.status)}>
                      {doc.status}
                    </Badge>
                  </TableCell>
                  <TableCell>{doc.progress_percent}%</TableCell>
                  <TableCell className="text-muted-foreground text-xs">
                    {new Date(doc.created_at).toLocaleDateString("vi-VN")}
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex gap-1 justify-end">
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => router.push(`/admin/documents/${doc.document_id}`)}
                      >
                        <Eye className="h-4 w-4" />
                      </Button>
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
            Bạn có chắc muốn xóa tài liệu này? Hành động này không thể hoàn tác.
          </p>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>
              Hủy
            </Button>
            <Button
              variant="destructive"
              onClick={() => deleteTarget && handleDelete(deleteTarget)}
            >
              Xóa
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
