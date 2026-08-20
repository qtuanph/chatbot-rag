"use client";

import { useCallback, useEffect, useState } from "react";
import { Columns, RefreshCw } from "lucide-react";

import { analyticsApi } from "@/lib/api-client";
import { formatLatency, formatNumber, formatVnd } from "@/lib/format";
import type { TenantUsageSummaryItem } from "@/types/api";
import { Button, buttonVariants } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuCheckboxItem, DropdownMenuContent, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

const TABLE_COLUMNS = [
  "Tổ chức (Tenant)",
  "Số truy vấn LLM",
  "Tổng số API Calls",
  "Token tiêu thụ",
  "Chi phí ước tính",
  "Độ trễ TB",
];

export function TenantUsageTable() {
  const [items, setItems] = useState<TenantUsageSummaryItem[]>([]);
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pricing, setPricing] = useState({ llmInput: 1308, llmOutput: 5233, embInput: 291 });
  const [visibleColumns, setVisibleColumns] = useState<Record<string, boolean>>(
    TABLE_COLUMNS.reduce((acc, col) => ({ ...acc, [col]: true }), {})
  );

  // Load custom pricing rates from localStorage
  const loadPricing = useCallback(() => {
    try {
      const saved = localStorage.getItem("chatbot_custom_model_pricing_v2");
      if (saved) {
        const parsed = JSON.parse(saved);
        setPricing({
          llmInput: typeof parsed.llmInput === "number" ? parsed.llmInput : 1308,
          llmOutput: typeof parsed.llmOutput === "number" ? parsed.llmOutput : 5233,
          embInput: typeof parsed.embInput === "number" ? parsed.embInput : 291,
        });
      }
    } catch (e) {}
  }, []);

  useEffect(() => {
    loadPricing();
    const handleStorageChange = () => loadPricing();
    window.addEventListener("storage", handleStorageChange);
    return () => window.removeEventListener("storage", handleStorageChange);
  }, [loadPricing]);

  const load = useCallback(async (silent = false) => {
    try {
      if (!silent) setLoading(true);
      setError(null);
      loadPricing();
      const result = await analyticsApi.getTenantsUsage(days);
      setItems(result.items);
    } catch (err) {
      if (!silent) {
        setError(err instanceof Error ? err.message : "Không thể tải dữ liệu thống kê theo tổ chức");
      }
    } finally {
      if (!silent) setLoading(false);
    }
  }, [days, loadPricing]);

  useEffect(() => {
    void load();
  }, [load]);

  // Real-time silent background polling
  useEffect(() => {
    const interval = setInterval(() => {
      if (document.visibilityState === "visible") {
        void load(true);
      }
    }, 10000);

    return () => clearInterval(interval);
  }, [load]);

  return (
    <div className="flex flex-col gap-4 mt-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="text-xl font-bold">Thống kê Tiêu thụ Tài nguyên theo Tổ chức (Tenant Usage Breakdown)</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Báo cáo chi tiết số lượng truy vấn LLM, dung lượng Token tiêu thụ và chi phí ước tính của từng Tổ chức.
          </p>
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
          <Button size="sm" variant="outline" onClick={() => load(false)} disabled={loading}>
            <RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            Làm mới
          </Button>
        </div>
      </div>
      <div>
        {error ? (
          <div className="text-sm text-destructive">{error}</div>
        ) : loading ? (
          <div className="text-sm text-muted-foreground">Đang tải dữ liệu lưu lượng theo tổ chức...</div>
        ) : items.length === 0 ? (
          <div className="text-sm text-muted-foreground">Chưa có dữ liệu truy vấn từ tổ chức nào trong khoảng thời gian này.</div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                {visibleColumns["Tổ chức (Tenant)"] && <TableHead className="pr-4 text-xs font-semibold text-muted-foreground">Tổ chức (Tenant)</TableHead>}
                {visibleColumns["Số truy vấn LLM"] && <TableHead className="pr-4 text-right text-xs font-semibold text-muted-foreground">Số truy vấn LLM</TableHead>}
                {visibleColumns["Tổng số API Calls"] && <TableHead className="pr-4 text-right text-xs font-semibold text-muted-foreground">Tổng số API Calls</TableHead>}
                {visibleColumns["Token tiêu thụ"] && <TableHead className="pr-4 text-right text-xs font-semibold text-muted-foreground">Token tiêu thụ</TableHead>}
                {visibleColumns["Chi phí ước tính"] && <TableHead className="pr-4 text-right text-xs font-semibold text-muted-foreground">Chi phí ước tính</TableHead>}
                {visibleColumns["Độ trễ TB"] && <TableHead className="text-right text-xs font-semibold text-muted-foreground">Độ trễ TB</TableHead>}
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((item) => {
                const tenantCostVnd = Math.round(
                  (item.tokens_in * pricing.llmInput) / 1000000 + (item.tokens_out * pricing.llmOutput) / 1000000
                );

                return (
                  <TableRow key={item.tenant_id}>
                    {visibleColumns["Tổ chức (Tenant)"] && (
                      <TableCell className="pr-4">
                        <div className="font-semibold text-foreground">{item.tenant_name}</div>
                        <div className="text-xs text-muted-foreground font-mono">{item.tenant_slug}</div>
                      </TableCell>
                    )}
                    {visibleColumns["Số truy vấn LLM"] && (
                      <TableCell className="pr-4 text-right">
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-primary/10 text-primary">
                          {formatNumber(item.question_count ?? item.call_count)} truy vấn
                        </span>
                      </TableCell>
                    )}
                    {visibleColumns["Tổng số API Calls"] && <TableCell className="pr-4 text-right font-medium">{formatNumber(item.call_count)}</TableCell>}
                    {visibleColumns["Token tiêu thụ"] && <TableCell className="pr-4 text-right font-mono">{formatNumber(item.total_tokens)}</TableCell>}
                    {visibleColumns["Chi phí ước tính"] && <TableCell className="pr-4 text-right font-bold text-primary font-mono">{formatVnd(tenantCostVnd)}</TableCell>}
                    {visibleColumns["Độ trễ TB"] && <TableCell className="text-right font-mono">{formatLatency(item.avg_latency_ms)}</TableCell>}
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
      </div>
    </div>
  );
}
