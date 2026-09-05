"use client";

import { useMemo } from "react";
import { RefreshCw, ThumbsDown, ThumbsUp } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  DataTable,
  DataTableSortHeader,
  createColumnHelper,
  type DataTableFeatures,
} from "@/components/ui/data-table";
import { Skeleton } from "@/components/ui/skeleton";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { formatCompactNumber, formatDateTimeVN, formatLatency, formatNumber } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { AnalyticsStats, RecentRequest } from "@/types/api";
import { DATE_RANGES, useAnalyticsStats } from "./use-analytics-stats";

export function AnalyticsLogs({ initialStats }: { initialStats?: AnalyticsStats | null }) {
  const { days, setDays, stats, loading, error, loadStats } = useAnalyticsStats(30, initialStats);

  const recentRequestColumns = useMemo(() => {
    const columnHelper = createColumnHelper<DataTableFeatures, RecentRequest>();

    return columnHelper.columns([
      columnHelper.accessor("model_name", {
        meta: { title: "Model" },
        header: ({ column }) => <DataTableSortHeader column={column} title="Model" />,
        cell: ({ row }) => {
          const mType = row.original.model_type;
          return (
            <div className="font-mono text-xs flex items-center gap-2">
              <span
                className={cn(
                  "w-2 h-2 rounded-full shrink-0",
                  mType === "llm" ? "bg-blue-500" : mType === "embedding" ? "bg-emerald-500" : "bg-purple-500"
                )}
              />
              <span className="truncate max-w-[180px]">{row.original.model_name || "System"}</span>
            </div>
          );
        },
      }),
      columnHelper.accessor("tokens_in", {
        meta: { title: "Vào" },
        header: ({ column }) => <DataTableSortHeader column={column} title="Vào" />,
        cell: ({ row }) => (
          <Tooltip>
            <TooltipTrigger>
              <span className="font-mono text-xs cursor-default">{formatCompactNumber(row.original.tokens_in)}</span>
            </TooltipTrigger>
            <TooltipContent>{formatNumber(row.original.tokens_in)} tokens</TooltipContent>
          </Tooltip>
        ),
      }),
      columnHelper.accessor("tokens_out", {
        meta: { title: "Ra" },
        header: ({ column }) => <DataTableSortHeader column={column} title="Ra" />,
        cell: ({ row }) => (
          <Tooltip>
            <TooltipTrigger>
              <span className="font-mono text-xs cursor-default">{formatCompactNumber(row.original.tokens_out)}</span>
            </TooltipTrigger>
            <TooltipContent>{formatNumber(row.original.tokens_out)} tokens</TooltipContent>
          </Tooltip>
        ),
      }),
      columnHelper.accessor("latency_ms", {
        meta: { title: "Độ trễ" },
        header: ({ column }) => <DataTableSortHeader column={column} title="Độ trễ" />,
        cell: ({ row }) => <span className="font-mono text-xs">{formatLatency(row.original.latency_ms)}</span>,
      }),
      columnHelper.accessor("created_at", {
        meta: { title: "Thời gian" },
        header: ({ column }) => <DataTableSortHeader column={column} title="Thời gian" />,
        cell: ({ row }) => (
          <span className="text-xs text-muted-foreground font-mono">
            {formatDateTimeVN(row.original.created_at)}
          </span>
        ),
      }),
    ]);
  }, []);

  const fb = stats?.feedback_summary;

  return (
    <TooltipProvider>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Nhật ký API &amp; Đánh giá</h1>
            <p className="text-sm text-muted-foreground">
              Lịch sử các lượt truy vấn gần nhất và phản hồi chất lượng từ người dùng.
            </p>
          </div>

          <div className="flex items-center gap-2">
            {DATE_RANGES.map((r) => (
              <Button
                key={r.value}
                size="sm"
                variant={days === r.value ? "default" : "outline"}
                onClick={() => setDays(r.value)}
              >
                {r.label}
              </Button>
            ))}
            <Button size="sm" variant="outline" onClick={() => loadStats(false)} disabled={loading}>
              <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            </Button>
          </div>
        </div>

        {error && <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">{error}</div>}

        {loading && !stats ? (
          <div className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <Skeleton className="h-24 rounded-xl" />
              <Skeleton className="h-24 rounded-xl" />
            </div>
            <Skeleton className="h-64 rounded-xl" />
          </div>
        ) : stats ? (
          <div className="space-y-6">
            {/* Feedback summary cards */}
            <div className="grid gap-4 sm:grid-cols-3">
              <Card className="shadow-sm border">
                <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
                  <CardTitle className="text-xs font-medium text-muted-foreground">Tổng Đánh Giá</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold font-mono tracking-tight">{formatNumber(fb?.total ?? 0)}</div>
                  <p className="text-[11px] text-muted-foreground mt-1">Lượt phản hồi câu trả lời</p>
                </CardContent>
              </Card>

              <Card className="shadow-sm border">
                <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
                  <CardTitle className="text-xs font-medium text-muted-foreground">Hài Lòng</CardTitle>
                  <ThumbsUp className="h-4 w-4 text-emerald-500" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold font-mono text-emerald-600 dark:text-emerald-400 tracking-tight">
                    {formatNumber(fb?.like_count ?? 0)}
                  </div>
                  <p className="text-[11px] text-muted-foreground mt-1">Đánh giá hữu ích</p>
                </CardContent>
              </Card>

              <Card className="shadow-sm border">
                <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
                  <CardTitle className="text-xs font-medium text-muted-foreground">Cần Cải Thiện</CardTitle>
                  <ThumbsDown className="h-4 w-4 text-rose-500" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold font-mono text-rose-600 dark:text-rose-400 tracking-tight">
                    {formatNumber(fb?.dislike_count ?? 0)}
                  </div>
                  <p className="text-[11px] text-muted-foreground mt-1">
                    Tỷ lệ: {((fb?.dislike_rate ?? 0) * 100).toFixed(1)}%
                  </p>
                </CardContent>
              </Card>
            </div>

            {/* Recent requests table */}
            <Card className="shadow-sm border">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-semibold">Lịch sử Gọi Gần Nhất</CardTitle>
                <CardDescription className="text-xs">Chi tiết các request AI vừa được xử lý trong hệ thống.</CardDescription>
              </CardHeader>
              <CardContent className="p-4">
                <DataTable
                  columns={recentRequestColumns}
                  data={stats.recent_requests}
                  searchKey="model_name"
                  searchPlaceholder="Lọc theo model..."
                  enablePagination
                  enableColumnVisibility
                  emptyMessage="Chưa có nhật ký request nào gần đây."
                />
              </CardContent>
            </Card>

            {/* Top disliked sections / docs */}
            {((fb?.top_disliked_documents?.length ?? 0) > 0 || (fb?.top_disliked_sections?.length ?? 0) > 0) && (
              <div className="grid gap-4 md:grid-cols-2">
                {(fb?.top_disliked_documents?.length ?? 0) > 0 && (
                  <Card className="shadow-sm border">
                    <CardHeader className="pb-2">
                      <CardTitle className="text-xs font-semibold">Tài liệu cần rà soát</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-2 pt-1">
                      {fb?.top_disliked_documents.map((item) => (
                        <div key={item.document_id} className="flex items-center justify-between rounded-lg border p-2 text-xs">
                          <span className="font-medium truncate pr-2">{item.title}</span>
                          <Badge variant="destructive" className="text-[10px]">{item.count} dislike</Badge>
                        </div>
                      ))}
                    </CardContent>
                  </Card>
                )}

                {(fb?.top_disliked_sections?.length ?? 0) > 0 && (
                  <Card className="shadow-sm border">
                    <CardHeader className="pb-2">
                      <CardTitle className="text-xs font-semibold">Section cần rà soát</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-2 pt-1">
                      {fb?.top_disliked_sections.map((item) => (
                        <div key={`${item.document_id}-${item.section_id}`} className="flex items-center justify-between rounded-lg border p-2 text-xs">
                          <span className="font-medium truncate pr-2">{item.heading}</span>
                          <Badge variant="destructive" className="text-[10px]">{item.count} dislike</Badge>
                        </div>
                      ))}
                    </CardContent>
                  </Card>
                )}
              </div>
            )}
          </div>
        ) : null}
      </div>
    </TooltipProvider>
  );
}
