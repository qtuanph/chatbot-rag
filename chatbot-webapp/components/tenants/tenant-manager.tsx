"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Copy,
  Infinity as InfinityIcon,
  MoreHorizontal,
  Pencil,
  Plus,
  RefreshCw,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  DataTable,
  DataTableSortHeader,
  createColumnHelper,
  type DataTableFeatures,
} from "@/components/ui/data-table";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { tenantsApi } from "@/lib/api-client";
import { formatDateVN, formatDateTimeVN } from "@/lib/format";
import type { TenantItem } from "@/types/api";

import { TenantCreateDialog } from "./tenant-create-dialog";
import { TenantDetailDialog } from "./tenant-detail-dialog";

interface TenantManagerProps {
  initialTenants?: TenantItem[];
}

export function TenantManager({ initialTenants = [] }: TenantManagerProps) {
  const [tenants, setTenants] = useState<TenantItem[]>(initialTenants);
  const [selectedTenantId, setSelectedTenantId] = useState<string | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [loading, setLoading] = useState(initialTenants.length === 0);
  const [lastCreatedTenantAdmin, setLastCreatedTenantAdmin] = useState<{
    username: string;
    password: string;
  } | null>(null);

  const loadTenants = useCallback(async (silent = false) => {
    try {
      if (!silent) setLoading(true);
      const rows = await tenantsApi.list();
      setTenants(rows);
    } catch (error) {
      if (!silent) {
        const message = error instanceof Error ? error.message : "Không thể tải danh sách tenant";
        toast.error(message);
      }
    } finally {
      if (!silent) setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadTenants();
  }, [loadTenants]);

  const openTenant = useCallback((tenantId: string) => {
    setSelectedTenantId(tenantId);
    setDetailOpen(true);
  }, []);

  const handleCreateSuccess = (
    created: TenantItem,
    adminAcc?: { username: string; password: string }
  ) => {
    setTenants((current) => [created, ...current.filter((t) => t.id !== created.id)]);
    setLastCreatedTenantAdmin(adminAcc || null);
    openTenant(created.id);
  };

  const handleTenantUpdated = (updated: TenantItem) => {
    setTenants((current) => current.map((t) => (t.id === updated.id ? updated : t)));
  };

  const columns = useMemo(() => {
    const columnHelper = createColumnHelper<DataTableFeatures, TenantItem>();

    return columnHelper.columns([
      columnHelper.accessor("name", {
        header: ({ column }) => <DataTableSortHeader column={column} title="Tenant" />,
        cell: ({ row, getValue }) => {
          const name = getValue();
          const id = row.original.id;
          const desc = row.original.description;
          return (
            <div className="flex flex-col min-w-0 max-w-[180px]">
              <Tooltip>
                <TooltipTrigger className="truncate text-left block w-full">
                  <button
                    type="button"
                    className="font-medium text-foreground hover:underline cursor-pointer truncate block w-full text-left"
                    onClick={() => openTenant(id)}
                  >
                    {name}
                  </button>
                </TooltipTrigger>
                <TooltipContent className="text-xs max-w-xs flex flex-col gap-1 p-2 bg-neutral-900 text-white border border-neutral-800 shadow-xl">
                  <span className="font-semibold text-white">{name}</span>
                  {desc && (
                    <span className="text-zinc-300 text-[11px] leading-relaxed whitespace-pre-wrap">
                      {desc}
                    </span>
                  )}
                </TooltipContent>
              </Tooltip>
            </div>
          );
        },
      }),

      columnHelper.accessor("slug", {
        header: ({ column }) => <DataTableSortHeader column={column} title="Slug" />,
        cell: ({ getValue }) => {
          const slug = getValue();
          return (
            <Tooltip>
              <TooltipTrigger className="max-w-[110px] truncate block cursor-default">
                <span className="font-mono text-xs text-muted-foreground truncate block">
                  {slug}
                </span>
              </TooltipTrigger>
              <TooltipContent className="font-mono text-xs bg-neutral-900 text-zinc-200 border-neutral-800">
                {slug}
              </TooltipContent>
            </Tooltip>
          );
        },
      }),

      columnHelper.accessor("status", {
        header: ({ column }) => <DataTableSortHeader column={column} title="Trạng thái" />,
        cell: ({ getValue }) => {
          const status = getValue();
          const isActive = status === "active";
          return (
            <span
              className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium uppercase ${
                isActive
                  ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                  : "bg-muted text-muted-foreground"
              }`}
            >
              {status}
            </span>
          );
        },
      }),

      columnHelper.accessor("rate_limit_rpm", {
        header: ({ column }) => <DataTableSortHeader column={column} title="RPM" />,
        cell: ({ getValue }) => {
          const val = getValue() ?? 60;
          return (
            <Tooltip>
              <TooltipTrigger className="cursor-default">
                <span className="font-mono text-xs">{val}</span>
              </TooltipTrigger>
              <TooltipContent className="text-xs">Tối đa {val} requests mỗi phút</TooltipContent>
            </Tooltip>
          );
        },
      }),

      columnHelper.accessor("monthly_request_quota", {
        header: ({ column }) => <DataTableSortHeader column={column} title="Req/tháng" />,
        cell: ({ getValue }) => {
          const val = getValue();
          const isUnlimited = !val || val === 0;
          return (
            <Tooltip>
              <TooltipTrigger className="cursor-default">
                <span className="font-mono text-xs">
                  {isUnlimited ? (
                    <InfinityIcon className="size-3.5 text-muted-foreground inline" />
                  ) : (
                    val.toLocaleString("vi-VN")
                  )}
                </span>
              </TooltipTrigger>
              <TooltipContent className="text-xs">
                {isUnlimited ? "Không giới hạn request" : `${val.toLocaleString("vi-VN")} request/tháng`}
              </TooltipContent>
            </Tooltip>
          );
        },
      }),

      columnHelper.accessor("monthly_token_quota", {
        header: ({ column }) => <DataTableSortHeader column={column} title="Token/tháng" />,
        cell: ({ getValue }) => {
          const val = getValue();
          const isUnlimited = !val || val === 0;
          return (
            <Tooltip>
              <TooltipTrigger className="cursor-default">
                <span className="font-mono text-xs">
                  {isUnlimited ? (
                    <InfinityIcon className="size-3.5 text-muted-foreground inline" />
                  ) : (
                    val.toLocaleString("vi-VN")
                  )}
                </span>
              </TooltipTrigger>
              <TooltipContent className="text-xs">
                {isUnlimited ? "Không giới hạn token" : `${val.toLocaleString("vi-VN")} token/tháng`}
              </TooltipContent>
            </Tooltip>
          );
        },
      }),

      columnHelper.accessor("created_at", {
        header: ({ column }) => <DataTableSortHeader column={column} title="Ngày tạo" />,
        cell: ({ getValue }) => {
          const dateStr = getValue();
          return (
            <Tooltip>
              <TooltipTrigger className="cursor-default">
                <span className="text-xs text-muted-foreground whitespace-nowrap font-mono">
                  {formatDateVN(dateStr)}
                </span>
              </TooltipTrigger>
              <TooltipContent className="text-xs">
                Thời gian tạo: {formatDateTimeVN(dateStr)}
              </TooltipContent>
            </Tooltip>
          );
        },
      }),

      columnHelper.display({
        id: "actions",
        header: () => <div className="text-right">Thao tác</div>,
        cell: ({ row }) => {
          const tenant = row.original;
          return (
            <div className="flex justify-end">
              <DropdownMenu>
                <DropdownMenuTrigger
                  render={
                    <Button variant="ghost" className="h-8 w-8 p-0">
                      <span className="sr-only">Mở menu</span>
                      <MoreHorizontal className="h-4 w-4" />
                    </Button>
                  }
                />
                <DropdownMenuContent align="end">
                  <DropdownMenuGroup>
                    <DropdownMenuItem onClick={() => openTenant(tenant.id)}>
                      <Pencil className="mr-2 h-4 w-4" /> Chỉnh sửa & Cấu hình
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      onClick={() => {
                        void navigator.clipboard.writeText(tenant.id);
                        toast.success("Đã sao chép ID Tenant");
                      }}
                    >
                      <Copy className="mr-2 h-4 w-4" /> Sao chép ID Tenant
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      onClick={() => {
                        void navigator.clipboard.writeText(tenant.slug);
                        toast.success("Đã sao chép Slug");
                      }}
                    >
                      <Copy className="mr-2 h-4 w-4" /> Sao chép Slug
                    </DropdownMenuItem>
                  </DropdownMenuGroup>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          );
        },
      }),
    ]);
  }, [openTenant]);

  return (
    <TooltipProvider>
      <div className="flex flex-col gap-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Quản lý các công ty (Tenants)</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Mỗi công ty/tổ chức (Tenant) là một không gian độc lập. Quản trị viên tại đây có thể tạo tài khoản Tenant Admin và cấu hình API Key cho từng đối tác.
          </p>
        </div>

        <DataTable
          columns={columns}
          data={tenants}
          searchKey="name"
          searchPlaceholder="Lọc theo tên tenant..."
          enablePagination
          enableColumnVisibility
          emptyMessage={loading ? "Đang tải danh sách tenant..." : "Chưa có tenant nào. Hãy tạo tenant đầu tiên."}
          toolbarExtra={
            <div className="flex items-center gap-2">
              <Button
                className="rounded-xl"
                onClick={() => setCreateOpen(true)}
              >
                <Plus className="mr-2 h-4 w-4" /> Tạo tenant
              </Button>
              <Button className="rounded-xl" variant="outline" onClick={() => loadTenants(false)} disabled={loading}>
                <RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} /> Làm mới
              </Button>
            </div>
          }
        />

        {/* Modal Tạo Tenant mới (Stepper Wizard) */}
        <TenantCreateDialog
          open={createOpen}
          onOpenChange={setCreateOpen}
          onSuccess={handleCreateSuccess}
        />

        {/* Modal Cấu hình Tenant 2 cột (phong cách ChatGPT Settings) */}
        <TenantDetailDialog
          open={detailOpen}
          onOpenChange={setDetailOpen}
          tenantId={selectedTenantId}
          initialAdminAccount={lastCreatedTenantAdmin}
          onTenantUpdated={handleTenantUpdated}
        />
      </div>
    </TooltipProvider>
  );
}
