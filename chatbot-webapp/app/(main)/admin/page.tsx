"use client";

import { useCallback, useEffect, useState } from "react";
import { Activity, Database, FileText, Server, Sparkles, RefreshCw, CheckCircle2, AlertTriangle } from "lucide-react";

import { healthApi } from "@/lib/api-client";
import { TenantUsageTable } from "@/components/analytics/tenant-usage-table";
import type { HealthData } from "@/types/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const LABELS: Record<string, string> = {
  database: "PostgreSQL Database",
  redis: "Redis Cache & Broker",
  storage: "RustFS Object Storage",
  ai_provider: "AI Gateway (9Router)",
  workers: "Celery Task Workers",
  qdrant: "Qdrant Vector DB",
};

const ICONS: Record<string, typeof Activity> = {
  database: Database,
  redis: Server,
  storage: FileText,
  ai_provider: Sparkles,
  workers: Server,
  qdrant: Database,
};

export default function AdminDashboardPage() {
  const [health, setHealth] = useState<HealthData | null>(null);
  const [loading, setLoading] = useState(false);
  const [isRealtime, setIsRealtime] = useState(true);

  const serviceEntries = Object.entries(health?.checks ?? health?.services ?? {});

  const load = useCallback(async (silent = false) => {
    try {
      if (!silent) setLoading(true);
      const result = await healthApi.getData();
      setHealth(result);
    } catch {
      if (!silent) setHealth(null);
    } finally {
      if (!silent) setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // Real-time silent background polling
  useEffect(() => {
    if (!isRealtime) return;

    const interval = setInterval(() => {
      if (document.visibilityState === "visible") {
        void load(true);
      }
    }, 10000);

    return () => clearInterval(interval);
  }, [isRealtime, load]);

  const isHealthy = health?.status === "healthy" || health?.status === "ok";

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-6 md:p-8 animate-in fade-in-50 duration-300">
      {/* Top Header */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between border-b pb-5">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight">Tổng quan Platform</h1>
            {isRealtime ? (
              <Badge variant="outline" className="gap-1.5 border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-medium text-xs py-0.5">
                <span className="pulse-dot-active" /> Real-time Live
              </Badge>
            ) : (
              <Badge variant="outline" className="text-xs text-muted-foreground">
                Tạm dừng live
              </Badge>
            )}
          </div>
          <p className="text-sm text-muted-foreground mt-1">
            Theo dõi sức khỏe hạ tầng, tài liệu sẵn sàng và mức tiêu thụ tài nguyên các Tenant.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={() => setIsRealtime(!isRealtime)}
            className={cn("gap-1.5 text-xs", isRealtime && "text-emerald-600 dark:text-emerald-400 border-emerald-500/30")}
          >
            <Activity className="size-3.5" />
            {isRealtime ? "Live Bật" : "Live Tắt"}
          </Button>
          <Button size="sm" variant="outline" onClick={() => load(false)} disabled={loading}>
            <RefreshCw className={cn("mr-1.5 h-3.5 w-3.5", loading && "animate-spin")} />
            Làm mới
          </Button>
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {/* System Health */}
        <Card className="shadow-xs border transition-all hover:shadow-sm">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
              Trạng thái Hạ tầng
            </CardTitle>
            {isHealthy ? (
              <CheckCircle2 className="h-4 w-4 text-emerald-500" />
            ) : (
              <AlertTriangle className="h-4 w-4 text-amber-500" />
            )}
          </CardHeader>
          <CardContent>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold font-mono capitalize">
                {health?.status || "Đang kiểm tra..."}
              </span>
            </div>
            <p className="text-xs text-muted-foreground mt-1">Tổng hợp từ health probes backend</p>
          </CardContent>
        </Card>

        {/* Ready Documents */}
        <Card className="shadow-xs border transition-all hover:shadow-sm">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
              Tài liệu Sẵn sàng
            </CardTitle>
            <FileText className="h-4 w-4 text-primary" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold font-mono">{health?.active_docs ?? 0}</div>
            <p className="text-xs text-muted-foreground mt-1">
              Trên tổng {health?.total_docs ?? 0} tài liệu toàn sàn
            </p>
          </CardContent>
        </Card>

        {/* Top 2 Critical Services */}
        {serviceEntries.slice(0, 2).map(([key, value]) => {
          const Icon = ICONS[key] || Activity;
          const statusText =
            typeof value.status === "string"
              ? value.status
              : typeof value.configured === "boolean"
                ? value.configured
                  ? "up"
                  : "down"
                : "unknown";
          const detailText =
            typeof value.latency_ms === "number"
              ? `${value.latency_ms} ms`
              : typeof value.provider === "string"
                ? value.provider
                : typeof value.broker === "string"
                  ? value.broker
                  : "Đang hoạt động";
          return (
            <Card key={key} className="shadow-xs border transition-all hover:shadow-sm">
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                  {LABELS[key] || key}
                </CardTitle>
                <Icon className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold font-mono uppercase text-emerald-600 dark:text-emerald-400">
                  {statusText}
                </div>
                <p className="text-xs text-muted-foreground mt-1">{detailText}</p>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Tenant Usage Table */}
      <TenantUsageTable />
    </div>
  );
}
