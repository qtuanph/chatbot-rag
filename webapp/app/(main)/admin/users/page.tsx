"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { authApi, tenantsApi } from "@/lib/api-client";
import type { CreateUserRequest, RoleItem, TenantItem, UserItem } from "@/types/api";
import { PageHeader } from "@/components/layout/page-header";
import { TenantSelect } from "@/components/tenants/tenant-select";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

const EMPTY_FORM: CreateUserRequest = {
  username: "",
  password: "",
  role: "tenant_admin",
  tenant_id: null,
};

export default function AdminUsersPage() {
  const [users, setUsers] = useState<UserItem[]>([]);
  const [roles, setRoles] = useState<RoleItem[]>([]);
  const [tenants, setTenants] = useState<TenantItem[]>([]);
  const [form, setForm] = useState<CreateUserRequest>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);

  const tenantNameMap = useMemo(() => new Map(tenants.map((tenant) => [tenant.id, tenant.name])), [tenants]);

  const load = useCallback(async () => {
    try {
      const [userRows, roleRows, tenantRows] = await Promise.all([authApi.getUsers(), authApi.getRoles(), tenantsApi.list()]);
      setUsers(userRows);
      setRoles(roleRows);
      setTenants(tenantRows);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Không thể tải dữ liệu user";
      toast.error(message);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void load();
    }, 0);
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
      toast.success("Đã tạo user");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Không thể tạo user";
      toast.error(message);
    } finally {
      setSaving(false);
    }
  }, [form]);

  const handleDelete = useCallback(async (username: string) => {
    try {
      await authApi.deleteUser(username);
      setUsers((current) => current.filter((user) => user.username !== username));
      toast.success("Đã xóa user");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Không thể xóa user";
      toast.error(message);
    }
  }, []);

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-6">
      <PageHeader title="Quản lý người dùng" description="Tạo platform admin hoặc tenant admin mới theo đúng tenant scope." />

      <Card className="rounded-3xl border-border/60 shadow-sm">
        <CardHeader>
          <CardTitle>Tạo user mới</CardTitle>
          <CardDescription>Tenant admin bắt buộc phải gắn với một tenant cụ thể.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <div className="space-y-2">
            <Label htmlFor="username">Tên đăng nhập</Label>
            <Input id="username" value={form.username} onChange={(event) => setForm((current) => ({ ...current, username: event.target.value }))} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">Mật khẩu</Label>
            <Input
              id="password"
              type="password"
              value={form.password}
              onChange={(event) => setForm((current) => ({ ...current, password: event.target.value }))}
            />
          </div>
          <div className="space-y-2">
            <Label>Vai trò</Label>
            <Select
              value={form.role}
              onValueChange={(value) =>
                setForm((current) => ({
                  ...current,
                  role: value || "tenant_admin",
                  tenant_id: (value || "tenant_admin") === "tenant_admin" ? current.tenant_id : null,
                }))
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  {roles.map((role) => (
                    <SelectItem key={role.id} value={role.name}>
                      {role.name}
                    </SelectItem>
                  ))}
                </SelectGroup>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>Tenant</Label>
            <TenantSelect
              tenants={tenants}
              value={form.tenant_id}
              onValueChange={(tenantId) => setForm((current) => ({ ...current, tenant_id: tenantId }))}
              disabled={form.role !== "tenant_admin"}
            />
          </div>
          <div className="flex justify-end md:col-span-2 xl:col-span-4">
            <Button className="rounded-2xl" onClick={handleCreate} disabled={saving}>
              <Plus className="mr-2 h-4 w-4" />
              {saving ? "Đang tạo..." : "Tạo user"}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card className="rounded-3xl border-border/60 shadow-sm">
        <CardHeader>
          <CardTitle>Danh sách user</CardTitle>
          <CardDescription>Giữ role rõ ràng để webapp và backend đồng bộ hành vi.</CardDescription>
        </CardHeader>
        <CardContent>
          <Table className="min-w-[720px]">
            <TableHeader>
              <TableRow>
                <TableHead className="pr-4 text-xs text-muted-foreground">Username</TableHead>
                <TableHead className="pr-4 text-xs text-muted-foreground">Vai trò</TableHead>
                <TableHead className="pr-4 text-xs text-muted-foreground">Tenant</TableHead>
                <TableHead className="text-right text-xs text-muted-foreground">Thao tác</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {users.map((user) => (
                <TableRow key={user.id}>
                  <TableCell className="pr-4 font-medium">{user.username}</TableCell>
                  <TableCell className="pr-4">{user.role}</TableCell>
                  <TableCell className="pr-4 text-sm text-muted-foreground">
                    {user.tenant_id ? tenantNameMap.get(user.tenant_id) || "Không rõ tenant" : "—"}
                  </TableCell>
                  <TableCell className="text-right">
                    <Button size="sm" variant="destructive" className="rounded-2xl" onClick={() => handleDelete(user.username)}>
                      <Trash2 className="mr-2 h-4 w-4" />
                      Xóa
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
