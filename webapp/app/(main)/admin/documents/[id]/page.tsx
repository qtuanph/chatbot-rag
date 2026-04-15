"use client";

import { useEffect, useState, useCallback } from "react";
import { useSession } from "next-auth/react";
import { useParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Button } from "@/components/ui/button";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { documentsApi, treeApi } from "@/lib/api-client";
import { DocumentTree } from "@/components/admin/document-tree";
import type { DocumentDetail, TreeResponse } from "@/types/api";

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function DocumentDetailPage() {
  const { data: session } = useSession();
  const params = useParams();
  const docId = params.id as string;
  const [doc, setDoc] = useState<DocumentDetail | null>(null);
  const [tree, setTree] = useState<TreeResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!session?.accessToken || !docId) return;

    Promise.all([
      documentsApi.get(docId, session.accessToken),
      treeApi.get(docId, session.accessToken).catch(() => null),
    ])
      .then(([docData, treeData]) => {
        setDoc(docData);
        setTree(treeData);
      })
      .finally(() => setLoading(false));
  }, [session?.accessToken, docId]);

  if (loading) {
    return (
      <div className="p-6 space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64" />
      </div>
    );
  }

  if (!doc) {
    return (
      <div className="p-6">
        <p className="text-muted-foreground">Không tìm thấy tài liệu</p>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" asChild>
          <Link href="/admin/documents">
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <div>
          <h1 className="text-xl font-bold truncate">{doc.file_name}</h1>
          <p className="text-sm text-muted-foreground">
            v{doc.version} · {formatSize(doc.file_size)} · {doc.file_type}
          </p>
        </div>
        <Badge
          variant="outline"
          className={
            doc.status === "ready"
              ? "bg-green-500/15 text-green-700"
              : doc.status === "failed"
                ? "bg-red-500/15 text-red-700"
                : "bg-blue-500/15 text-blue-700"
          }
        >
          {doc.status}
        </Badge>
      </div>

      {/* Info Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {[
          { label: "Trạng thái", value: doc.stage },
          { label: "Tiến trình", value: `${doc.progress_percent}%` },
          { label: "Ngày tạo", value: new Date(doc.created_at).toLocaleString("vi-VN") },
          { label: "Cập nhật", value: new Date(doc.updated_at).toLocaleString("vi-VN") },
        ].map((item) => (
          <Card key={item.label}>
            <CardHeader className="pb-1">
              <CardTitle className="text-xs text-muted-foreground">{item.label}</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm font-medium">{item.value}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {doc.parse_error && (
        <Card className="border-destructive">
          <CardHeader className="pb-1">
            <CardTitle className="text-xs text-destructive">Lỗi phân tích</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm">{doc.parse_error}</p>
          </CardContent>
        </Card>
      )}

      {/* Tree Visualization */}
      <Card>
        <CardHeader>
          <CardTitle>Cấu trúc tài liệu</CardTitle>
        </CardHeader>
        <CardContent>
          {tree ? (
            <DocumentTree
              nodes={tree.nodes}
              documentTitle={tree.document_title}
              maxDepth={tree.max_depth}
            />
          ) : (
            <p className="text-sm text-muted-foreground">
              Chưa có dữ liệu cây phân cấp cho tài liệu này.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
