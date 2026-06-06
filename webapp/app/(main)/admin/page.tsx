"use client";

import { useCallback, useEffect, useState } from "react";
import { Activity, Database, FileText, Server } from "lucide-react";

import { healthApi } from "@/lib/api-client";
import { PageHeader } from "@/components/layout/page-header";
import { TenantUsageTable } from "@/components/analytics/tenant-usage-table";
import type { HealthData } from "@/types/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const LABELS: Record<string, string> = {
  database: "PostgreSQL",
  redis: "Redis",
  storage: "RustFS",
  ai_provider: "AI Provider",
  workers: "Workers",
  qdrant: "Qdrant",
};

const ICONS: Record<string, typeof Activity> = {
  database: Database,
  redis: Server,
  storage: FileText,
  ai_provider: Activity,
  workers: Server,
  qdrant: Database,
};

export default function AdminDashboardPage() {
  const [health, setHealth] = useState<HealthData | null>(null);
  const serviceEntries = Object.entries(health?.checks ?? health?.services ?? {});

  const load = useCallback(async () => {
    try {
      const result = await healthApi.getData();
      setHealth(result);
    } catch {
      setHealth(null);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void load();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-6">
      <PageHeader
        title="Tổng quan platform"
        description="Theo dõi sức khỏe hệ thống, tài liệu sẵn sàng và tenant usage nổi bật."
      />

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Card className="rounded-3xl border-border/60 shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Trạng thái hệ thống</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{health?.status || "unknown"}</div>
            <p className="text-xs text-muted-foreground">Tổng hợp từ health probes backend</p>
          </CardContent>
        </Card>
        <Card className="rounded-3xl border-border/60 shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Tài liệu sẵn sàng</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{health?.active_docs ?? 0}</div>
            <p className="text-xs text-muted-foreground">Trên tổng {health?.total_docs ?? 0} tài liệu</p>
          </CardContent>
        </Card>
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
                  : "Không có latency";
          return (
            <Card key={key} className="rounded-3xl border-border/60 shadow-sm">
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium">{LABELS[key] || key}</CardTitle>
                <Icon className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{statusText}</div>
                <p className="text-xs text-muted-foreground">{detailText}</p>
              </CardContent>
            </Card>
          );
        })}
      </div>

      <TenantUsageTable />
    </div>
  );
}
