"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Plus, Trash2, RefreshCw, MoreHorizontal, Copy, Globe } from "lucide-react";
import { toast } from "sonner";

import { TenantSelect } from "@/components/tenants/tenant-select";
import { Button, buttonVariants } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  DataTable,
  DataTableSortHeader,
  createColumnHelper,
  type DataTableFeatures,
} from "@/components/ui/data-table";
import { Field, FieldContent, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { authApi, tenantsApi } from "@/lib/api-client";
import { CreateUserRequestSchema } from "@/lib/schemas";
import type { CreateUserRequest, RoleItem, TenantItem, UserItem } from "@/types/api";

const EMPTY_FORM: CreateUserRequest = {
  username: "",
  password: "",
  role: "tenant_admin",
  tenant_id: null,
};

interface UserManagerProps {
  initialUsers?: UserItem[];
  initialRoles?: RoleItem[];
  initialTenants?: TenantItem[];
}

export function UserManager({
  initialUsers = [],
  initialRoles = [],
  initialTenants = [],
}: UserManagerProps) {
  const [users, setUsers] = useState<UserItem[]>(initialUsers);
  const [roles, setRoles] = useState<RoleItem[]>(initialRoles);
  const [tenants, setTenants] = useState<TenantItem[]>(initialTenants);
  const [form, setForm] = useState<CreateUserRequest>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(initialUsers.length === 0);
  const [createOpen, setCreateOpen] = useState(false);
  const [deletingUser, setDeletingUser] = useState<string | null>(null);

  const tenantNameMap = useMemo(() => new Map(tenants.map((t) => [t.id, t.name])), [tenants]);

  const load = useCallback(async (silent = false) => {
    try {
      if (!silent) setLoading(true);
      const [userRows, roleRows, tenantRows] = await Promise.all([
        authApi.getUsers(),
        authApi.getRoles(),
        tenantsApi.list(),
      ]);
      setUsers(userRows);
      setRoles(roleRows);
      setTenants(tenantRows);
    } catch (error) {
      if (!silent) {
        const message = error instanceof Error ? error.message : "Không thể tải dữ liệu";
        toast.error(message);
      }
    } finally {
      if (!silent) setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const handleCreate = useCallback(async () => {
    try {
      setSaving(true);

      if (form.role === "tenant_admin" && !form.tenant_id) {
        toast.error("Vui lòng chọn tenant cho tenant admin");
        return;
      }

      const payload: CreateUserRequest = {
        username: form.username.trim(),
        password: form.password,
        role: form.role,
        tenant_id: form.role === "tenant_admin" ? form.tenant_id : null,
      };

      const parsedPayload = CreateUserRequestSchema.safeParse(payload);
      if (!parsedPayload.success) {
        toast.error("Dữ liệu người dùng không hợp lệ");
        return;
      }

      const created = await authApi.createUser(parsedPayload.data);
      setUsers((current) => [...current, created]);
      setForm(EMPTY_FORM);
      setCreateOpen(false);
      toast.success("Đã tạo người dùng");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Không thể tạo người dùng";
      toast.error(message);
    } finally {
      setSaving(false);
    }
  }, [form]);

  const handleDelete = useCallback(async (username: string) => {
    try {
      await authApi.deleteUser(username);
      setUsers((current) => current.filter((u) => u.username !== username));
      setDeletingUser(null);
      toast.success("Đã xóa người dùng");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Không thể xóa người dùng";
      toast.error(message);
    }
  }, []);

  const columns = useMemo(() => {
    const columnHelper = createColumnHelper<DataTableFeatures, UserItem>();

    return columnHelper.columns([
      columnHelper.accessor("username", {
        meta: { title: "Tên đăng nhập" },
        header: ({ column }) => <DataTableSortHeader column={column} title="Tên đăng nhập" />,
        cell: ({ row }) => <span className="font-medium text-foreground">{row.original.username}</span>,
      }),
      columnHelper.accessor("role", {
        meta: { title: "Vai trò" },
        header: ({ column }) => <DataTableSortHeader column={column} title="Vai trò" />,
        cell: ({ row }) => {
          const role = row.original.role;
          return (
            <Tooltip>
              <TooltipTrigger>
                <Badge variant={role === "platform_admin" ? "default" : "secondary"} className="cursor-default text-xs">
                  {role === "platform_admin" ? "Platform" : "Tenant"}
                </Badge>
              </TooltipTrigger>
              <TooltipContent>
                {role === "platform_admin" ? "Platform Administrator (Toàn quyền hệ thống)" : "Tenant Administrator (Quản trị tenant)"}
              </TooltipContent>
            </Tooltip>
          );
        },
      }),
      columnHelper.accessor("tenant_id", {
        meta: { title: "Tenant trực thuộc" },
        header: ({ column }) => <DataTableSortHeader column={column} title="Tenant trực thuộc" />,
        cell: ({ row }) => {
          const tenantId = row.original.tenant_id;
          if (!tenantId) {
            return (
              <Tooltip>
                <TooltipTrigger>
                  <span className="inline-flex items-center gap-1 text-xs text-muted-foreground cursor-default">
                    <Globe className="h-3.5 w-3.5 text-muted-foreground/70" /> Toàn hệ thống
                  </span>
                </TooltipTrigger>
                <TooltipContent>Tài khoản quản trị cấp cao, truy cập toàn bộ hệ thống</TooltipContent>
              </Tooltip>
            );
          }
          return (
            <Badge variant="outline" className="text-xs font-normal">
              {tenantNameMap.get(tenantId) || "Không rõ"}
            </Badge>
          );
        },
      }),
      columnHelper.display({
        id: "actions",
        enableHiding: false,
        cell: ({ row }) => {
          const username = row.original.username;
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
                    <DropdownMenuLabel>Hành động</DropdownMenuLabel>
                    <DropdownMenuItem
                      onClick={() => {
                        void navigator.clipboard.writeText(username);
                        toast.success("Đã sao chép tên đăng nhập");
                      }}
                    >
                      <Copy className="mr-2 h-4 w-4" /> Sao chép username
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem
                      className="text-destructive focus:text-destructive"
                      onClick={() => setDeletingUser(username)}
                    >
                      <Trash2 className="mr-2 h-4 w-4" /> Xóa tài khoản
                    </DropdownMenuItem>
                  </DropdownMenuGroup>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          );
        },
      }),
    ]);
  }, [tenantNameMap]);

  return (
    <TooltipProvider>
      <div className="mx-auto flex max-w-7xl flex-col gap-6 p-6 md:p-8 animate-in fade-in-50 duration-300">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Quản lý người dùng</h1>
        <p className="text-sm text-muted-foreground mt-1">Tạo platform admin hoặc tenant admin mới.</p>
      </div>

      <DataTable
        columns={columns}
        data={users}
        searchKey="username"
        searchPlaceholder="Lọc theo tên đăng nhập..."
        enablePagination
        enableColumnVisibility
        emptyMessage={loading ? "Đang tải danh sách người dùng..." : "Chưa có người dùng nào."}
        toolbarExtra={
          <div className="flex items-center gap-2">
            <Button onClick={() => { setForm(EMPTY_FORM); setCreateOpen(true); }}>
              <Plus className="mr-2 h-4 w-4" /> Tạo người dùng
            </Button>
            <Button variant="outline" onClick={() => load(false)} disabled={loading}>
              <RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} /> Làm mới
            </Button>
          </div>
        }
      />

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="w-full sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Tạo người dùng mới</DialogTitle>
          </DialogHeader>
          <FieldGroup className="grid gap-4 py-4">
            <Field>
              <FieldContent>
                <FieldLabel htmlFor="username">Tên đăng nhập</FieldLabel>
                <Input id="username" value={form.username} onChange={(e) => setForm((c) => ({ ...c, username: e.target.value }))} placeholder="Ví dụ: alpha.admin" />
                <FieldDescription>Tên tài khoản dùng để đăng nhập vào trang quản trị (viết liền, không khoảng trắng).</FieldDescription>
              </FieldContent>
            </Field>
            <Field>
              <FieldContent>
                <FieldLabel htmlFor="password">Mật khẩu</FieldLabel>
                <Input id="password" type="password" value={form.password} onChange={(e) => setForm((c) => ({ ...c, password: e.target.value }))} placeholder="Tối thiểu 6 ký tự" />
                <FieldDescription>Mật khẩu quản trị viên (tối thiểu 6 ký tự).</FieldDescription>
              </FieldContent>
            </Field>
            <Field>
              <FieldContent>
                <FieldLabel>Vai trò</FieldLabel>
                <Select
                  value={form.role}
                  onValueChange={(val) =>
                    setForm((c) => ({
                      ...c,
                      role: val || "tenant_admin",
                      tenant_id: (val || "tenant_admin") === "tenant_admin" ? c.tenant_id : null,
                    }))
                  }
                >
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Chọn vai trò..." />
                  </SelectTrigger>
                  <SelectContent>
                    {roles.map((role) => (
                      <SelectItem key={role.id} value={role.name}>
                        {role.name === "platform_admin"
                          ? "Platform Admin"
                          : role.name === "tenant_admin"
                          ? "Tenant Admin"
                          : role.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <FieldDescription>Platform Admin quản trị toàn hệ thống; Tenant Admin quản trị phạm vi tenant.</FieldDescription>
              </FieldContent>
            </Field>
            <Field>
              <FieldContent>
                <FieldLabel>Tenant</FieldLabel>
                <TenantSelect
                  tenants={tenants}
                  value={form.tenant_id}
                  onValueChange={(tenantId) => setForm((c) => ({ ...c, tenant_id: tenantId }))}
                  disabled={form.role !== "tenant_admin"}
                />
                <FieldDescription>Tenant mà tài khoản trực thuộc.</FieldDescription>
              </FieldContent>
            </Field>
            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="outline" onClick={() => setCreateOpen(false)}>Hủy</Button>
              <Button onClick={handleCreate} disabled={saving}>
                <Plus className="mr-2 h-4 w-4" />
                {saving ? "Đang tạo..." : "Tạo người dùng"}
              </Button>
            </div>
          </FieldGroup>
        </DialogContent>
      </Dialog>

      {/* Delete User Confirmation Alert Dialog */}
      <AlertDialog open={!!deletingUser} onOpenChange={(open) => !open && setDeletingUser(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Xác nhận xóa người dùng</AlertDialogTitle>
            <AlertDialogDescription>
              Bạn có chắc chắn muốn xóa tài khoản <span className="font-semibold text-foreground">&quot;{deletingUser}&quot;</span> khỏi hệ thống? Thao tác này không thể hoàn tác.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Hủy</AlertDialogCancel>
            <AlertDialogAction
              className={buttonVariants({ variant: "destructive" })}
              onClick={async () => {
                if (deletingUser) {
                  await handleDelete(deletingUser);
                }
              }}
            >
              Xóa tài khoản
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      </div>
    </TooltipProvider>
  );
}
