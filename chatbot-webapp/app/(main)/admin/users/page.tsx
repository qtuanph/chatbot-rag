"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Columns, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { TenantSelect } from "@/components/tenants/tenant-select";
import { Button, buttonVariants } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuCheckboxItem, DropdownMenuContent, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Field, FieldContent, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { authApi, tenantsApi } from "@/lib/api-client";
import type { CreateUserRequest, RoleItem, TenantItem, UserItem } from "@/types/api";

const EMPTY_FORM: CreateUserRequest = {
  username: "",
  password: "",
  role: "tenant_admin",
  tenant_id: null,
};

const TABLE_COLUMNS = ["Username", "Vai trò", "Tenant", "Thao tác"];

export default function AdminUsersPage() {
  const [users, setUsers] = useState<UserItem[]>([]);
  const [roles, setRoles] = useState<RoleItem[]>([]);
  const [tenants, setTenants] = useState<TenantItem[]>([]);
  const [form, setForm] = useState<CreateUserRequest>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [visibleColumns, setVisibleColumns] = useState<Record<string, boolean>>(
    TABLE_COLUMNS.reduce((acc, col) => ({ ...acc, [col]: true }), {})
  );

  const tenantNameMap = useMemo(() => new Map(tenants.map((t) => [t.id, t.name])), [tenants]);

  const load = useCallback(async () => {
    try {
      const [userRows, roleRows, tenantRows] = await Promise.all([
        authApi.getUsers(),
        authApi.getRoles(),
        tenantsApi.list(),
      ]);
      setUsers(userRows);
      setRoles(roleRows);
      setTenants(tenantRows);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Không thể tải dữ liệu";
      toast.error(message);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => { void load(); }, 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const handleCreate = useCallback(async () => {
    try {
      setSaving(true);
      const payload: CreateUserRequest = {
        username: form.username.trim(),
        password: form.password,
        role: form.role,
        tenant_id: form.role === "tenant_admin" ? form.tenant_id : null,
      };
      const created = await authApi.createUser(payload);
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
      toast.success("Đã xóa người dùng");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Không thể xóa người dùng";
      toast.error(message);
    }
  }, []);

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Quản lý người dùng</h1>
          <p className="text-sm text-muted-foreground">Tạo platform admin hoặc tenant admin mới.</p>
        </div>
        <div className="flex items-center gap-2">
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
          <Button onClick={() => { setForm(EMPTY_FORM); setCreateOpen(true); }}>
            <Plus className="mr-2 h-4 w-4" /> Tạo người dùng
          </Button>
        </div>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            {visibleColumns["Username"] && <TableHead className="text-xs text-muted-foreground">Username</TableHead>}
            {visibleColumns["Vai trò"] && <TableHead className="text-xs text-muted-foreground">Vai trò</TableHead>}
            {visibleColumns["Tenant"] && <TableHead className="text-xs text-muted-foreground">Tenant</TableHead>}
            {visibleColumns["Thao tác"] && <TableHead className="text-right text-xs text-muted-foreground">Thao tác</TableHead>}
          </TableRow>
        </TableHeader>
        <TableBody>
          {users.length === 0 ? (
            <TableRow>
              <TableCell colSpan={4} className="text-center text-sm text-muted-foreground py-8">
                Chưa có người dùng nào.
              </TableCell>
            </TableRow>
          ) : (
            users.map((user) => (
              <TableRow key={user.id}>
                {visibleColumns["Username"] && <TableCell className="font-medium">{user.username}</TableCell>}
                {visibleColumns["Vai trò"] && <TableCell>{user.role}</TableCell>}
                {visibleColumns["Tenant"] && (
                  <TableCell className="text-sm text-muted-foreground">
                    {user.tenant_id ? tenantNameMap.get(user.tenant_id) || "Không rõ" : "—"}
                  </TableCell>
                )}
                {visibleColumns["Thao tác"] && (
                  <TableCell className="text-right">
                    <Button size="sm" variant="destructive" onClick={() => handleDelete(user.username)}>
                      <Trash2 className="mr-1 h-3 w-3" /> Xóa
                    </Button>
                  </TableCell>
                )}
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>

      <Sheet open={createOpen} onOpenChange={setCreateOpen}>
        <SheetContent className="w-[90vw] sm:max-w-xl overflow-y-auto" side="right">
          <SheetHeader>
            <SheetTitle>Tạo người dùng mới</SheetTitle>
          </SheetHeader>
          <FieldGroup className="grid gap-4">
            <Field>
              <FieldContent>
                <FieldLabel htmlFor="username">Tên đăng nhập</FieldLabel>
                <Input id="username" value={form.username} onChange={(e) => setForm((c) => ({ ...c, username: e.target.value }))} />
              </FieldContent>
            </Field>
            <Field>
              <FieldContent>
                <FieldLabel htmlFor="password">Mật khẩu</FieldLabel>
                <Input id="password" type="password" value={form.password} onChange={(e) => setForm((c) => ({ ...c, password: e.target.value }))} />
              </FieldContent>
            </Field>
            <Field>
              <FieldContent>
                <FieldLabel>Vai trò</FieldLabel>
                <NativeSelect
                  value={form.role}
                  onChange={(e) =>
                    setForm((c) => ({
                      ...c,
                      role: e.target.value || "tenant_admin",
                      tenant_id: (e.target.value || "tenant_admin") === "tenant_admin" ? c.tenant_id : null,
                    }))
                  }
                >
                  {roles.map((role) => (
                    <NativeSelectOption key={role.id} value={role.name}>{role.name}</NativeSelectOption>
                  ))}
                </NativeSelect>
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
        </SheetContent>
      </Sheet>
    </div>
  );
}
