"use client";

import { useCallback, useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import {
  Activity,
  Brain,
  Calculator,
  Cpu,
  DollarSign,
  MessageSquare,
  Network,
  RefreshCw,
  Sliders,
  ThumbsDown,
  TimerReset,
  Trash2,
  TrendingUp,
  Users,
  Zap,
} from "lucide-react";

import { analyticsApi } from "@/lib/api-client";
import { formatDateTimeVN, formatLatency, formatNumber, formatVnd } from "@/lib/format";
import type { AnalyticsStats, ModelTypeStats, RecentRequest } from "@/types/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, XAxis, YAxis } from "recharts";
import { ChartContainer, ChartLegend, ChartLegendContent, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart";
import { TenantUsageTable } from "@/components/analytics/tenant-usage-table";
import { cn } from "@/lib/utils";

type AnalyticsDashboardProps = {
  title: string;
  subtitle: string;
  allowClear?: boolean;
  initialStats?: AnalyticsStats | null;
};

const DATE_RANGES = [
  { label: "1 ngày", value: 1 },
  { label: "7 ngày", value: 7 },
  { label: "30 ngày", value: 30 },
  { label: "90 ngày", value: 90 },
];

export type ModelPricingConfig = {
  llmInput: number;
  llmOutput: number;
  embInput: number;
  rerankInput: number;
  preset: string;
};

const DEFAULT_PRICING: ModelPricingConfig = {
  llmInput: 1308,     // FPT Cloud LLM (gpt-oss-20b) Input: 1.308 VND / 1M tokens
  llmOutput: 5233,    // FPT Cloud LLM (gpt-oss-20b) Output: 5.233 VND / 1M tokens
  embInput: 291,      // FPT AI Factory (Vietnamese_Embedding) Input: 291 VND / 1M tokens
  rerankInput: 0,     // Reranker: 0 VND
  preset: "fpt",
};

// ── Pure Shadcn Model Breakdown Card ──
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
          {formatNumber(stats.call_count)} lượt
        </Badge>
      </CardHeader>

      <CardContent className="space-y-2.5 pt-2 text-sm">
        <div className="flex items-center justify-between">
          <span className="text-muted-foreground">Token Vào</span>
          <span className="font-mono font-medium">{formatNumber(stats.tokens_in)}</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-muted-foreground">Token Ra</span>
          <span className="font-mono font-medium">{formatNumber(stats.tokens_out)}</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-muted-foreground">Độ Trễ TB</span>
          <span className="font-mono font-medium">{formatLatency(stats.avg_latency_ms)}</span>
        </div>
        
        <div className="flex items-center justify-between text-xs pt-2 border-t text-muted-foreground">
          <span>Đơn giá áp dụng</span>
          <span className="font-mono font-medium text-foreground">
            {formatVnd(inputPrice)}/1M {typeof outputPrice === "number" && outputPrice > 0 ? `• ${formatVnd(outputPrice)}/1M` : ""}
          </span>
        </div>

        <div className="flex items-center justify-between pt-2 border-t font-semibold">
          <span>Chi phí tự tính</span>
          <span className="font-mono text-base text-primary">{formatVnd(calculatedCostVnd)}</span>
        </div>
      </CardContent>
    </Card>
  );
}

// ── Pure Shadcn Executive Dashboard Component ──
export function AnalyticsDashboard({ title, subtitle, allowClear = false, initialStats = null }: AnalyticsDashboardProps) {
  const { data: session } = useSession();
  const [stats, setStats] = useState<AnalyticsStats | null>(initialStats);
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(!initialStats);
  const [clearing, setClearing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Dynamic Custom Model Pricing State (Saved in LocalStorage)
  const [pricing, setPricing] = useState<ModelPricingConfig>(DEFAULT_PRICING);

  useEffect(() => {
    try {
      const saved = localStorage.getItem("chatbot_custom_model_pricing_v2");
      if (saved) {
        const parsed = JSON.parse(saved);
        setPricing({
          llmInput: typeof parsed.llmInput === "number" ? parsed.llmInput : DEFAULT_PRICING.llmInput,
          llmOutput: typeof parsed.llmOutput === "number" ? parsed.llmOutput : DEFAULT_PRICING.llmOutput,
          embInput: typeof parsed.embInput === "number" ? parsed.embInput : DEFAULT_PRICING.embInput,
          rerankInput: typeof parsed.rerankInput === "number" ? parsed.rerankInput : DEFAULT_PRICING.rerankInput,
          preset: parsed.preset || "custom",
        });
      }
    } catch (e) {
      console.warn("Could not load custom pricing:", e);
    }
  }, []);

  const updatePricing = (newP: Partial<ModelPricingConfig>) => {
    setPricing((prev) => {
      const updated = { ...prev, ...newP };
      try {
        localStorage.setItem("chatbot_custom_model_pricing_v2", JSON.stringify(updated));
      } catch (e) {}
      return updated;
    });
  };

  const loadStats = useCallback(async (silent = false) => {
    if (!session) return;
    try {
      if (!silent) setLoading(true);
      setError(null);
      const nextStats = await analyticsApi.getStats(days);
      setStats(nextStats);
    } catch (err) {
      if (!silent) {
        setError(err instanceof Error ? err.message : "Không thể tải thống kê");
      }
    } finally {
      if (!silent) setLoading(false);
    }
  }, [days, session]);

  // Initial load
  useEffect(() => {
    void loadStats();
  }, [loadStats]);

  // Real-time silent background polling (every 6 seconds, automatically when tab is active)
  useEffect(() => {
    const interval = setInterval(() => {
      if (document.visibilityState === "visible") {
        void loadStats(true);
      }
    }, 6000);

    return () => clearInterval(interval);
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

  // Dynamic live cost calculation across all models
  const llmCostVnd = stats ? Math.round((stats.by_model_type.llm.tokens_in * pricing.llmInput) / 1000000 + (stats.by_model_type.llm.tokens_out * pricing.llmOutput) / 1000000) : 0;
  const embCostVnd = stats ? Math.round((stats.by_model_type.embedding.tokens_in * pricing.embInput) / 1000000) : 0;
  const rerankCostVnd = stats ? Math.round((stats.by_model_type.reranker.tokens_in * pricing.rerankInput) / 1000000) : 0;
  const totalCalculatedCostVnd = llmCostVnd + embCostVnd + rerankCostVnd;

  if (loading && !stats) {
    return (
      <div className="space-y-6 p-6 md:p-8 animate-in fade-in-50 duration-300">
        <Skeleton className="h-10 w-1/3 rounded-lg" />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
          {Array.from({ length: 6 }).map((_, index) => (
            <Skeleton key={index} className="h-28 rounded-xl" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6 md:p-8 animate-in fade-in-50 duration-300">
      {/* ── Top Executive Header (Clean & Minimal) ── */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between border-b pb-5">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
          <p className="text-sm text-muted-foreground mt-1">{subtitle}</p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {DATE_RANGES.map((range) => (
            <Button
              key={range.value}
              size="sm"
              variant={days === range.value ? "default" : "outline"}
              onClick={() => setDays(range.value)}
            >
              {range.label}
            </Button>
          ))}
          <Button size="sm" variant="outline" onClick={() => loadStats(false)} disabled={loading}>
            <RefreshCw className={cn("mr-2 h-4 w-4", loading && "animate-spin")} />
            Làm mới
          </Button>
          {allowClear && (
            <Button size="sm" variant="destructive" onClick={handleClear} disabled={clearing}>
              <Trash2 className="mr-2 h-4 w-4" />
              {clearing ? "Đang xóa..." : "Xóa usage"}
            </Button>
          )}
        </div>
      </div>

      {error && (
        <Card className="border-destructive/50">
          <CardContent className="pt-6 text-sm text-destructive">{error}</CardContent>
        </Card>
      )}

      {stats && (
        <>
          {/* ── Executive Top KPI Metric Cards (6 Cards Grid) ── */}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
            {/* 1. Tổng Chi Phí Ước Tính */}
            <Card className="shadow-sm border">
              <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
                <CardTitle className="text-xs font-semibold text-muted-foreground">TỔNG CHI PHÍ UỚC TÍNH</CardTitle>
                <DollarSign className="h-4 w-4 text-primary" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold font-mono text-primary">{formatVnd(totalCalculatedCostVnd)}</div>
                <p className="text-xs text-muted-foreground mt-1">Tính theo đơn giá model</p>
              </CardContent>
            </Card>

            {/* 2. Số Truy Vấn LLM */}
            <Card className="shadow-sm border">
              <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
                <CardTitle className="text-xs font-semibold text-muted-foreground">TRUY VẤN LLM (PROMPTS)</CardTitle>
                <MessageSquare className="h-4 w-4 text-blue-500" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold font-mono">{formatNumber(stats.by_model_type.llm.call_count)}</div>
                <p className="text-xs text-muted-foreground mt-1">Lượt truy vấn khởi tạo LLM</p>
              </CardContent>
            </Card>

            {/* 3. Tổng Token Tiêu Thụ */}
            <Card className="shadow-sm border">
              <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
                <CardTitle className="text-xs font-semibold text-muted-foreground">TỔNG TOKEN TIÊU THỤ</CardTitle>
                <Activity className="h-4 w-4 text-emerald-500" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold font-mono">{formatNumber(stats.total_tokens)}</div>
                <p className="text-xs text-muted-foreground mt-1">In: {formatNumber(stats.total_tokens_in)} • Out: {formatNumber(stats.total_tokens_out)}</p>
              </CardContent>
            </Card>

            {/* 4. Tỷ Lệ Cache Tối Ưu */}
            <Card className="shadow-sm border">
              <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
                <CardTitle className="text-xs font-semibold text-muted-foreground">TỶ LỆ CACHE TỐI ƯU</CardTitle>
                <Zap className="h-4 w-4 text-amber-500" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold font-mono text-amber-600 dark:text-amber-400">
                  {stats.total_messages > 0 ? Math.max(0, Math.round(((stats.total_messages - stats.by_model_type.llm.call_count) / stats.total_messages) * 100)) : 0}%
                </div>
                <p className="text-xs text-muted-foreground mt-1">Truy vấn phản hồi qua Cache</p>
              </CardContent>
            </Card>

            {/* 5. Độ Trễ Trung Bình */}
            <Card className="shadow-sm border">
              <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
                <CardTitle className="text-xs font-semibold text-muted-foreground">ĐỘ TRỄ TRUNG BÌNH</CardTitle>
                <TimerReset className="h-4 w-4 text-orange-500" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold font-mono">{formatLatency(stats.avg_latency_ms)}</div>
                <p className="text-xs text-muted-foreground mt-1">Thời gian xử lý trung bình</p>
              </CardContent>
            </Card>

            {/* 6. Chỉ Số Hài Lòng */}
            <Card className="shadow-sm border">
              <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
                <CardTitle className="text-xs font-semibold text-muted-foreground">CHỈ SỐ HÀI LÒNG (CSAT)</CardTitle>
                <ThumbsDown className="h-4 w-4 text-rose-500" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold font-mono">
                  {100 - Math.round((stats.feedback_summary.dislike_rate || 0) * 100)}%
                </div>
                <p className="text-xs text-muted-foreground mt-1">
                  {formatNumber(stats.feedback_summary.like_count)} Hài lòng • {formatNumber(stats.feedback_summary.dislike_count)} Chưa hài lòng
                </p>
              </CardContent>
            </Card>
          </div>

          {/* ── Structured Tabbed Analytics View ── */}
          <Tabs defaultValue="overview" className="space-y-6 pt-2">
            <TabsList className="grid w-full grid-cols-2 md:w-auto md:inline-flex md:grid-cols-4">
              <TabsTrigger value="overview" className="gap-2">
                <Sliders className="h-4 w-4" />
                Cấu hình Đơn giá & Model
              </TabsTrigger>
              <TabsTrigger value="tenants" className="gap-2">
                <Users className="h-4 w-4" />
                Thống kê Theo Tenant
              </TabsTrigger>
              <TabsTrigger value="trends" className="gap-2">
                <TrendingUp className="h-4 w-4" />
                Biểu đồ Xu hướng
              </TabsTrigger>
              <TabsTrigger value="logs" className="gap-2">
                <Activity className="h-4 w-4" />
                Nhật ký & Đánh giá
              </TabsTrigger>
            </TabsList>

            {/* ── TAB 1: Tổng Quan & Cấu Hình Đơn Giá ── */}
            <TabsContent value="overview" className="space-y-6">
              {/* Form Cấu hình Đơn giá */}
              <Card className="shadow-sm border">
                <CardHeader>
                  <div className="flex items-center gap-2.5">
                    <Calculator className="h-5 w-5 text-primary" />
                    <div>
                      <CardTitle className="text-base font-semibold">Cấu hình Đơn giá Model AI (VND / 1 triệu Tokens)</CardTitle>
                      <CardDescription className="text-xs">
                        Nhập đơn giá tương ứng với nhà cung cấp. Tất cả thẻ KPI & bảng thống kê sẽ tự động cập nhật chi phí tương ứng.
                      </CardDescription>
                    </div>
                  </div>
                </CardHeader>

                <CardContent>
                  <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                    <div className="space-y-1.5 p-3 rounded-lg border bg-muted/20">
                      <label className="text-xs font-semibold text-foreground">💬 LLM Token Vào (Input)</label>
                      <div className="relative">
                        <Input
                          type="number"
                          min="0"
                          className="h-9 font-mono text-sm pr-14"
                          value={pricing.llmInput}
                          onChange={(e) => updatePricing({ llmInput: parseFloat(e.target.value) || 0 })}
                          placeholder="1308"
                        />
                        <span className="absolute right-3 top-2.5 text-xs text-muted-foreground font-medium pointer-events-none">
                          ₫/1M
                        </span>
                      </div>
                    </div>

                    <div className="space-y-1.5 p-3 rounded-lg border bg-muted/20">
                      <label className="text-xs font-semibold text-foreground">💬 LLM Token Ra (Output)</label>
                      <div className="relative">
                        <Input
                          type="number"
                          min="0"
                          className="h-9 font-mono text-sm pr-14"
                          value={pricing.llmOutput}
                          onChange={(e) => updatePricing({ llmOutput: parseFloat(e.target.value) || 0 })}
                          placeholder="5233"
                        />
                        <span className="absolute right-3 top-2.5 text-xs text-muted-foreground font-medium pointer-events-none">
                          ₫/1M
                        </span>
                      </div>
                    </div>

                    <div className="space-y-1.5 p-3 rounded-lg border bg-muted/20">
                      <label className="text-xs font-semibold text-foreground">🧠 Embedding (Véc-tơ)</label>
                      <div className="relative">
                        <Input
                          type="number"
                          min="0"
                          className="h-9 font-mono text-sm pr-14"
                          value={pricing.embInput}
                          onChange={(e) => updatePricing({ embInput: parseFloat(e.target.value) || 0 })}
                          placeholder="291"
                        />
                        <span className="absolute right-3 top-2.5 text-xs text-muted-foreground font-medium pointer-events-none">
                          ₫/1M
                        </span>
                      </div>
                    </div>

                    <div className="space-y-1.5 p-3 rounded-lg border bg-muted/20">
                      <label className="text-xs font-semibold text-foreground">⚡ Reranker (Sắp xếp)</label>
                      <div className="relative">
                        <Input
                          type="number"
                          min="0"
                          className="h-9 font-mono text-sm pr-14"
                          value={pricing.rerankInput}
                          onChange={(e) => updatePricing({ rerankInput: parseFloat(e.target.value) || 0 })}
                          placeholder="0"
                        />
                        <span className="absolute right-3 top-2.5 text-xs text-muted-foreground font-medium pointer-events-none">
                          ₫/1M
                        </span>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* 3 Thẻ Model Chi Tiết */}
              <div className="grid gap-6 md:grid-cols-3">
                <ModelBreakdownCard
                  title="LLM Chat Model"
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
                  title="Reranker Context"
                  stats={stats.by_model_type.reranker}
                  calculatedCostVnd={rerankCostVnd}
                  inputPrice={pricing.rerankInput}
                  icon={Network}
                />
              </div>
            </TabsContent>

            {/* ── TAB 2: Thống kê Theo Tenant ── */}
            <TabsContent value="tenants">
              <TenantUsageTable />
            </TabsContent>

            {/* ── TAB 3: Biểu đồ Xu hướng tiêu thụ ── */}
            <TabsContent value="trends">
              <Card className="shadow-sm border">
                <CardHeader>
                  <CardTitle className="text-base font-semibold">Xu hướng tiêu thụ Token AI</CardTitle>
                  <CardDescription>
                    Biểu đồ thống kê chi tiết lượng Token Input và Output đã được xử lý theo từng ngày.
                  </CardDescription>
                </CardHeader>
                <CardContent className="h-80">
                  <ChartContainer
                    config={{
                      tokens_in: { label: "Token Vào (Input)", color: "var(--primary)" },
                      tokens_out: { label: "Token Ra (Output)", color: "hsl(142.1 76.2% 36.3%)" },
                    }}
                    className="h-full w-full"
                  >
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart
                        data={stats.daily.map(item => ({
                          ...item,
                          formattedDate: item.date.split("-").slice(1).reverse().join("/"),
                        }))}
                        margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
                      >
                        <defs>
                          <linearGradient id="colorTokensIn" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="hsl(var(--primary))" stopOpacity={0.3}/>
                            <stop offset="95%" stopColor="hsl(var(--primary))" stopOpacity={0.0}/>
                          </linearGradient>
                          <linearGradient id="colorTokensOut" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="hsl(142.1 76.2% 36.3%)" stopOpacity={0.3}/>
                            <stop offset="95%" stopColor="hsl(142.1 76.2% 36.3%)" stopOpacity={0.0}/>
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" vertical={false} opacity={0.3} />
                        <XAxis dataKey="formattedDate" tickLine={false} axisLine={false} tickMargin={8} fontSize={12} />
                        <YAxis tickLine={false} axisLine={false} tickMargin={8} fontSize={12} tickFormatter={(val) => formatNumber(val)} />
                        <ChartTooltip content={<ChartTooltipContent indicator="line" />} />
                        <ChartLegend content={<ChartLegendContent />} />
                        <Area type="monotone" dataKey="tokens_in" name="Token Vào (Input)" stroke="hsl(var(--primary))" fillOpacity={1} fill="url(#colorTokensIn)" strokeWidth={2} />
                        <Area type="monotone" dataKey="tokens_out" name="Token Ra (Output)" stroke="hsl(142.1 76.2% 36.3%)" fillOpacity={1} fill="url(#colorTokensOut)" strokeWidth={2} />
                      </AreaChart>
                    </ResponsiveContainer>
                  </ChartContainer>
                </CardContent>
              </Card>
            </TabsContent>

            {/* ── TAB 4: Nhật ký Request & Phản Hồi ── */}
            <TabsContent value="logs" className="space-y-6">
              {/* Table 20 Request gần đây */}
              <Card className="shadow-sm border">
                <CardHeader>
                  <CardTitle className="text-base font-semibold">Nhật ký Request gần đây (20 lượt cuối)</CardTitle>
                  <CardDescription>Chi tiết số lượng token, độ trễ và chi phí tự tính cho mỗi lượt truy vấn.</CardDescription>
                </CardHeader>
                <CardContent className="p-0">
                  <ScrollArea className="h-[360px] w-full">
                    <Table>
                      <TableHeader className="sticky top-0 bg-background z-10 border-b">
                        <TableRow>
                          <TableHead className="pl-4">Model</TableHead>
                          <TableHead className="text-right">Token Vào</TableHead>
                          <TableHead className="text-right">Token Ra</TableHead>
                          <TableHead className="text-right">Độ Trễ</TableHead>
                          <TableHead className="text-right">Chi Phí Tự Tính</TableHead>
                          <TableHead className="text-right pr-4">Thời Gian</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {stats.recent_requests.map((row: RecentRequest, index: number) => {
                          const rate = row.model_type === "embedding" ? pricing.embInput : row.model_type === "reranker" ? pricing.rerankInput : pricing.llmInput;
                          const outRate = row.model_type === "llm" ? pricing.llmOutput : 0;
                          const reqCostVnd = Math.round((row.tokens_in * rate) / 1000000 + (row.tokens_out * outRate) / 1000000);

                          return (
                            <TableRow key={index}>
                              <TableCell className="pl-4 font-mono font-medium text-xs flex items-center gap-2">
                                <span className={cn(
                                  "w-2 h-2 rounded-full",
                                  row.model_type === "llm" ? "bg-blue-500" : row.model_type === "embedding" ? "bg-emerald-500" : "bg-purple-500"
                                )} />
                                {row.model_name || "System Request"}
                              </TableCell>
                              <TableCell className="text-right font-mono text-xs">{formatNumber(row.tokens_in)}</TableCell>
                              <TableCell className="text-right font-mono text-xs">{formatNumber(row.tokens_out)}</TableCell>
                              <TableCell className="text-right font-mono text-xs">{formatLatency(row.latency_ms)}</TableCell>
                              <TableCell className="text-right font-mono text-xs font-semibold text-primary">
                                {formatVnd(reqCostVnd)}
                              </TableCell>
                              <TableCell className="text-right text-xs text-muted-foreground pr-4">{formatDateTimeVN(row.created_at)}</TableCell>
                            </TableRow>
                          );
                        })}
                      </TableBody>
                    </Table>
                  </ScrollArea>
                </CardContent>
              </Card>

              {/* Quality & Feedback Audit */}
              <Card className="shadow-sm border">
                <CardHeader>
                  <CardTitle className="text-base font-semibold">Đánh giá chất lượng Phản hồi</CardTitle>
                  <CardDescription>
                    Theo dõi các tài liệu hoặc section bị dislike nhiều để kịp thời cập nhật dữ liệu.
                  </CardDescription>
                </CardHeader>
                <CardContent className="grid gap-6 md:grid-cols-2">
                  <div className="space-y-3">
                    <h3 className="text-sm font-semibold">Tài liệu bị Dislike nhiều nhất</h3>
                    {stats.feedback_summary.top_disliked_documents.length === 0 ? (
                      <p className="text-xs text-muted-foreground">Không có tài liệu nào bị dislike.</p>
                    ) : (
                      <div className="space-y-2">
                        {stats.feedback_summary.top_disliked_documents.map((item) => (
                          <div key={item.document_id} className="flex items-center justify-between rounded-lg border p-2.5 text-xs">
                            <span className="font-medium truncate pr-2">{item.title}</span>
                            <Badge variant="destructive">{formatNumber(item.count)} dislike</Badge>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  <div className="space-y-3">
                    <h3 className="text-sm font-semibold">Section bị Dislike nhiều nhất</h3>
                    {stats.feedback_summary.top_disliked_sections.length === 0 ? (
                      <p className="text-xs text-muted-foreground">Không có section nào bị dislike.</p>
                    ) : (
                      <div className="space-y-2">
                        {stats.feedback_summary.top_disliked_sections.map((item) => (
                          <div key={`${item.document_id}-${item.section_id}`} className="flex items-center justify-between rounded-lg border p-2.5 text-xs">
                            <span className="font-medium truncate pr-2">{item.heading}</span>
                            <Badge variant="destructive">{formatNumber(item.count)} dislike</Badge>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </>
      )}
    </div>
  );
}
