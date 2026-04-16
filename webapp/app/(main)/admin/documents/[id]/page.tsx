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
import { ArrowLeft, Search, ChevronDown, ChevronRight, Loader2 } from "lucide-react";
import Link from "next/link";
import { documentsApi, treeApi } from "@/lib/api-client";
import type { DocumentDetail, TreeNode } from "@/types/api";

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
      if (!session?.accessToken || !docId) return;
      if (offset === 0) setLoading(true);
      else setLoadingMore(true);

      try {
        if (offset === 0) {
          const docData = await documentsApi.get(docId, session.accessToken);
          setDoc(docData);
        }
        const treeData = await treeApi.get(docId, session.accessToken, offset, PAGE_SIZE);
        if (append) {
          setNodes((prev) => [...prev, ...treeData.nodes]);
        } else {
          setNodes(treeData.nodes);
        }
        setTotalNodes(treeData.total_nodes);
        setHasMore(offset + PAGE_SIZE < treeData.total_nodes);
      } finally {
        setLoading(false);
        setLoadingMore(false);
      }
    },
    [session?.accessToken, docId],
  );

  // Initial load
  useEffect(() => {
    fetchPage(0, false);
  }, [fetchPage]);

  // Search — load all matching (server-side search)
  useEffect(() => {
    if (!searchQuery || !session?.accessToken || !docId) return;
    const timer = setTimeout(() => {
      treeApi
        .search(docId, searchQuery, session.accessToken)
        .then((data) => {
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
          setNodes(searchNodes);
          setTotalNodes(searchNodes.length);
          setHasMore(false);
        })
        .catch(() => {});
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery, session?.accessToken, docId]);

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
      <div className="flex items-center gap-3">
        <Link href="/admin/documents">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
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
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>
            Nội dung tài liệu ({nodes.length}/{totalNodes})
          </CardTitle>
          <div className="relative w-64">
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
              <ScrollArea className="h-[500px]">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-12">#</TableHead>
                      <TableHead className="w-16">Trang</TableHead>
                      <TableHead>Tiêu đề</TableHead>
                      <TableHead className="w-20">Ký tự</TableHead>
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
                        accessToken={session?.accessToken || ""}
                      />
                    ))}
                  </TableBody>
                </Table>
              </ScrollArea>

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
  accessToken,
}: {
  node: TreeNode;
  docId: string;
  index: number;
  isExpanded: boolean;
  onToggle: () => void;
  accessToken: string;
}) {
  const [nodeText, setNodeText] = useState<string | null>(null);
  const [loadingText, setLoadingText] = useState(false);

  useEffect(() => {
    if (isExpanded && nodeText === null && !loadingText) {
      setLoadingText(true);
      treeApi
        .getNode(docId, node.node_id, accessToken)
        .then((detail) => setNodeText(detail.text))
        .catch(() => setNodeText("(Lỗi tải nội dung)"))
        .finally(() => setLoadingText(false));
    }
  }, [isExpanded, nodeText, loadingText, docId, node.node_id, accessToken]);

  return (
    <>
      <TableRow className="cursor-pointer hover:bg-muted/50" onClick={onToggle}>
        <TableCell className="text-xs text-muted-foreground">{index}</TableCell>
        <TableCell className="text-xs text-muted-foreground">{node.page_number || "?"}</TableCell>
        <TableCell className="font-medium text-sm truncate max-w-[500px]">{node.title}</TableCell>
        <TableCell className="text-xs text-muted-foreground">
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
