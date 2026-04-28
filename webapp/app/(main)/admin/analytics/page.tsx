"use client";

import { useEffect, useState, useCallback } from "react";
import { useSession } from "next-auth/react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { analyticsApi } from "@/lib/api-client";
import type { AnalyticsStats } from "@/types/api";
import {
  DollarSign,
  Clock,
  Hash,
  MessageSquare,
  RefreshCw,
  Cpu,
  Zap,
} from "lucide-react";

function formatNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toLocaleString();
}

function formatCost(usd: number): string {
  if (usd === 0) return "$0.00";
  if (usd < 0.01) return `$${usd.toFixed(4)}`;
  return `$${usd.toFixed(2)}`;
}

function formatLatency(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

export default function AnalyticsPage() {
  const { data: session } = useSession();
  const [data, setData] = useState<AnalyticsStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    if (!session) return;
    try {
      setLoading(true);
      setError(null);
      const result = await analyticsApi.getStats();
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không thể tải thống kê");
    } finally {
      setLoading(false);
    }
  }, [session]);

  useEffect(() => {
    if (session) {
      void fetchData();
    }
  }, [session, fetchData]);

  if (loading && !data) {
    return (
      <div className="p-6 space-y-6">
        <h1 className="text-2xl font-bold">Thống kê AI</h1>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {[...Array(4)].map((_, i) => (
            <Skeleton key={i} className="h-28" />
          ))}
        </div>
        <Skeleton className="h-64" />
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="p-6 space-y-4">
        <h1 className="text-2xl font-bold">Thống kê AI</h1>
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

  const maxDailyTokens = Math.max(...data.daily.map((d) => d.tokens_in + d.tokens_out), 1);

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Thống kê AI</h1>
          <p className="text-sm text-muted-foreground">
            Theo dõi token, chi phí và hiệu năng hệ thống
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={fetchData} disabled={loading}>
          <RefreshCw className={`h-4 w-4 mr-2 ${loading ? "animate-spin" : ""}`} />
          Làm mới
        </Button>
      </div>

      {/* Model Info */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-wrap items-center gap-3">
            <Cpu className="h-5 w-5 text-muted-foreground" />
            <span className="font-medium">{data.model_used}</span>
            <Badge variant={data.pricing.note ? "secondary" : "outline"}>
              {data.pricing.note || "Paid"}
            </Badge>
            <span className="text-sm text-muted-foreground ml-auto">
              Input: ${data.pricing.input_per_1m}/M | Output: ${data.pricing.output_per_1m}/M
            </span>
          </div>
        </CardContent>
      </Card>

      {/* KPI Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Chi phí ước tính</CardTitle>
            <DollarSign className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{formatCost(data.estimated_cost_usd)}</div>
            <p className="text-xs text-muted-foreground">
              {data.pricing.note || `Input $${data.pricing.input_per_1m}/M tokens`}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Độ trễ trung bình</CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{formatLatency(data.avg_latency_ms)}</div>
            <p className="text-xs text-muted-foreground">Thời gian phản hồi TB</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Tổng tokens</CardTitle>
            <Hash className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{formatNumber(data.total_tokens)}</div>
            <p className="text-xs text-muted-foreground">
              In: {formatNumber(data.total_tokens_in)} | Out: {formatNumber(data.total_tokens_out)}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Tin nhắn</CardTitle>
            <MessageSquare className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{data.total_messages.toLocaleString()}</div>
            <p className="text-xs text-muted-foreground">
              {data.total_sessions} phiên chat
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Daily Usage Chart */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Zap className="h-5 w-5" />
            Token theo ngày (30 ngày gần nhất)
          </CardTitle>
        </CardHeader>
        <CardContent>
          {data.daily.length === 0 ? (
            <p className="text-sm text-muted-foreground py-8 text-center">
              Chưa có dữ liệu. Hãy chat để bắt đầu thu thập thống kê.
            </p>
          ) : (
            <div className="space-y-2">
              {data.daily.map((day) => {
                const total = day.tokens_in + day.tokens_out;
                const pct = (total / maxDailyTokens) * 100;
                return (
                  <div key={day.date} className="flex items-center gap-3">
                    <span className="text-xs text-muted-foreground w-20 shrink-0">
                      {new Date(day.date).toLocaleDateString("vi-VN", {
                        day: "2-digit",
                        month: "2-digit",
                      })}
                    </span>
                    <div className="flex-1 h-6 bg-muted rounded-sm overflow-hidden">
                      <div
                        className="h-full bg-primary/70 rounded-sm transition-all"
                        style={{ width: `${Math.max(pct, 1)}%` }}
                      />
                    </div>
                    <span className="text-xs font-medium w-16 text-right shrink-0">
                      {formatNumber(total)}
                    </span>
                    <span className="text-xs text-muted-foreground w-16 text-right shrink-0">
                      {day.messages} msg
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Cost Comparison Table */}
      <Card>
        <CardHeader>
          <CardTitle>So sánh chi phí mô hình</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b">
                  <th className="text-left py-2 pr-4 font-medium">Mô hình</th>
                  <th className="text-right py-2 px-4 font-medium">Input $/M</th>
                  <th className="text-right py-2 px-4 font-medium">Output $/M</th>
                  <th className="text-right py-2 px-4 font-medium">Chi phí ước tính</th>
                  <th className="text-right py-2 pl-4 font-medium">Ghi chú</th>
                </tr>
              </thead>
              <tbody>
                {[
                  {
                    name: data.model_used,
                    input: data.pricing.input_per_1m,
                    output: data.pricing.output_per_1m,
                    note: data.pricing.note || "Paid",
                    current: true,
                  },
                  {
                    name: "Gemini 2.5 Flash",
                    input: 0.3,
                    output: 2.5,
                    note: "Cloud, 1M context",
                    current: false,
                  },
                  {
                    name: "Gemini 2.5 Pro",
                    input: 1.25,
                    output: 10.0,
                    note: "Cloud, chất lượng cao",
                    current: false,
                  },
                  {
                    name: "Local vLLM (GTX 1650)",
                    input: 0,
                    output: 0,
                    note: "~$10-15/tháng điện",
                    current: false,
                  },
                ].map((model) => {
                  const estimated =
                    model.input > 0 || model.output > 0
                      ? (data.total_tokens_in * model.input + data.total_tokens_out * model.output) / 1_000_000
                      : null;
                  return (
                    <tr key={model.name} className={`border-b ${model.current ? "bg-primary/5" : ""}`}>
                      <td className="py-2 pr-4 font-medium">
                        {model.name}
                        {model.current && (
                          <Badge variant="secondary" className="ml-2 text-xs">
                            Hiện tại
                          </Badge>
                        )}
                      </td>
                      <td className="text-right py-2 px-4">
                        ${model.input.toFixed(2)}
                      </td>
                      <td className="text-right py-2 px-4">
                        ${model.output.toFixed(2)}
                      </td>
                      <td className="text-right py-2 px-4">
                        {estimated !== null ? formatCost(estimated) : "~$10-15/tháng"}
                      </td>
                      <td className="text-right py-2 pl-4 text-muted-foreground">
                        {model.note}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
