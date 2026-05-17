"use client";

import { useEffect, useState, useCallback } from "react";
import { useSession } from "next-auth/react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { analyticsApi } from "@/lib/api-client";
import type { AnalyticsStats } from "@/types/api";
import { Clock, Hash, MessageSquare, RefreshCw, Zap, ArrowRight, ArrowLeft } from "lucide-react";

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
    if (session) void fetchData();
  }, [session, fetchData]);

  if (loading && !data) {
    return (
      <div className="p-6 space-y-6">
        <h1 className="text-2xl font-bold">Thống kê AI</h1>
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
        <h1 className="text-2xl font-bold">Thống kê AI</h1>
        <Card>
          <CardContent className="pt-6">
            <p className="text-destructive">{error}</p>
            <Button onClick={fetchData} variant="outline" className="mt-4">Thử lại</Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!data) return null;

  const maxDailyTokens = Math.max(...data.daily.map((d) => d.tokens_in + d.tokens_out), 1);

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Thống kê AI</h1>
          <p className="text-sm text-muted-foreground">Theo dõi hiệu năng và token tiêu thụ</p>
        </div>
        <Button variant="outline" size="sm" onClick={fetchData} disabled={loading}>
          <RefreshCw className={`h-4 w-4 mr-2 ${loading ? "animate-spin" : ""}`} />
          Làm mới
        </Button>
      </div>

      {/* KPI Cards */}
      <div className="grid gap-4 md:grid-cols-3">
        {/* Avg latency */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Thời gian phản hồi TB</CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{formatLatency(data.avg_latency_ms)}</div>
            <p className="text-xs text-muted-foreground mt-1">
              Từ lúc gửi câu hỏi đến khi AI trả lời xong
            </p>
          </CardContent>
        </Card>

        {/* Token burn */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Token đã đốt</CardTitle>
            <Hash className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{formatNumber(data.total_tokens)}</div>
            <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
              <span className="flex items-center gap-1">
                <ArrowRight className="h-3 w-3 text-blue-500" />
                In: {formatNumber(data.total_tokens_in)}
              </span>
              <span className="flex items-center gap-1">
                <ArrowLeft className="h-3 w-3 text-emerald-500" />
                Out: {formatNumber(data.total_tokens_out)}
              </span>
            </div>
          </CardContent>
        </Card>

        {/* Messages */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Tin nhắn AI</CardTitle>
            <MessageSquare className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{data.total_messages.toLocaleString()}</div>
            <p className="text-xs text-muted-foreground mt-1">
              {data.total_sessions} phiên chat
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Daily Token Chart */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Zap className="h-4 w-4" />
            Token theo ngày (30 ngày gần nhất)
          </CardTitle>
          <div className="flex items-center gap-4 text-xs text-muted-foreground">
            <span className="flex items-center gap-1.5">
              <span className="inline-block w-3 h-3 rounded-sm bg-blue-500/70" /> Token In (câu hỏi)
            </span>
            <span className="flex items-center gap-1.5">
              <span className="inline-block w-3 h-3 rounded-sm bg-emerald-500/70" /> Token Out (trả lời)
            </span>
          </div>
        </CardHeader>
        <CardContent>
          {data.daily.length === 0 ? (
            <p className="text-sm text-muted-foreground py-12 text-center">
              Chưa có dữ liệu. Hãy chat để bắt đầu thu thập thống kê.
            </p>
          ) : (
            <div className="space-y-2">
              {data.daily.map((day) => {
                const total = day.tokens_in + day.tokens_out;
                const pctIn = (day.tokens_in / maxDailyTokens) * 100;
                const pctOut = (day.tokens_out / maxDailyTokens) * 100;
                return (
                  <div key={day.date} className="flex items-center gap-3">
                    <span className="text-xs text-muted-foreground w-16 shrink-0">
                      {new Date(day.date).toLocaleDateString("vi-VN", {
                        day: "2-digit",
                        month: "2-digit",
                      })}
                    </span>
                    {/* Stacked bar: in + out */}
                    <div className="flex-1 h-5 bg-muted rounded-sm overflow-hidden flex">
                      <div
                        className="h-full bg-blue-500/70 transition-all"
                        style={{ width: `${Math.max(pctIn, 0.5)}%` }}
                        title={`In: ${formatNumber(day.tokens_in)}`}
                      />
                      <div
                        className="h-full bg-emerald-500/70 transition-all"
                        style={{ width: `${Math.max(pctOut, 0.5)}%` }}
                        title={`Out: ${formatNumber(day.tokens_out)}`}
                      />
                    </div>
                    <span className="text-xs font-medium w-14 text-right shrink-0">
                      {formatNumber(total)}
                    </span>
                    <span className="text-xs text-muted-foreground w-14 text-right shrink-0">
                      {formatLatency(day.avg_latency_ms ?? 0)}
                    </span>
                    <span className="text-xs text-muted-foreground w-12 text-right shrink-0">
                      {day.messages} msg
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
