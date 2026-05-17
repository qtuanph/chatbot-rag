"use client";

import { useEffect, useState, useCallback } from "react";
import { useSession } from "next-auth/react";
import { useParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ArrowLeft, Search, ChevronDown, ChevronRight, Loader2, AlertCircle } from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";
import { documentsApi, treeApi } from "@/lib/api-client";
import type { DocumentDetail, TreeNode } from "@/types/api";

function simplifyMimeType(mime: string) {
  if (!mime) return "Unknown";
  const m = mime.toLowerCase();
  if (m.includes("word") || m.includes("officedocument.wordprocessingml")) return "DOCX";
  if (m.includes("pdf")) return "PDF";
  if (m.includes("excel") || m.includes("officedocument.spreadsheetml")) return "XLSX";
  if (m.includes("powerpoint") || m.includes("officedocument.presentationml")) return "PPTX";
  if (m.includes("text/plain")) return "TXT";
  if (m.includes("text/markdown")) return "MD";
  return mime.split("/").pop()?.toUpperCase() || mime;
}

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

const PAGE_SIZE = 20;

export default function DocumentDetailPage() {
  const { data: session } = useSession();
  const params = useParams();
  const docId = params.id as string;
  const [doc, setDoc] = useState<DocumentDetail | null>(null);
  const [nodes, setNodes] = useState<TreeNode[]>([]);
  const [totalNodes, setTotalNodes] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [expandedNode, setExpandedNode] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(false);

  const fetchPage = useCallback(
    async (offset: number, append: boolean) => {
      if (!session || !docId) return;
      if (offset === 0) setLoading(true);
      else setLoadingMore(true);

      try {
        if (offset === 0) {
          const docData = await documentsApi.get(docId);
          setDoc(docData);
        }
        const treeData = await treeApi.get(docId, offset, PAGE_SIZE);
        if (append) {
          setNodes((prev) => [...prev, ...treeData.nodes]);
        } else {
          setNodes(treeData.nodes);
        }
        setTotalNodes(treeData.total_nodes);
        setHasMore(offset + PAGE_SIZE < treeData.total_nodes);
      } catch (error) {
        console.error("Fetch page error:", error);
        toast.error("Không thể tải dữ liệu tài liệu. Vui lòng thử lại.");
      } finally {
        setLoading(false);
        setLoadingMore(false);
      }
    },
    [session, docId],
  );

  // Initial load
  useEffect(() => {
    const timer = setTimeout(() => {
      void fetchPage(0, false);
    }, 0);
    return () => clearTimeout(timer);
  }, [fetchPage]);

  // Search — load all matching (server-side search)
  useEffect(() => {
    const normalizedQuery = searchQuery.trim();
    if (!session || !docId) return;

    if (!normalizedQuery) {
      const timer = setTimeout(() => {
        setExpandedNode(null);
        void fetchPage(0, false);
      }, 0);
      return () => clearTimeout(timer);
    }

    let cancelled = false;

    const timer = setTimeout(() => {
      treeApi
        .search(docId, normalizedQuery.slice(0, 500))
        .then((data) => {
          if (cancelled) return;
          // Convert search results to display format
          const results = ((data.results || []) as Array<{ node_id: string; title: string; preview?: string }>);
          const searchNodes: TreeNode[] = results.map((r) => ({
            node_id: r.node_id,
            title: r.title,
            level: 0,
            breadcrumb: r.title,
            parent_id: null,
            child_count: 0,
            text_length: r.preview?.length || 0,
            page_number: "?",
          }));
          setExpandedNode(null);
          setNodes(searchNodes);
          setTotalNodes(searchNodes.length);
          setHasMore(false);
        })
        .catch((err) => {
          console.error("Search error:", err);
          if (!cancelled) {
            toast.error("Lỗi khi tìm kiếm nội dung.");
          }
        });
    }, 300);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [searchQuery, session, docId, fetchPage]);

  if (loading && nodes.length === 0) {
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
      <div className="flex flex-col sm:flex-row sm:items-center gap-3">
        <div className="flex items-center gap-3">
          <Link href="/admin/documents">
            <Button variant="ghost" size="icon">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <div className="min-w-0">
            <h1 className="text-xl font-bold truncate">{doc.file_name}</h1>
            <p className="text-sm text-muted-foreground truncate">
              v{doc.version} · {formatSize(doc.file_size)} · {simplifyMimeType(doc.file_type)}
            </p>
          </div>
        </div>
        <div className="ml-auto sm:ml-0">
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
      </div>

      {/* Info Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {[
          { label: "Trạng thái", value: doc.stage },
          { label: "Tiến trình", value: `${doc.progress_percent}%` },
          { label: "Tổng nodes", value: totalNodes.toString() },
          { label: "Ngày tạo", value: new Date(doc.created_at).toLocaleString("vi-VN") },
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

      {/* Node Table */}
      <Card>
        <CardHeader className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <CardTitle className="text-lg">
            Nội dung tài liệu ({nodes.length}/{totalNodes})
          </CardTitle>
          <div className="relative w-full sm:w-64">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Tìm kiếm nội dung..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9 h-9"
            />
          </div>
        </CardHeader>
        <CardContent>
          {nodes.length === 0 ? (
            <p className="text-sm text-muted-foreground py-4">Không có dữ liệu.</p>
          ) : (
            <>
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-12">#</TableHead>
                      <TableHead className="w-16">Trang</TableHead>
                      <TableHead className="min-w-[200px]">Tiêu đề</TableHead>
                      <TableHead className="w-20 hidden sm:table-cell">Ký tự</TableHead>
                      <TableHead className="w-10"></TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {nodes.map((node, idx) => (
                      <NodeRow
                        key={node.node_id}
                        node={node}
                        docId={docId}
                        index={idx + 1}
                        isExpanded={expandedNode === node.node_id}
                        onToggle={() =>
                          setExpandedNode(expandedNode === node.node_id ? null : node.node_id)
                        }
                      />
                    ))}
                  </TableBody>
                  </Table>
                </div>

              {/* Load More */}
              {hasMore && !searchQuery && (
                <div className="flex justify-center pt-4">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={loadingMore}
                    onClick={() => fetchPage(nodes.length, true)}
                  >
                    {loadingMore ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin mr-2" />
                        Đang tải...
                      </>
                    ) : (
                      `Tải thêm (${totalNodes - nodes.length} còn lại)`
                    )}
                  </Button>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function NodeRow({
  node,
  docId,
  index,
  isExpanded,
  onToggle,
}: {
  node: TreeNode;
  docId: string;
  index: number;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  const [nodeText, setNodeText] = useState<string | null>(null);
  const [loadingText, setLoadingText] = useState(false);

  const handleToggle = () => {
    if (!isExpanded && nodeText === null && !loadingText) {
      setLoadingText(true);
      treeApi
        .getNode(docId, node.node_id)
        .then((detail) => setNodeText(detail.text))
        .catch(() => setNodeText("(Lỗi tải nội dung)"))
        .finally(() => setLoadingText(false));
    }
    onToggle();
  };

  return (
    <>
      <TableRow className="cursor-pointer hover:bg-muted/50" onClick={handleToggle}>
        <TableCell className="text-xs text-muted-foreground">{index}</TableCell>
        <TableCell className="text-xs text-muted-foreground">{node.page_range || node.page_number || "?"}</TableCell>
        <TableCell className="font-medium text-sm truncate max-w-[200px] sm:max-w-[500px]">{node.title}</TableCell>
        <TableCell className="text-xs text-muted-foreground hidden sm:table-cell">
          {node.text_length?.toLocaleString()}
        </TableCell>
        <TableCell>
          {node.text_length > 0 &&
            (isExpanded ? (
              <ChevronDown className="h-4 w-4 text-muted-foreground" />
            ) : (
              <ChevronRight className="h-4 w-4 text-muted-foreground" />
            ))}
        </TableCell>
      </TableRow>
      {isExpanded && (
        <TableRow>
          <TableCell colSpan={5} className="bg-muted/30">
            {loadingText ? (
              <p className="text-xs text-muted-foreground p-2">Đang tải...</p>
            ) : nodeText ? (
              <pre className="text-xs whitespace-pre-wrap font-sans leading-relaxed max-h-[300px] overflow-auto p-2">
                {nodeText}
              </pre>
            ) : null}
          </TableCell>
        </TableRow>
      )}
    </>
  );
}
