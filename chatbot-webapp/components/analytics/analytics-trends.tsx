"use client";

import { RefreshCw } from "lucide-react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, XAxis, YAxis } from "recharts";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ChartContainer, ChartLegend, ChartLegendContent, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart";
import { Skeleton } from "@/components/ui/skeleton";
import { TooltipProvider } from "@/components/ui/tooltip";
import { formatCompactNumber } from "@/lib/format";
import type { AnalyticsStats } from "@/types/api";
import { DATE_RANGES, useAnalyticsStats } from "./use-analytics-stats";

export function AnalyticsTrends({ initialStats }: { initialStats?: AnalyticsStats | null }) {
  const { days, setDays, stats, loading, error, loadStats } = useAnalyticsStats(30, initialStats);

  const chartData = (stats?.daily ?? []).map((item) => ({
    ...item,
    formattedDate: item.date.split("-").slice(1).reverse().join("/"),
  }));

  return (
    <TooltipProvider>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Xu hướng Lưu lượng</h1>
            <p className="text-sm text-muted-foreground">
              Phân tích biến động tokens và lượt gọi API theo thời gian.
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
            <Skeleton className="h-80 w-full rounded-xl" />
            <Skeleton className="h-80 w-full rounded-xl" />
          </div>
        ) : stats ? (
          <div className="space-y-6">
            {/* Chart 1: Tokens in & out */}
            <Card className="shadow-sm border">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-semibold">Xu hướng Token</CardTitle>
                <CardDescription className="text-xs">Lượng token vào và token ra xử lý mỗi ngày.</CardDescription>
              </CardHeader>
              <CardContent className="h-72 pt-2">
                <ChartContainer
                  config={{
                    tokens_in: { label: "Token Vào", color: "var(--primary)" },
                    tokens_out: { label: "Token Ra", color: "hsl(142.1 76.2% 36.3%)" },
                  }}
                  className="h-full w-full"
                >
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                      <defs>
                        <linearGradient id="colorTokensIn" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="hsl(var(--primary))" stopOpacity={0.3} />
                          <stop offset="95%" stopColor="hsl(var(--primary))" stopOpacity={0.0} />
                        </linearGradient>
                        <linearGradient id="colorTokensOut" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="hsl(142.1 76.2% 36.3%)" stopOpacity={0.3} />
                          <stop offset="95%" stopColor="hsl(142.1 76.2% 36.3%)" stopOpacity={0.0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} opacity={0.3} />
                      <XAxis dataKey="formattedDate" tickLine={false} axisLine={false} tickMargin={8} fontSize={11} />
                      <YAxis tickLine={false} axisLine={false} tickMargin={8} fontSize={11} tickFormatter={(val) => formatCompactNumber(val)} />
                      <ChartTooltip content={<ChartTooltipContent indicator="line" />} />
                      <ChartLegend content={<ChartLegendContent />} />
                      <Area type="monotone" dataKey="tokens_in" name="Token Vào" stroke="hsl(var(--primary))" fillOpacity={1} fill="url(#colorTokensIn)" strokeWidth={2} />
                      <Area type="monotone" dataKey="tokens_out" name="Token Ra" stroke="hsl(142.1 76.2% 36.3%)" fillOpacity={1} fill="url(#colorTokensOut)" strokeWidth={2} />
                    </AreaChart>
                  </ResponsiveContainer>
                </ChartContainer>
              </CardContent>
            </Card>

            {/* Chart 2: Daily Requests / Messages */}
            <Card className="shadow-sm border">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-semibold">Xu hướng Lượt Gọi</CardTitle>
                <CardDescription className="text-xs">Số lượng request xử lý mỗi ngày.</CardDescription>
              </CardHeader>
              <CardContent className="h-64 pt-2">
                <ChartContainer
                  config={{
                    messages: { label: "Lượt gọi", color: "hsl(217.2 91.2% 59.8%)" },
                  }}
                  className="h-full w-full"
                >
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                      <defs>
                        <linearGradient id="colorCalls" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="hsl(217.2 91.2% 59.8%)" stopOpacity={0.3} />
                          <stop offset="95%" stopColor="hsl(217.2 91.2% 59.8%)" stopOpacity={0.0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} opacity={0.3} />
                      <XAxis dataKey="formattedDate" tickLine={false} axisLine={false} tickMargin={8} fontSize={11} />
                      <YAxis tickLine={false} axisLine={false} tickMargin={8} fontSize={11} tickFormatter={(val) => formatCompactNumber(val)} />
                      <ChartTooltip content={<ChartTooltipContent indicator="line" />} />
                      <Area type="monotone" dataKey="messages" name="Lượt gọi" stroke="hsl(217.2 91.2% 59.8%)" fillOpacity={1} fill="url(#colorCalls)" strokeWidth={2} />
                    </AreaChart>
                  </ResponsiveContainer>
                </ChartContainer>
              </CardContent>
            </Card>
          </div>
        ) : null}
      </div>
    </TooltipProvider>
  );
}
