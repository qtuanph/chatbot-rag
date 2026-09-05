"use client";

import { ArrowDownLeft, ArrowUpRight, Brain, Calculator, Cpu, DollarSign, ListFilter, Network, RefreshCw, TimerReset } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { formatCompactNumber, formatLatency, formatNumber, formatVnd } from "@/lib/format";
import type { AnalyticsStats, ModelTypeStats } from "@/types/api";
import { DATE_RANGES, useAnalyticsStats } from "./use-analytics-stats";

function ModelBreakdownCard({
  title,
  stats,
  calculatedCostVnd,
  inputPrice,
  outputPrice,
  icon: Icon,
}: {
  title: string;
  stats: ModelTypeStats;
  calculatedCostVnd: number;
  inputPrice: number;
  outputPrice?: number;
  icon: typeof Brain;
}) {
  return (
    <Card className="shadow-sm border">
      <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
        <CardTitle className="text-sm font-semibold flex items-center gap-2">
          <Icon className="h-4 w-4 text-muted-foreground" />
          {title}
        </CardTitle>
        <Badge variant="secondary" className="font-mono text-xs">
          {formatNumber(stats.call_count)} calls
        </Badge>
      </CardHeader>

      <CardContent className="space-y-2.5 pt-2 text-sm">
        <div className="flex items-center justify-between">
          <span className="text-muted-foreground text-xs">Token Vào</span>
          <span className="font-mono font-medium text-xs">{formatCompactNumber(stats.tokens_in)}</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-muted-foreground text-xs">Token Ra</span>
          <span className="font-mono font-medium text-xs">{formatCompactNumber(stats.tokens_out)}</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-muted-foreground text-xs">Độ trễ TB</span>
          <span className="font-mono font-medium text-xs">{formatLatency(stats.avg_latency_ms)}</span>
        </div>

        <div className="flex items-center justify-between text-xs pt-2 border-t text-muted-foreground">
          <span>Đơn giá</span>
          <span className="font-mono font-medium text-foreground">
            {formatVnd(inputPrice)}/1M {typeof outputPrice === "number" && outputPrice > 0 ? `• ${formatVnd(outputPrice)}/1M` : ""}
          </span>
        </div>

        <div className="flex items-center justify-between pt-2 border-t font-semibold">
          <span className="text-xs">Chi phí tính</span>
          <span className="font-mono text-sm text-primary">{formatVnd(calculatedCostVnd)}</span>
        </div>
      </CardContent>
    </Card>
  );
}

export function AnalyticsOverview({ initialStats }: { initialStats?: AnalyticsStats | null }) {
  const {
    days,
    setDays,
    stats,
    loading,
    error,
    pricing,
    updatePricing,
    loadStats,
    llmCostVnd,
    embCostVnd,
    rerankCostVnd,
    totalCalculatedCostVnd,
  } = useAnalyticsStats(30, initialStats);

  return (
    <TooltipProvider>
      <div className="space-y-6">
        {/* Header toolbar */}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Tổng quan Thống kê</h1>
            <p className="text-sm text-muted-foreground">
              Lưu lượng, chi phí ước tính và phân bổ model trong hệ thống.
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
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Skeleton className="h-28 rounded-xl" />
            <Skeleton className="h-28 rounded-xl" />
            <Skeleton className="h-28 rounded-xl" />
            <Skeleton className="h-28 rounded-xl" />
          </div>
        ) : stats ? (
          <>
            {/* 4 Top KPI Cards */}
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <Card className="shadow-sm border">
                <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
                  <CardTitle className="text-xs font-medium text-muted-foreground">Lượt Hỏi Chatbot</CardTitle>
                  <Brain className="h-4 w-4 text-blue-500" />
                </CardHeader>
                <CardContent>
                  <Tooltip>
                    <TooltipTrigger>
                      <div className="text-2xl font-bold font-mono tracking-tight cursor-default">
                        {formatNumber(stats.by_model_type?.llm?.call_count ?? stats.total_messages)}
                      </div>
                    </TooltipTrigger>
                    <TooltipContent>Tổng số câu hỏi người dùng đã gửi trong {days} ngày</TooltipContent>
                  </Tooltip>
                  <p className="text-[11px] text-muted-foreground mt-1">Mỗi câu hỏi người dùng tính 1 lượt</p>
                </CardContent>
              </Card>

              <Card className="shadow-sm border">
                <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
                  <CardTitle className="text-xs font-medium text-muted-foreground">Tokens Tiêu Thụ</CardTitle>
                  <Cpu className="h-4 w-4 text-emerald-500" />
                </CardHeader>
                <CardContent>
                  <Tooltip>
                    <TooltipTrigger>
                      <div className="text-2xl font-bold font-mono tracking-tight text-emerald-600 dark:text-emerald-400 cursor-default">
                        {formatCompactNumber(stats.total_tokens)}
                      </div>
                    </TooltipTrigger>
                    <TooltipContent>{formatNumber(stats.total_tokens)} tokens</TooltipContent>
                  </Tooltip>
                  <div className="flex items-center gap-2 text-[11px] text-muted-foreground mt-1">
                    <span>Vào {formatCompactNumber(stats.total_tokens_in)}</span>
                    <span>•</span>
                    <span>Ra {formatCompactNumber(stats.total_tokens_out)}</span>
                  </div>
                </CardContent>
              </Card>

              <Card className="shadow-sm border">
                <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
                  <CardTitle className="text-xs font-medium text-muted-foreground">Chi Phí Ước Tính</CardTitle>
                  <DollarSign className="h-4 w-4 text-amber-500" />
                </CardHeader>
                <CardContent>
                  <Tooltip>
                    <TooltipTrigger>
                      <div className="text-2xl font-bold font-mono tracking-tight text-primary cursor-default">
                        {formatVnd(totalCalculatedCostVnd)}
                      </div>
                    </TooltipTrigger>
                    <TooltipContent>Chi phí quy đổi theo đơn giá cấu hình</TooltipContent>
                  </Tooltip>
                  <p className="text-[11px] text-muted-foreground mt-1">Quy đổi theo đơn giá cấu hình</p>
                </CardContent>
              </Card>

              <Card className="shadow-sm border">
                <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
                  <CardTitle className="text-xs font-medium text-muted-foreground">Thời Gian Phản Hồi</CardTitle>
                  <TimerReset className="h-4 w-4 text-purple-500" />
                </CardHeader>
                <CardContent>
                  <Tooltip>
                    <TooltipTrigger>
                      <div className="text-2xl font-bold font-mono tracking-tight cursor-default">
                        {formatLatency(stats.avg_latency_ms)}
                      </div>
                    </TooltipTrigger>
                    <TooltipContent>Độ trễ trung bình toàn pipeline RAG</TooltipContent>
                  </Tooltip>
                  <p className="text-[11px] text-muted-foreground mt-1">Độ trễ trung bình toàn pipeline</p>
                </CardContent>
              </Card>
            </div>

            {/* Cấu hình Đơn giá */}
            <Card className="shadow-sm border">
              <CardHeader className="pb-3">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                  <div className="flex items-center gap-2">
                    <Calculator className="h-4 w-4 text-primary" />
                    <CardTitle className="text-sm font-semibold">Cấu hình Đơn giá Model</CardTitle>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-7 text-xs"
                      onClick={() => updatePricing({ llmInput: 1308, llmOutput: 5233, embInput: 291, rerankInput: 0, preset: "fpt" })}
                    >
                      FPT Cloud
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-7 text-xs"
                      onClick={() => updatePricing({ llmInput: 12500, llmOutput: 50000, embInput: 500, rerankInput: 0, preset: "openai" })}
                    >
                      OpenAI
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-7 text-xs"
                      onClick={() => updatePricing({ llmInput: 3500, llmOutput: 7000, embInput: 0, rerankInput: 0, preset: "deepseek" })}
                    >
                      DeepSeek
                    </Button>
                  </div>
                </div>
                <CardDescription className="text-xs">Đơn giá VND trên 1 triệu tokens để tính chi phí tự động.</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  <div className="space-y-1 p-2.5 rounded-lg border bg-muted/20">
                    <label className="text-xs font-medium text-foreground flex items-center gap-1.5">
                      <ArrowDownLeft className="size-3.5 text-blue-500" />
                      LLM Token Vào
                    </label>
                    <div className="relative">
                      <Input
                        type="number"
                        min="0"
                        className="h-8 font-mono text-xs pr-12"
                        value={pricing.llmInput}
                        onChange={(e) => updatePricing({ llmInput: parseFloat(e.target.value) || 0 })}
                        placeholder="1308"
                      />
                      <span className="absolute right-2 top-2 text-[11px] text-muted-foreground font-mono pointer-events-none">₫/1M</span>
                    </div>
                  </div>

                  <div className="space-y-1 p-2.5 rounded-lg border bg-muted/20">
                    <label className="text-xs font-medium text-foreground flex items-center gap-1.5">
                      <ArrowUpRight className="size-3.5 text-emerald-500" />
                      LLM Token Ra
                    </label>
                    <div className="relative">
                      <Input
                        type="number"
                        min="0"
                        className="h-8 font-mono text-xs pr-12"
                        value={pricing.llmOutput}
                        onChange={(e) => updatePricing({ llmOutput: parseFloat(e.target.value) || 0 })}
                        placeholder="5233"
                      />
                      <span className="absolute right-2 top-2 text-[11px] text-muted-foreground font-mono pointer-events-none">₫/1M</span>
                    </div>
                  </div>

                  <div className="space-y-1 p-2.5 rounded-lg border bg-muted/20">
                    <label className="text-xs font-medium text-foreground flex items-center gap-1.5">
                      <Network className="size-3.5 text-purple-500" />
                      Embedding Token
                    </label>
                    <div className="relative">
                      <Input
                        type="number"
                        min="0"
                        className="h-8 font-mono text-xs pr-12"
                        value={pricing.embInput}
                        onChange={(e) => updatePricing({ embInput: parseFloat(e.target.value) || 0 })}
                        placeholder="291"
                      />
                      <span className="absolute right-2 top-2 text-[11px] text-muted-foreground font-mono pointer-events-none">₫/1M</span>
                    </div>
                  </div>

                  <div className="space-y-1 p-2.5 rounded-lg border bg-muted/20">
                    <label className="text-xs font-medium text-foreground flex items-center gap-1.5">
                      <ListFilter className="size-3.5 text-amber-500" />
                      Reranker Lượt gọi
                    </label>
                    <div className="relative">
                      <Input
                        type="number"
                        min="0"
                        className="h-8 font-mono text-xs pr-12"
                        value={pricing.rerankInput}
                        onChange={(e) => updatePricing({ rerankInput: parseFloat(e.target.value) || 0 })}
                        placeholder="0"
                      />
                      <span className="absolute right-2 top-2 text-[11px] text-muted-foreground font-mono pointer-events-none">₫/1M</span>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* 3 Model Breakdown Cards */}
            <div className="grid gap-4 md:grid-cols-3">
              <ModelBreakdownCard
                title="LLM Chat"
                stats={stats.by_model_type.llm}
                calculatedCostVnd={llmCostVnd}
                inputPrice={pricing.llmInput}
                outputPrice={pricing.llmOutput}
                icon={Brain}
              />
              <ModelBreakdownCard
                title="Embedding Vector"
                stats={stats.by_model_type.embedding}
                calculatedCostVnd={embCostVnd}
                inputPrice={pricing.embInput}
                icon={Cpu}
              />
              <ModelBreakdownCard
                title="Reranker"
                stats={stats.by_model_type.reranker}
                calculatedCostVnd={rerankCostVnd}
                inputPrice={pricing.rerankInput}
                icon={Network}
              />
            </div>
          </>
        ) : null}
      </div>
    </TooltipProvider>
  );
}
