"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { RefreshCw } from "lucide-react";

import { analyticsApi } from "@/lib/api-client";
import { formatCompactNumber, formatLatency, formatNumber, formatVnd } from "@/lib/format";
import type { TenantUsageSummaryItem } from "@/types/api";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  DataTable,
  DataTableSortHeader,
  createColumnHelper,
  type DataTableFeatures,
} from "@/components/ui/data-table";

export function TenantUsageTable() {
  const [items, setItems] = useState<TenantUsageSummaryItem[]>([]);
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pricing, setPricing] = useState({ llmInput: 1308, llmOutput: 5233, embInput: 291 });

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
    } catch {
      // Ignore localStorage errors
    }
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

  const columns = useMemo(() => {
    const columnHelper = createColumnHelper<DataTableFeatures, TenantUsageSummaryItem>();

    return columnHelper.columns([
      columnHelper.accessor("tenant_name", {
        meta: { title: "Tenant" },
        header: ({ column }) => <DataTableSortHeader column={column} title="Tenant" />,
        cell: ({ row }) => (
          <div>
            <div className="font-semibold text-foreground text-xs">{row.original.tenant_name}</div>
            <div className="text-[11px] text-muted-foreground font-mono">{row.original.tenant_slug}</div>
          </div>
        ),
      }),
      columnHelper.accessor("question_count", {
        meta: { title: "Số Câu Hỏi" },
        header: ({ column }) => <DataTableSortHeader column={column} title="Số Câu Hỏi" />,
        cell: ({ row }) => (
          <Tooltip>
            <TooltipTrigger>
              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-primary/10 text-primary cursor-default font-mono">
                {formatNumber(row.original.question_count ?? 0)}
              </span>
            </TooltipTrigger>
            <TooltipContent>Số câu hỏi người dùng đã gửi chatbot</TooltipContent>
          </Tooltip>
        ),
      }),
      columnHelper.accessor("total_tokens", {
        meta: { title: "Tokens" },
        header: ({ column }) => <DataTableSortHeader column={column} title="Tokens" />,
        cell: ({ row }) => (
          <Tooltip>
            <TooltipTrigger>
              <span className="font-mono text-xs cursor-default">{formatCompactNumber(row.original.total_tokens)}</span>
            </TooltipTrigger>
            <TooltipContent>{formatNumber(row.original.total_tokens)} tokens</TooltipContent>
          </Tooltip>
        ),
      }),
      columnHelper.display({
        id: "cost_vnd",
        meta: { title: "Chi phí" },
        header: "Chi phí",
        cell: ({ row }) => {
          const item = row.original;
          const tenantCostVnd = Math.round(
            (item.tokens_in * pricing.llmInput) / 1000000 + (item.tokens_out * pricing.llmOutput) / 1000000
          );
          return <span className="font-bold text-primary font-mono text-xs">{formatVnd(tenantCostVnd)}</span>;
        },
      }),
      columnHelper.accessor("avg_latency_ms", {
        meta: { title: "Độ trễ" },
        header: ({ column }) => <DataTableSortHeader column={column} title="Độ trễ" />,
        cell: ({ row }) => <span className="font-mono text-xs">{formatLatency(row.original.avg_latency_ms)}</span>,
      }),
    ]);
  }, [pricing]);

  return (
    <TooltipProvider>
      <div className="space-y-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Thống kê theo Tenant</h1>
            <p className="text-sm text-muted-foreground mt-1">
              Chi tiết truy vấn LLM, dung lượng token và chi phí ước tính của từng tenant.
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
          <Button size="sm" variant="outline" onClick={() => load(false)} disabled={loading}>
            <RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            Làm mới
          </Button>
        </div>
      </div>

      {error ? (
        <div className="text-sm text-destructive">{error}</div>
      ) : loading && items.length === 0 ? (
        <div className="text-sm text-muted-foreground">Đang tải dữ liệu lưu lượng theo tổ chức...</div>
      ) : (
        <DataTable
          columns={columns}
          data={items}
          searchKey="tenant_name"
          searchPlaceholder="Lọc theo tên tổ chức..."
          enablePagination
          enableColumnVisibility
          emptyMessage="Chưa có dữ liệu truy vấn từ tổ chức nào trong khoảng thời gian này."
        />
      )}
      </div>
    </TooltipProvider>
  );
}
