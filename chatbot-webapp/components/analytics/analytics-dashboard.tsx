"use client";

import { useCallback, useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { Brain, Cpu, Network, RefreshCw, ThumbsDown, TimerReset, Trash2 } from "lucide-react";

import { analyticsApi } from "@/lib/api-client";
import { formatDateTimeVN, formatLatency, formatNumber, formatVnd, microsVndToRoundedVnd } from "@/lib/format";
import type { AnalyticsStats, ModelTypeStats, RecentRequest } from "@/types/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { cn } from "@/lib/utils";

type AnalyticsDashboardProps = {
  title: string;
  subtitle: string;
  allowClear?: boolean;
};

const DATE_RANGES = [
  { label: "1 ngày", value: 1 },
  { label: "7 ngày", value: 7 },
  { label: "30 ngày", value: 30 },
];

function CostText({ micros }: { micros: number }) {
  return <>{formatVnd(microsVndToRoundedVnd(micros))}</>;
}

function ModelTypeCard({
  title,
  stats,
  icon: Icon,
  gradientClass = "from-blue-500/20 to-purple-500/20",
  iconColor = "text-blue-500",
}: {
  title: string;
  stats: ModelTypeStats;
  icon: typeof Brain;
  gradientClass?: string;
  iconColor?: string;
}) {
  return (
    <Card className={cn("relative overflow-hidden bg-white/40 dark:bg-black/40 backdrop-blur-xl border-white/20 dark:border-white/10 shadow-lg hover:shadow-2xl hover:-translate-y-1 transition-all duration-300", "bg-gradient-to-br", gradientClass)}>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="flex items-center gap-3 text-sm font-semibold">
          <div className={cn("p-2 rounded-xl bg-background/50 backdrop-blur-md shadow-sm", iconColor)}>
            <Icon className="h-4 w-4" />
          </div>
          {title}
        </CardTitle>
        <span className="text-xs font-medium px-2.5 py-1 rounded-full bg-background/50 backdrop-blur-md shadow-sm">{formatNumber(stats.call_count)} lượt</span>
      </CardHeader>
      <CardContent className="space-y-3 text-sm mt-2">
        <div className="flex items-center justify-between">
          <span className="text-muted-foreground font-medium">Token vào</span>
          <span className="font-bold">{formatNumber(stats.tokens_in)}</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-muted-foreground font-medium">Token ra</span>
          <span className="font-bold">{formatNumber(stats.tokens_out)}</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-muted-foreground font-medium">Độ trễ TB</span>
          <span className="font-bold">{formatLatency(stats.avg_latency_ms)}</span>
        </div>
        <div className="flex items-center justify-between pt-2 border-t border-border/40">
          <span className="text-muted-foreground font-medium">Chi phí</span>
          <span className="font-bold text-primary">
            <CostText micros={stats.cost_micros_vnd} />
          </span>
        </div>
      </CardContent>
    </Card>
  );
}

function RequestRow({ row }: { row: RecentRequest }) {
  return (
    <TableRow>
      <TableCell className="pr-4 text-sm font-medium">{row.model_name}</TableCell>
      <TableCell className="pr-4 text-sm">{row.model_type}</TableCell>
      <TableCell className="pr-4 text-right text-sm">{formatNumber(row.tokens_in)}</TableCell>
      <TableCell className="pr-4 text-right text-sm">{formatNumber(row.tokens_out)}</TableCell>
      <TableCell className="pr-4 text-right text-sm">{formatLatency(row.latency_ms)}</TableCell>
      <TableCell className="pr-4 text-right text-sm">
        <CostText micros={row.cost_micros_vnd} />
      </TableCell>
      <TableCell className="text-right text-xs text-muted-foreground">{formatDateTimeVN(row.created_at)}</TableCell>
    </TableRow>
  );
}

export function AnalyticsDashboard({ title, subtitle, allowClear = false }: AnalyticsDashboardProps) {
  const { data: session } = useSession();
  const [stats, setStats] = useState<AnalyticsStats | null>(null);
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(true);
  const [clearing, setClearing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadStats = useCallback(async () => {
    if (!session) return;
    try {
      setLoading(true);
      setError(null);
      const nextStats = await analyticsApi.getStats(days);
      setStats(nextStats);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không thể tải thống kê");
    } finally {
      setLoading(false);
    }
  }, [days, session]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadStats();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadStats]);

  const handleClear = useCallback(async () => {
    try {
      setClearing(true);
      await analyticsApi.clearStats();
      await loadStats();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không thể xóa thống kê");
    } finally {
      setClearing(false);
    }
  }, [loadStats]);

  if (loading && !stats) {
    return (
      <div className="space-y-6 p-6">
        <Skeleton className="h-12" />
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <Skeleton key={index} className="h-32" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8 p-6 md:p-8 min-h-screen bg-gradient-to-br from-slate-50 via-white to-slate-50 dark:from-slate-950 dark:via-background dark:to-slate-900">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold tracking-tight md:text-3xl">{title}</h1>
          <p className="max-w-3xl text-sm leading-6 text-muted-foreground">{subtitle}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {DATE_RANGES.map((range) => (
            <Button
              key={range.value}
              size="sm"
                className=""
              variant={days === range.value ? "default" : "outline"}
              onClick={() => setDays(range.value)}
            >
              {range.label}
            </Button>
          ))}
          <Button size="sm" variant="outline" className="rounded-2xl" onClick={loadStats} disabled={loading}>
            <RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            Làm mới
          </Button>
          {allowClear && (
            <Button size="sm" variant="destructive" className="rounded-2xl" onClick={handleClear} disabled={clearing}>
              <Trash2 className="mr-2 h-4 w-4" />
              {clearing ? "Đang xóa..." : "Xóa usage"}
            </Button>
          )}
        </div>
      </div>

      {error && (
        <Card className="rounded-3xl border-destructive/50 shadow-sm">
          <CardContent className="pt-6 text-sm text-destructive">{error}</CardContent>
        </Card>
      )}

      {stats && (
        <>
          <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-5">
            <Card className="bg-white/40 dark:bg-black/40 backdrop-blur-xl border-white/20 dark:border-white/10 shadow-lg hover:shadow-xl hover:-translate-y-1 transition-all duration-300">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">Tổng request</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{formatNumber(stats.total_messages)}</div>
                <p className="text-xs text-muted-foreground">Theo cửa sổ {days} ngày</p>
              </CardContent>
            </Card>
            <Card className="bg-white/40 dark:bg-black/40 backdrop-blur-xl border-white/20 dark:border-white/10 shadow-lg hover:shadow-xl hover:-translate-y-1 transition-all duration-300">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">Tổng token</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{formatNumber(stats.total_tokens)}</div>
                <p className="text-xs text-muted-foreground">
                  In {formatNumber(stats.total_tokens_in)} • Out {formatNumber(stats.total_tokens_out)}
                </p>
              </CardContent>
            </Card>
            <Card className="bg-white/40 dark:bg-black/40 backdrop-blur-xl border-white/20 dark:border-white/10 shadow-lg hover:shadow-xl hover:-translate-y-1 transition-all duration-300">
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
                  <div className="p-1.5 rounded-md bg-orange-500/10 text-orange-500">
                    <TimerReset className="h-4 w-4" />
                  </div>
                  Độ trễ trung bình
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{formatLatency(stats.avg_latency_ms)}</div>
                <p className="text-xs text-muted-foreground">Theo request đã ghi nhận</p>
              </CardContent>
            </Card>
            <Card className="bg-white/40 dark:bg-black/40 backdrop-blur-xl border-white/20 dark:border-white/10 shadow-lg hover:shadow-xl hover:-translate-y-1 transition-all duration-300 relative overflow-hidden">
              <div className="absolute top-0 right-0 p-4 opacity-10">
                <span className="text-6xl font-black">$</span>
              </div>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">Chi phí ước tính</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{formatVnd(stats.cost_vnd_rounded)}</div>
                <p className="text-xs text-muted-foreground">
                  {stats.currency_code} • model {stats.pricing.model}
                </p>
              </CardContent>
            </Card>
            <Card className="bg-white/40 dark:bg-black/40 backdrop-blur-xl border-white/20 dark:border-white/10 shadow-lg hover:shadow-xl hover:-translate-y-1 transition-all duration-300">
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
                  <div className="p-1.5 rounded-md bg-destructive/10 text-destructive">
                    <ThumbsDown className="h-4 w-4" />
                  </div>
                  Tỷ lệ dislike
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{Math.round((stats.feedback_summary.dislike_rate || 0) * 100)}%</div>
                <p className="text-xs text-muted-foreground">
                  {formatNumber(stats.feedback_summary.dislike_count)} dislike • {formatNumber(stats.feedback_summary.like_count)} like
                </p>
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-6 lg:grid-cols-3 mt-4">
            <ModelTypeCard title="LLM" stats={stats.by_model_type.llm} icon={Brain} gradientClass="from-blue-500/10 to-cyan-500/10" iconColor="text-blue-500" />
            <ModelTypeCard title="Embedding" stats={stats.by_model_type.embedding} icon={Cpu} gradientClass="from-emerald-500/10 to-teal-500/10" iconColor="text-emerald-500" />
            <ModelTypeCard title="Reranker" stats={stats.by_model_type.reranker} icon={Network} gradientClass="from-purple-500/10 to-pink-500/10" iconColor="text-purple-500" />
          </div>

          <Card className="bg-white/40 dark:bg-black/40 backdrop-blur-xl border-white/20 dark:border-white/10 shadow-lg mt-4">
            <CardHeader>
              <CardTitle>Yêu cầu gần đây</CardTitle>
              <CardDescription>
                Giúp kiểm tra model nào đang tiêu tốn nhiều nhất trong cửa sổ hiện tại.
              </CardDescription>
              <CardDescription>
                Embedding và reranker thường chỉ có token vào hoặc số ước tính theo request, nên token ra có thể bằng 0 là bình thường.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {stats.recent_requests.length === 0 ? (
                <p className="text-sm text-muted-foreground">Chưa có request nào trong khoảng thời gian này.</p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="pr-4 text-xs text-muted-foreground">Model</TableHead>
                      <TableHead className="pr-4 text-xs text-muted-foreground">Loại</TableHead>
                      <TableHead className="pr-4 text-right text-xs text-muted-foreground">In</TableHead>
                      <TableHead className="pr-4 text-right text-xs text-muted-foreground">Out</TableHead>
                      <TableHead className="pr-4 text-right text-xs text-muted-foreground">Độ trễ</TableHead>
                      <TableHead className="pr-4 text-right text-xs text-muted-foreground">Chi phí</TableHead>
                      <TableHead className="text-right text-xs text-muted-foreground">Thời điểm</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {stats.recent_requests.map((row, index) => (
                      <RequestRow key={`${row.model_name}-${row.created_at}-${index}`} row={row} />
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>

          <Card className="bg-white/40 dark:bg-black/40 backdrop-blur-xl border-white/20 dark:border-white/10 shadow-lg mt-4">
            <CardHeader>
              <CardTitle>Phản hồi chất lượng</CardTitle>
              <CardDescription>
                Theo dõi dislike để biết tài liệu nào cần cải thiện retrieval hoặc instruction.
              </CardDescription>
            </CardHeader>
            <CardContent className="grid gap-6 lg:grid-cols-2">
              <div className="space-y-3">
                <div className="text-sm font-medium">Tài liệu bị dislike nhiều</div>
                {stats.feedback_summary.top_disliked_documents.length === 0 ? (
                  <p className="text-sm text-muted-foreground">Chưa có dislike nào trong cửa sổ hiện tại.</p>
                ) : (
                  <div className="space-y-2">
                    {stats.feedback_summary.top_disliked_documents.map((item) => (
                      <div
                        key={item.document_id}
                        className="flex items-center justify-between rounded-xl border px-3 py-2"
                      >
                        <div className="min-w-0 truncate pr-3 text-sm font-medium">{item.title}</div>
                        <div className="shrink-0 text-xs text-muted-foreground">{formatNumber(item.count)} dislike</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
              <div className="space-y-3">
                <div className="text-sm font-medium">Section bị dislike nhiều</div>
                {stats.feedback_summary.top_disliked_sections.length === 0 ? (
                  <p className="text-sm text-muted-foreground">Chưa có section nào cần ưu tiên xử lý.</p>
                ) : (
                  <div className="space-y-2">
                    {stats.feedback_summary.top_disliked_sections.map((item) => (
                      <div
                        key={`${item.document_id}-${item.section_id}`}
                        className="flex items-center justify-between rounded-xl border px-3 py-2"
                      >
                        <div className="min-w-0 truncate pr-3 text-sm font-medium">{item.heading}</div>
                        <div className="shrink-0 text-xs text-muted-foreground">{formatNumber(item.count)} dislike</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
