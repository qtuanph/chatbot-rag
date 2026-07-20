"use client";

import { useCallback, useEffect, useState } from "react";
import { Columns, RefreshCw } from "lucide-react";

import { analyticsApi } from "@/lib/api-client";
import { formatLatency, formatNumber, formatVnd } from "@/lib/format";
import type { TenantUsageSummaryItem } from "@/types/api";
import { Button, buttonVariants } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuCheckboxItem, DropdownMenuContent, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

const TABLE_COLUMNS = ["Tenant", "Request", "Token", "Chi phí", "Latency TB"];

export function TenantUsageTable() {
  const [items, setItems] = useState<TenantUsageSummaryItem[]>([]);
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [visibleColumns, setVisibleColumns] = useState<Record<string, boolean>>(
    TABLE_COLUMNS.reduce((acc, col) => ({ ...acc, [col]: true }), {})
  );

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
    <div className="flex flex-col gap-4 mt-8">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="text-xl font-bold">Tenant tiêu thụ nhiều nhất</h2>
          <p className="text-sm text-muted-foreground mt-1">So sánh mức sử dụng theo tenant để ưu tiên kiểm tra quota và chi phí.</p>
        </div>
        <div className="flex items-center gap-2">
          {[7, 30, 90].map((value) => (
            <Button
              key={value}
              size="sm"
              variant={days === value ? "default" : "outline"}
              onClick={() => setDays(value)}
            >
              {value} ngày
            </Button>
          ))}
          <DropdownMenu>
            <DropdownMenuTrigger className={buttonVariants({ variant: "outline", className: "h-9" })}>
              <Columns className="mr-2 h-4 w-4" /> Cột hiển thị
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              {TABLE_COLUMNS.map((col) => (
                <DropdownMenuCheckboxItem
                  key={col}
                  checked={visibleColumns[col]}
                  onCheckedChange={(val) => setVisibleColumns((prev) => ({ ...prev, [col]: val }))}
                >
                  {col}
                </DropdownMenuCheckboxItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
          <Button size="sm" variant="outline" onClick={load} disabled={loading}>
            <RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            Làm mới
          </Button>
        </div>
      </div>
      <div>
        {error ? (
          <div className="text-sm text-destructive">{error}</div>
        ) : loading ? (
          <div className="text-sm text-muted-foreground">Đang tải usage theo tenant...</div>
        ) : items.length === 0 ? (
          <div className="text-sm text-muted-foreground">Chưa có usage tenant nào trong khoảng này.</div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                {visibleColumns["Tenant"] && <TableHead className="pr-4 text-xs text-muted-foreground">Tenant</TableHead>}
                {visibleColumns["Request"] && <TableHead className="pr-4 text-right text-xs text-muted-foreground">Request</TableHead>}
                {visibleColumns["Token"] && <TableHead className="pr-4 text-right text-xs text-muted-foreground">Token</TableHead>}
                {visibleColumns["Chi phí"] && <TableHead className="pr-4 text-right text-xs text-muted-foreground">Chi phí</TableHead>}
                {visibleColumns["Latency TB"] && <TableHead className="text-right text-xs text-muted-foreground">Latency TB</TableHead>}
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((item) => (
                <TableRow key={item.tenant_id}>
                  {visibleColumns["Tenant"] && (
                    <TableCell className="pr-4">
                      <div className="font-medium">{item.tenant_name}</div>
                      <div className="text-xs text-muted-foreground">{item.tenant_slug}</div>
                    </TableCell>
                  )}
                  {visibleColumns["Request"] && <TableCell className="pr-4 text-right">{formatNumber(item.call_count)}</TableCell>}
                  {visibleColumns["Token"] && <TableCell className="pr-4 text-right">{formatNumber(item.total_tokens)}</TableCell>}
                  {visibleColumns["Chi phí"] && <TableCell className="pr-4 text-right font-medium">{formatVnd(item.cost_vnd_rounded)}</TableCell>}
                  {visibleColumns["Latency TB"] && <TableCell className="text-right">{formatLatency(item.avg_latency_ms)}</TableCell>}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>
    </div>
  );
}
