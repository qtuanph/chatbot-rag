"use client";

import { useEffect, useState, useCallback } from "react";
import { useSession } from "next-auth/react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { analyticsApi } from "@/lib/api-client";
import type { AnalyticsStats, ModelTypeStats, RecentRequest } from "@/types/api";
import { Clock, Hash, MessageSquare, RefreshCw, ArrowRight, ArrowLeft, Cpu, Network, Brain, Trash2 } from "lucide-react";

function formatNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toLocaleString();
}

function formatLatency(ms: number): string {
  if (ms === 0) return "—";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function formatCost(usd: number): string {
  return `$${usd.toFixed(6)}`;
}

function timeAgo(dateStr: string): string {
  const now = new Date();
  const date = new Date(dateStr);
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return "Vừa xong";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${diffDays}d ago`;
}

const DATE_RANGES = [
  { label: "Hôm nay", value: 1 },
  { label: "7 ngày", value: 7 },
  { label: "30 ngày", value: 30 },
];

const MODEL_TYPE_COLORS: Record<string, string> = {
  llm: "text-purple-500",
  embedding: "text-blue-500",
  reranker: "text-amber-500",
};

const MODEL_TYPE_LABELS: Record<string, string> = {
  llm: "LLM",
  embedding: "Embed",
  reranker: "Rerank",
};

function ModelTypeCard({
  title,
  icon: Icon,
  color,
  stats,
  hideOut = false,
}: {
  title: string;
  icon: typeof Cpu;
  color: string;
  stats: ModelTypeStats;
  hideOut?: boolean;
}) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-medium flex items-center gap-2">
          <Icon className={`h-4 w-4 ${color}`} />
          {title}
        </CardTitle>
        <span className="text-xs text-muted-foreground">{stats.call_count} calls</span>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">Token In</span>
            <span className="font-medium">{formatNumber(stats.tokens_in)}</span>
          </div>
          {!hideOut && (
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Token Out</span>
              <span className="font-medium">{formatNumber(stats.tokens_out)}</span>
            </div>
          )}
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">Latency TB</span>
            <span className="font-medium">{formatLatency(stats.avg_latency_ms)}</span>
          </div>
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">Cost</span>
            <span className="font-medium">{formatCost(stats.cost_usd)}</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function RequestRow({ req }: { req: RecentRequest }) {
  const dotColor = MODEL_TYPE_COLORS[req.model_type] || "text-gray-500";
  const typeLabel = MODEL_TYPE_LABELS[req.model_type] || req.model_type;

  return (
    <tr className="border-b border-muted/50 last:border-0">
      <td className="py-2 pr-4">
        <div className="flex items-center gap-2">
          <span className={`inline-block w-2 h-2 rounded-full ${dotColor.replace("text-", "bg-")}`} />
          <span className="text-sm font-mono truncate max-w-[200px]" title={req.model_name}>
            {req.model_name}
          </span>
          <span className="text-xs text-muted-foreground shrink-0">[{typeLabel}]</span>
        </div>
      </td>
      <td className="py-2 text-right">
        <span className="text-sm font-medium text-orange-500">{formatNumber(req.tokens_in)}↑</span>
      </td>
      <td className="py-2 text-right">
        <span className="text-sm font-medium text-emerald-500">{formatNumber(req.tokens_out)}↓</span>
      </td>
      <td className="py-2 text-right text-xs text-muted-foreground whitespace-nowrap">{timeAgo(req.created_at)}</td>
    </tr>
  );
}

type AnalyticsDashboardProps = {
  title: string;
  subtitle: string;
  allowClear?: boolean;
};

export function AnalyticsDashboard({ title, subtitle, allowClear = false }: AnalyticsDashboardProps) {
  const { data: session } = useSession();
  const [data, setData] = useState<AnalyticsStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [days, setDays] = useState(30);
  const [clearing, setClearing] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  const fetchData = useCallback(async () => {
    if (!session) return;
    try {
      setLoading(true);
      setError(null);
      const result = await analyticsApi.getStats(days);
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không thể tải thống kê");
    } finally {
      setLoading(false);
    }
  }, [session, days]);

  const handleClear = async () => {
    try {
      setClearing(true);
      await analyticsApi.clearStats();
      setShowConfirm(false);
      await fetchData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không thể xóa thống kê");
    } finally {
      setClearing(false);
    }
  };

  useEffect(() => {
    if (session) {
      analyticsApi
        .getStats(days)
        .then(setData)
        .catch((err) => setError(err instanceof Error ? err.message : "Lỗi tải dữ liệu"))
        .finally(() => setLoading(false));
    }
  }, [session, days]);

  if (loading && !data) {
    return (
      <div className="p-6 space-y-6">
        <h1 className="text-2xl font-bold">{title}</h1>
        <div className="grid gap-4 md:grid-cols-3">
          {[...Array(3)].map((_, i) => (
            <Skeleton key={i} className="h-28" />
          ))}
        </div>
        <Skeleton className="h-72" />
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="p-6 space-y-4">
        <h1 className="text-2xl font-bold">{title}</h1>
        <Card>
          <CardContent className="pt-6">
            <p className="text-destructive">{error}</p>
            <Button onClick={fetchData} variant="outline" className="mt-4">
              Thử lại
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!data) return null;

  const llmTokens = data.by_model_type.llm.tokens_in + data.by_model_type.llm.tokens_out;

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">{title}</h1>
          <p className="text-sm text-muted-foreground">{subtitle}</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1 bg-muted rounded-md p-1">
            {DATE_RANGES.map((r) => (
              <Button key={r.value} variant={days === r.value ? "default" : "ghost"} size="sm" onClick={() => setDays(r.value)}>
                {r.label}
              </Button>
            ))}
          </div>
          {allowClear && (
            <Button variant="outline" size="sm" className="text-destructive hover:text-destructive" onClick={() => setShowConfirm(true)} disabled={clearing}>
              <Trash2 className="h-4 w-4 mr-2" />
              Xóa thống kê
            </Button>
          )}
          <Button variant="outline" size="sm" onClick={fetchData} disabled={loading}>
            <RefreshCw className={`h-4 w-4 mr-2 ${loading ? "animate-spin" : ""}`} />
            Làm mới
          </Button>
        </div>
      </div>

      {allowClear && showConfirm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <Card className="w-full max-w-md">
            <CardHeader>
              <CardTitle className="text-destructive flex items-center gap-2">
                <Trash2 className="h-5 w-5" />
                Xóa toàn bộ thống kê?
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground mb-4">
                Hành động này sẽ xóa vĩnh viễn tất cả dữ liệu thống kê token, chi phí và latency. Không thể hoàn tác.
              </p>
              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={() => setShowConfirm(false)} disabled={clearing}>
                  Hủy
                </Button>
                <Button variant="destructive" onClick={handleClear} disabled={clearing}>
                  {clearing ? "Đang xóa..." : "Xác nhận xóa"}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Thời gian phản hồi TB</CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{formatLatency(data.avg_latency_ms)}</div>
            <p className="text-xs text-muted-foreground mt-1">Từ lúc gửi câu hỏi đến khi AI trả lời xong</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Token LLM</CardTitle>
            <Hash className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{formatNumber(llmTokens)}</div>
            <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
              <span className="flex items-center gap-1">
                <ArrowRight className="h-3 w-3 text-blue-500" />
                In: {formatNumber(data.by_model_type.llm.tokens_in)}
              </span>
              <span className="flex items-center gap-1">
                <ArrowLeft className="h-3 w-3 text-emerald-500" />
                Out: {formatNumber(data.by_model_type.llm.tokens_out)}
              </span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Tin nhắn AI</CardTitle>
            <MessageSquare className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{data.total_messages.toLocaleString()}</div>
            <p className="text-xs text-muted-foreground mt-1">{data.total_sessions} phiên chat</p>
          </CardContent>
        </Card>
      </div>

      <div>
        <h2 className="text-lg font-semibold mb-3">Thống kê theo Model</h2>
        <div className="grid gap-4 md:grid-cols-3">
          <ModelTypeCard title="LLM Chính" icon={Brain} color="text-purple-500" stats={data.by_model_type.llm} />
          <ModelTypeCard title="Embedding" icon={Cpu} color="text-blue-500" stats={data.by_model_type.embedding} hideOut />
          <ModelTypeCard title="Reranking" icon={Network} color="text-amber-500" stats={data.by_model_type.reranker} hideOut />
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Recent Requests</CardTitle>
        </CardHeader>
        <CardContent>
          {data.recent_requests.length === 0 ? (
            <p className="text-sm text-muted-foreground">Chưa có dữ liệu request.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[560px]">
                <thead>
                  <tr className="border-b border-muted/70">
                    <th className="text-left py-2 pr-4 text-xs font-medium text-muted-foreground">Model</th>
                    <th className="text-right py-2 text-xs font-medium text-muted-foreground">In</th>
                    <th className="text-right py-2 text-xs font-medium text-muted-foreground">Out</th>
                    <th className="text-right py-2 text-xs font-medium text-muted-foreground">When</th>
                  </tr>
                </thead>
                <tbody>
                  {data.recent_requests.map((req, idx) => (
                    <RequestRow key={`${req.model_name}-${req.created_at}-${idx}`} req={req} />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

