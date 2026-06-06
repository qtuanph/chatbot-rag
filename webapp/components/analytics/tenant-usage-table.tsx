"use client";

import { useCallback, useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";

import { analyticsApi } from "@/lib/api-client";
import { formatLatency, formatNumber, formatVnd } from "@/lib/format";
import type { TenantUsageSummaryItem } from "@/types/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

export function TenantUsageTable() {
  const [items, setItems] = useState<TenantUsageSummaryItem[]>([]);
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const result = await analyticsApi.getTenantsUsage(days);
      setItems(result.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không thể tải usage theo tenant");
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void load();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  return (
    <Card className="rounded-3xl border-border/60 shadow-sm">
      <CardHeader>
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <CardTitle>Tenant đốt nhiều nhất</CardTitle>
            <CardDescription>So sánh usage theo tenant để ưu tiên kiểm tra quota và chi phí.</CardDescription>
          </div>
          <div className="flex items-center gap-2">
            {[7, 30, 90].map((value) => (
              <Button
                key={value}
                size="sm"
                className="rounded-2xl"
                variant={days === value ? "default" : "outline"}
                onClick={() => setDays(value)}
              >
                {value} ngày
              </Button>
            ))}
            <Button size="sm" variant="outline" className="rounded-2xl" onClick={load} disabled={loading}>
              <RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} />
              Làm mới
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {error ? (
          <div className="text-sm text-destructive">{error}</div>
        ) : loading ? (
          <div className="text-sm text-muted-foreground">Đang tải usage theo tenant...</div>
        ) : items.length === 0 ? (
          <div className="text-sm text-muted-foreground">Chưa có usage tenant nào trong khoảng này.</div>
        ) : (
          <Table className="min-w-[840px]">
            <TableHeader>
              <TableRow>
                <TableHead className="pr-4 text-xs text-muted-foreground">Tenant</TableHead>
                <TableHead className="pr-4 text-right text-xs text-muted-foreground">Request</TableHead>
                <TableHead className="pr-4 text-right text-xs text-muted-foreground">Token</TableHead>
                <TableHead className="pr-4 text-right text-xs text-muted-foreground">Chi phí</TableHead>
                <TableHead className="text-right text-xs text-muted-foreground">Latency TB</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((item) => (
                <TableRow key={item.tenant_id}>
                  <TableCell className="pr-4">
                    <div className="font-medium">{item.tenant_name}</div>
                    <div className="text-xs text-muted-foreground">{item.tenant_slug}</div>
                  </TableCell>
                  <TableCell className="pr-4 text-right">{formatNumber(item.call_count)}</TableCell>
                  <TableCell className="pr-4 text-right">{formatNumber(item.total_tokens)}</TableCell>
                  <TableCell className="pr-4 text-right font-medium">{formatVnd(item.cost_vnd_rounded)}</TableCell>
                  <TableCell className="text-right">{formatLatency(item.avg_latency_ms)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
