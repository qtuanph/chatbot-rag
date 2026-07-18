"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Copy, Key, Plus, Save, Trash2, Info, Columns } from "lucide-react";
import { toast } from "sonner";

import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { DropdownMenu, DropdownMenuCheckboxItem, DropdownMenuContent, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";

import { TenantSettingsForm } from "@/components/tenants/tenant-settings-form";
import { Button, buttonVariants } from "@/components/ui/button";
import { Field, FieldContent, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { authApi, tenantsApi } from "@/lib/api-client";
import { formatDateTimeVN } from "@/lib/format";
import {
  CreateUserRequestSchema,
  TenantApiKeyCreateRequestSchema,
  TenantCreateRequestSchema,
  TenantUpdateRequestSchema,
} from "@/lib/schemas";
import type {
  TenantApiKeyCreateRequest,
  TenantApiKeyCreateResponse,
  TenantApiKeyItem,
  TenantCreateRequest,
  TenantItem,
  TenantUpdateRequest,
  UserItem,
} from "@/types/api";

const EMPTY_FORM: TenantCreateRequest = {
  name: "",
  slug: "",
  description: "",
  rate_limit_rpm: 60,
  allowed_origins: [],
};

function createEmptyForm(): TenantCreateRequest {
  return { ...EMPTY_FORM, allowed_origins: [] };
}

function stringifyAllowedOrigins(origins?: string[] | null): string {
  return (origins || []).join("\n");
}

function parseAllowedOriginsDraft(draft: string): string[] {
  return draft.split(/\r?\n/).map((item) => item.trim()).filter(Boolean);
}

const TABLE_COLUMNS = [
  "Tên tenant",
  "Slug",
  "Mô tả",
  "RPM",
  "Quota request",
  "Quota token",
  "Ngày tạo",
];

export default function AdminTenantsPage() {
  const [tenants, setTenants] = useState<TenantItem[]>([]);
  const [selectedTenantId, setSelectedTenantId] = useState<string>("");
  const [sheetOpen, setSheetOpen] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [tenantForm, setTenantForm] = useState<TenantCreateRequest>(createEmptyForm);
  const [allowedOriginsDraft, setAllowedOriginsDraft] = useState("");
  const [apiKeys, setApiKeys] = useState<TenantApiKeyItem[]>([]);
  const [newApiKey, setNewApiKey] = useState<TenantApiKeyCreateRequest>({ name: "" });
  const [rawApiKey, setRawApiKey] = useState<string>("");
  const [tenantUsers, setTenantUsers] = useState<UserItem[]>([]);
  const [tenantAdminUsername, setTenantAdminUsername] = useState("");
  const [tenantAdminPassword, setTenantAdminPassword] = useState("");
  const [lastCreatedTenantAdmin, setLastCreatedTenantAdmin] = useState<{ username: string; password: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [savingTenant, setSavingTenant] = useState(false);
  const [savingApiKey, setSavingApiKey] = useState(false);
  const [savingTenantUser, setSavingTenantUser] = useState(false);
  const [visibleColumns, setVisibleColumns] = useState<Record<string, boolean>>(
    TABLE_COLUMNS.reduce((acc, col) => ({ ...acc, [col]: true }), {})
  );

  const selectedTenant = useMemo(
    () => tenants.find((t) => t.id === selectedTenantId) || null,
    [selectedTenantId, tenants],
  );

  const loadTenants = useCallback(async () => {
    try {
      setLoading(true);
      const rows = await tenantsApi.list();
      setTenants(rows);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Không thể tải danh sách tenant";
      toast.error(message);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadTenantDetails = useCallback(async () => {
    if (!selectedTenantId) return;
    try {
      const [tenant, keys, users] = await Promise.all([
        tenantsApi.get(selectedTenantId),
        tenantsApi.listApiKeys(selectedTenantId),
        authApi.getUsers(),
      ]);
      setTenantForm({
        name: tenant.name,
        slug: tenant.slug,
        description: tenant.description || "",
        monthly_request_quota: tenant.monthly_request_quota,
        monthly_token_quota: tenant.monthly_token_quota,
        rate_limit_rpm: tenant.rate_limit_rpm,
        allowed_origins: tenant.allowed_origins,
      });
      setAllowedOriginsDraft(stringifyAllowedOrigins(tenant.allowed_origins));
      setApiKeys(keys);
      setTenantUsers(users.filter((u) => u.tenant_id === selectedTenantId));
    } catch (error) {
      const message = error instanceof Error ? error.message : "Không thể tải chi tiết tenant";
      toast.error(message);
    }
  }, [selectedTenantId]);

  useEffect(() => {
    const t = window.setTimeout(() => { void loadTenants(); }, 0);
    return () => window.clearTimeout(t);
  }, [loadTenants]);

  useEffect(() => {
    if (!selectedTenantId || !sheetOpen) return;
    const t = window.setTimeout(() => { void loadTenantDetails(); }, 0);
    return () => window.clearTimeout(t);
  }, [selectedTenantId, sheetOpen, loadTenantDetails]);

  const openTenant = useCallback((tenantId: string) => {
    setSelectedTenantId(tenantId);
    setRawApiKey("");
    setLastCreatedTenantAdmin(null);
    setSheetOpen(true);
  }, []);

  const handleCreateTenant = useCallback(async () => {
    try {
      setSavingTenant(true);
      const payload: TenantCreateRequest = {
        ...tenantForm,
        allowed_origins: parseAllowedOriginsDraft(allowedOriginsDraft),
        admin_username: tenantAdminUsername.trim() || undefined,
        admin_password: tenantAdminPassword || undefined,
      };

      const parsedPayload = TenantCreateRequestSchema.safeParse(payload);
      if (!parsedPayload.success) {
        toast.error("Dữ liệu tenant không hợp lệ");
        return;
      }

      const created = await tenantsApi.create(parsedPayload.data);
      setTenants((current) => [created, ...current.filter((t) => t.id !== created.id)]);
      setCreateOpen(false);
      openTenant(created.id);
      setLastCreatedTenantAdmin(
        tenantAdminUsername.trim() && tenantAdminPassword
          ? { username: tenantAdminUsername.trim(), password: tenantAdminPassword }
          : null,
      );
      setTenantAdminUsername("");
      setTenantAdminPassword("");
      toast.success("Đã tạo tenant mới");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Không thể tạo tenant";
      toast.error(message);
    } finally {
      setSavingTenant(false);
    }
  }, [allowedOriginsDraft, tenantAdminPassword, tenantAdminUsername, tenantForm, openTenant]);

  const handleUpdateTenant = useCallback(async () => {
    if (!selectedTenantId) return;
    try {
      setSavingTenant(true);
      const payload: TenantUpdateRequest = {
        slug: tenantForm.slug?.trim() || undefined,
        name: tenantForm.name,
        description: tenantForm.description || "",
        monthly_request_quota: Number(tenantForm.monthly_request_quota || 0),
        monthly_token_quota: Number(tenantForm.monthly_token_quota || 0),
        rate_limit_rpm: Number(tenantForm.rate_limit_rpm || 60),
        allowed_origins: parseAllowedOriginsDraft(allowedOriginsDraft),
      };

      const parsedPayload = TenantUpdateRequestSchema.safeParse(payload);
      if (!parsedPayload.success) {
        toast.error("Dữ liệu cập nhật tenant không hợp lệ");
        return;
      }

      const updated = await tenantsApi.update(selectedTenantId, parsedPayload.data);
      setTenants((current) => current.map((t) => (t.id === updated.id ? updated : t)));
      setTenantForm((current) => ({ ...current, slug: updated.slug, allowed_origins: updated.allowed_origins }));
      setAllowedOriginsDraft(stringifyAllowedOrigins(updated.allowed_origins));
      toast.success("Đã cập nhật tenant");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Không thể cập nhật tenant";
      toast.error(message);
    } finally {
      setSavingTenant(false);
    }
  }, [allowedOriginsDraft, selectedTenantId, tenantForm]);

  const handleCreateApiKey = useCallback(async () => {
    if (!selectedTenantId || !newApiKey.name.trim()) return;
    try {
      setSavingApiKey(true);
      const payload = {
        name: newApiKey.name.trim(),
        expires_at: newApiKey.expires_at || null,
      };

      const parsedPayload = TenantApiKeyCreateRequestSchema.safeParse(payload);
      if (!parsedPayload.success) {
        toast.error("Dữ liệu API key không hợp lệ");
        return;
      }

      const result: TenantApiKeyCreateResponse = await tenantsApi.createApiKey(selectedTenantId, parsedPayload.data);
      setApiKeys((current) => [result, ...current]);
      setNewApiKey({ name: "" });
      setRawApiKey(result.raw_api_key);
      toast.success("Đã tạo API key");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Không thể tạo API key";
      toast.error(message);
    } finally {
      setSavingApiKey(false);
    }
  }, [newApiKey, selectedTenantId]);

  const handleRevokeApiKey = useCallback(async (keyId: string) => {
    if (!selectedTenantId) return;
    try {
      const revoked = await tenantsApi.revokeApiKey(selectedTenantId, keyId);
      setApiKeys((current) => current.map((item) => (item.id === revoked.id ? revoked : item)));
      toast.success("Đã thu hồi API key");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Không thể thu hồi API key";
      toast.error(message);
    }
  }, [selectedTenantId]);

  const handleCreateTenantUser = useCallback(async () => {
    if (!selectedTenantId || !tenantAdminUsername.trim() || !tenantAdminPassword.trim()) return;
    try {
      setSavingTenantUser(true);
      const payload = {
        username: tenantAdminUsername.trim(),
        password: tenantAdminPassword,
        role: "tenant_admin",
        tenant_id: selectedTenantId,
      };

      const parsedPayload = CreateUserRequestSchema.safeParse(payload);
      if (!parsedPayload.success) {
        toast.error("Dữ liệu tenant admin không hợp lệ");
        return;
      }

      const created = await authApi.createUser(parsedPayload.data);
      setTenantUsers((current) => [...current, created]);
      setLastCreatedTenantAdmin({ username: tenantAdminUsername.trim(), password: tenantAdminPassword });
      setTenantAdminUsername("");
      setTenantAdminPassword("");
      toast.success("Đã tạo tenant admin");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Không thể tạo tenant admin";
      toast.error(message);
    } finally {
      setSavingTenantUser(false);
    }
  }, [selectedTenantId, tenantAdminPassword, tenantAdminUsername]);

  const handleDeleteTenantUser = useCallback(async (username: string) => {
    try {
      await authApi.deleteUser(username);
      setTenantUsers((current) => current.filter((u) => u.username !== username));
      toast.success("Đã xóa tenant admin");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Không thể xóa tenant admin";
      toast.error(message);
    }
  }, []);

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Quản lý tenant</h1>
          <p className="text-sm text-muted-foreground">Chọn tenant để xem và chỉnh sửa chi tiết.</p>
        </div>
        <div className="flex gap-2">
          <DropdownMenu>
            <DropdownMenuTrigger className={buttonVariants({ variant: "outline" })}>
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
          <Button onClick={() => { setCreateOpen(true); setTenantForm(createEmptyForm()); setAllowedOriginsDraft(""); }}>
            <Plus className="mr-2 h-4 w-4" /> Tạo tenant
          </Button>
        </div>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            {TABLE_COLUMNS.map((col) => (
              visibleColumns[col] ? <TableHead key={col} className="text-xs text-muted-foreground">{col}</TableHead> : null
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {loading ? (
            <TableRow>
              <TableCell colSpan={TABLE_COLUMNS.length} className="text-center text-sm text-muted-foreground py-8">
                Đang tải...
              </TableCell>
            </TableRow>
          ) : tenants.length === 0 ? (
            <TableRow>
              <TableCell colSpan={TABLE_COLUMNS.length} className="text-center text-sm text-muted-foreground py-8">
                Chưa có tenant nào.
              </TableCell>
            </TableRow>
          ) : (
            tenants.map((tenant) => (
              <TableRow
                key={tenant.id}
                className="cursor-pointer"
                onClick={() => openTenant(tenant.id)}
              >
                {visibleColumns["Tên tenant"] && <TableCell className="font-medium">{tenant.name}</TableCell>}
                {visibleColumns["Slug"] && <TableCell className="font-mono text-xs">{tenant.slug}</TableCell>}
                {visibleColumns["Mô tả"] && <TableCell className="max-w-xs truncate text-sm text-muted-foreground">{tenant.description || "—"}</TableCell>}
                {visibleColumns["RPM"] && <TableCell>{tenant.rate_limit_rpm}</TableCell>}
                {visibleColumns["Quota request"] && <TableCell>{tenant.monthly_request_quota ?? "—"}</TableCell>}
                {visibleColumns["Quota token"] && <TableCell>{tenant.monthly_token_quota ?? "—"}</TableCell>}
                {visibleColumns["Ngày tạo"] && <TableCell className="text-sm text-muted-foreground">{formatDateTimeVN(tenant.created_at)}</TableCell>}
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>

      {/* ── Create Sheet ── */}
      <Sheet open={createOpen} onOpenChange={setCreateOpen}>
        <SheetContent className="w-[90vw] sm:max-w-xl overflow-y-auto" side="right">
          <SheetHeader>
            <SheetTitle>Tạo tenant mới</SheetTitle>
          </SheetHeader>
          <form onSubmit={(e) => { e.preventDefault(); handleCreateTenant(); }}>
            <FieldGroup className="grid gap-4">
              <Field>
                <FieldContent>
                  <FieldLabel htmlFor="create_name">Tên tenant</FieldLabel>
                  <Input id="create_name" value={tenantForm.name || ""} onChange={(e) => setTenantForm((c) => ({ ...c, name: e.target.value }))} />
                </FieldContent>
              </Field>
              <Field>
                <FieldContent>
                  <FieldLabel htmlFor="create_slug" className="flex items-center gap-1">
                    Slug
                    <TooltipProvider delay={100}>
                      <Tooltip>
                        <TooltipTrigger type="button"><Info className="h-3 w-3 text-muted-foreground" /></TooltipTrigger>
                        <TooltipContent>Mã định danh dùng trên URL (tự động đổi dấu cách thành dấu gạch ngang).</TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  </FieldLabel>
                  <Input id="create_slug" value={tenantForm.slug || ""} onChange={(e) => setTenantForm((c) => ({ ...c, slug: e.target.value.replace(/\s+/g, '-') }))} placeholder="Ví dụ: acme-corp" />
                </FieldContent>
              </Field>
              <Field>
                <FieldContent>
                  <FieldLabel htmlFor="create_desc">Mô tả</FieldLabel>
                  <Textarea id="create_desc" rows={2} value={tenantForm.description || ""} onChange={(e) => setTenantForm((c) => ({ ...c, description: e.target.value }))} />
                </FieldContent>
              </Field>
              <Field>
                <FieldContent>
                  <FieldLabel htmlFor="create_rpm">Rate limit RPM</FieldLabel>
                  <Input id="create_rpm" type="number" value={tenantForm.rate_limit_rpm ?? 60} onChange={(e) => setTenantForm((c) => ({ ...c, rate_limit_rpm: Number(e.target.value || 60) }))} />
                </FieldContent>
              </Field>
              <Field>
                <FieldContent>
                  <FieldLabel htmlFor="create_quota_req">Quota request / tháng</FieldLabel>
                  <Input id="create_quota_req" type="number" value={tenantForm.monthly_request_quota ?? ""} onChange={(e) => setTenantForm((c) => ({ ...c, monthly_request_quota: Number(e.target.value || 0) }))} />
                </FieldContent>
              </Field>
              <Field>
                <FieldContent>
                  <FieldLabel htmlFor="create_quota_token">Quota token / tháng</FieldLabel>
                  <Input id="create_quota_token" type="number" value={tenantForm.monthly_token_quota ?? ""} onChange={(e) => setTenantForm((c) => ({ ...c, monthly_token_quota: Number(e.target.value || 0) }))} />
                </FieldContent>
              </Field>
              <Field>
                <FieldContent>
                  <FieldLabel htmlFor="create_origins">Allowed origins</FieldLabel>
                  <Textarea id="create_origins" rows={3} value={allowedOriginsDraft} onChange={(e) => setAllowedOriginsDraft(e.target.value)} placeholder={"https://erp.company.vn\nhttps://portal.company.vn"} />
                  <FieldDescription>Mỗi dòng một origin.</FieldDescription>
                </FieldContent>
              </Field>
              <Field>
                <FieldContent>
                  <FieldLabel htmlFor="create_admin_user">Admin username</FieldLabel>
                  <Input id="create_admin_user" value={tenantAdminUsername} onChange={(e) => setTenantAdminUsername(e.target.value)} placeholder="Ví dụ: acme.admin" />
                </FieldContent>
              </Field>
              <Field>
                <FieldContent>
                  <FieldLabel htmlFor="create_admin_pass">Admin password</FieldLabel>
                  <Input id="create_admin_pass" type="password" value={tenantAdminPassword} onChange={(e) => setTenantAdminPassword(e.target.value)} placeholder="Ít nhất 6 ký tự" />
                </FieldContent>
              </Field>
              <div className="flex justify-end gap-2 pt-2">
                <Button type="button" variant="outline" onClick={() => setCreateOpen(false)}>Hủy</Button>
                <Button type="submit" disabled={savingTenant}>
                  <Plus className="mr-2 h-4 w-4" />
                  {savingTenant ? "Đang tạo..." : "Tạo tenant"}
                </Button>
              </div>
            </FieldGroup>
          </form>
        </SheetContent>
      </Sheet>

      {/* ── Tenant Detail Sheet ── */}
      <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
        <SheetContent className="w-[90vw] sm:max-w-4xl overflow-y-auto">
          <SheetHeader>
            <SheetTitle>{selectedTenant?.name || "Chi tiết tenant"}</SheetTitle>
          </SheetHeader>
          {selectedTenantId ? (
            <div className="flex flex-col gap-6">
              {/* Basic Info */}
              <section>
                <h3 className="font-heading text-base font-medium pb-3 border-b mb-4">Thông tin cơ bản</h3>
                <FieldGroup className="grid gap-4 md:grid-cols-2">
                  <Field>
                    <FieldContent>
                      <FieldLabel htmlFor="sheet_name">Tên tenant</FieldLabel>
                      <Input id="sheet_name" value={tenantForm.name || ""} onChange={(e) => setTenantForm((c) => ({ ...c, name: e.target.value }))} />
                    </FieldContent>
                  </Field>
                  <Field>
                    <FieldContent>
                      <FieldLabel htmlFor="sheet_slug" className="flex items-center gap-1">
                        Slug
                        <TooltipProvider delay={100}>
                          <Tooltip>
                            <TooltipTrigger type="button"><Info className="h-3 w-3 text-muted-foreground" /></TooltipTrigger>
                            <TooltipContent>Mã định danh dùng trên URL (tự động đổi dấu cách thành dấu gạch ngang).</TooltipContent>
                          </Tooltip>
                        </TooltipProvider>
                      </FieldLabel>
                      <Input id="sheet_slug" value={tenantForm.slug || ""} onChange={(e) => setTenantForm((c) => ({ ...c, slug: e.target.value.replace(/\s+/g, '-') }))} />
                    </FieldContent>
                  </Field>
                  <Field className="md:col-span-2">
                    <FieldContent>
                      <FieldLabel htmlFor="sheet_desc">Mô tả</FieldLabel>
                      <Textarea id="sheet_desc" rows={2} value={tenantForm.description || ""} onChange={(e) => setTenantForm((c) => ({ ...c, description: e.target.value }))} />
                    </FieldContent>
                  </Field>
                  <Field>
                    <FieldContent>
                      <FieldLabel htmlFor="sheet_rpm">Rate limit RPM</FieldLabel>
                      <Input id="sheet_rpm" type="number" value={tenantForm.rate_limit_rpm ?? 60} onChange={(e) => setTenantForm((c) => ({ ...c, rate_limit_rpm: Number(e.target.value || 60) }))} />
                    </FieldContent>
                  </Field>
                  <Field>
                    <FieldContent>
                      <FieldLabel htmlFor="sheet_quota_req">Quota request / tháng</FieldLabel>
                      <Input id="sheet_quota_req" type="number" value={tenantForm.monthly_request_quota ?? ""} onChange={(e) => setTenantForm((c) => ({ ...c, monthly_request_quota: Number(e.target.value || 0) }))} />
                    </FieldContent>
                  </Field>
                  <Field>
                    <FieldContent>
                      <FieldLabel htmlFor="sheet_quota_token">Quota token / tháng</FieldLabel>
                      <Input id="sheet_quota_token" type="number" value={tenantForm.monthly_token_quota ?? ""} onChange={(e) => setTenantForm((c) => ({ ...c, monthly_token_quota: Number(e.target.value || 0) }))} />
                    </FieldContent>
                  </Field>
                  <Field className="md:col-span-2">
                    <FieldContent>
                      <FieldLabel htmlFor="sheet_origins">Allowed origins</FieldLabel>
                      <Textarea id="sheet_origins" rows={3} value={allowedOriginsDraft} onChange={(e) => setAllowedOriginsDraft(e.target.value)} />
                      <FieldDescription>Mỗi dòng một origin.</FieldDescription>
                    </FieldContent>
                  </Field>
                  <div className="flex justify-end md:col-span-2">
                    <Button onClick={handleUpdateTenant} disabled={savingTenant}>
                      <Save className="mr-2 h-4 w-4" />
                      {savingTenant ? "Đang lưu..." : "Lưu"}
                    </Button>
                  </div>
                </FieldGroup>
              </section>

              {/* Created admin */}
              {lastCreatedTenantAdmin ? (
                <section>
                  <h3 className="font-heading text-base font-medium pb-3 border-b mb-4">Tài khoản vừa tạo</h3>
                  <p className="text-sm text-muted-foreground mb-4">Mật khẩu không thể xem lại sau này.</p>
                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="rounded-lg border p-3">
                      <div className="text-xs text-muted-foreground">Username</div>
                      <div className="font-medium">{lastCreatedTenantAdmin.username}</div>
                    </div>
                    <div className="rounded-lg border p-3">
                      <div className="text-xs text-muted-foreground">Mật khẩu</div>
                      <div className="font-medium">{lastCreatedTenantAdmin.password}</div>
                    </div>
                  </div>
                </section>
              ) : null}

              {/* Settings */}
              <section>
                <h3 className="font-heading text-base font-medium pb-3 border-b mb-4">Cấu hình chatbot</h3>
                <TenantSettingsForm mode="tenant" tenantId={selectedTenantId} noCard />
              </section>

              {/* API Keys */}
              <section>
                <h3 className="font-heading text-base font-medium pb-3 border-b mb-4">API key</h3>
                <p className="text-sm text-muted-foreground mb-4">Raw key chỉ hiển thị một lần sau khi tạo.</p>
                <div className="flex gap-2 mb-4">
                  <Input
                    value={newApiKey.name || ""}
                    onChange={(e) => setNewApiKey({ ...newApiKey, name: e.target.value })}
                    placeholder="Tên key"
                  />
                  <Input
                    type="datetime-local"
                    value={newApiKey.expires_at || ""}
                    onChange={(e) => setNewApiKey({ ...newApiKey, expires_at: e.target.value || null })}
                    className="max-w-48"
                  />
                  <Button onClick={handleCreateApiKey} disabled={savingApiKey}>
                    <Key className="mr-2 h-4 w-4" />
                    {savingApiKey ? "Đang tạo..." : "Tạo"}
                  </Button>
                </div>

                {rawApiKey ? (
                  <div className="rounded-lg border border-dashed p-3 text-sm mb-4">
                    <div className="mb-1 font-medium">Raw key mới</div>
                    <div className="flex items-center gap-2">
                      <code className="flex-1 overflow-x-auto rounded bg-muted px-2 py-1 text-xs">{rawApiKey}</code>
                      <Button variant="outline" size="sm" onClick={async () => { await navigator.clipboard.writeText(rawApiKey); toast.success("Đã copy"); }}>
                        <Copy className="mr-1 h-3 w-3" /> Copy
                      </Button>
                    </div>
                  </div>
                ) : null}

                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="text-xs text-muted-foreground">Tên</TableHead>
                      <TableHead className="text-xs text-muted-foreground">Prefix</TableHead>
                      <TableHead className="text-xs text-muted-foreground">Trạng thái</TableHead>
                      <TableHead className="text-xs text-muted-foreground">Lần cuối</TableHead>
                      <TableHead className="text-xs text-muted-foreground">Hết hạn</TableHead>
                      <TableHead className="text-right text-xs text-muted-foreground">Thao tác</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {apiKeys.map((item) => (
                      <TableRow key={item.id}>
                        <TableCell className="font-medium">{item.name}</TableCell>
                        <TableCell className="font-mono text-xs">{item.key_prefix}</TableCell>
                        <TableCell>{item.status}</TableCell>
                        <TableCell className="text-sm text-muted-foreground">{formatDateTimeVN(item.last_used_at)}</TableCell>
                        <TableCell className="text-sm text-muted-foreground">{formatDateTimeVN(item.expires_at)}</TableCell>
                        <TableCell className="text-right">
                          {item.status === "active" ? (
                            <Button size="sm" variant="destructive" onClick={() => handleRevokeApiKey(item.id)}>
                              <Trash2 className="mr-1 h-3 w-3" /> Thu hồi
                            </Button>
                          ) : (
                            <span className="text-xs text-muted-foreground">Đã thu hồi</span>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </section>

              {/* Tenant Users */}
              <section>
                <h3 className="font-heading text-base font-medium pb-3 border-b mb-4">Tài khoản tenant admin</h3>
                <div className="flex gap-2 mb-4">
                  <Input
                    value={tenantAdminUsername}
                    onChange={(e) => setTenantAdminUsername(e.target.value)}
                    placeholder="Username"
                  />
                  <Input
                    type="password"
                    value={tenantAdminPassword}
                    onChange={(e) => setTenantAdminPassword(e.target.value)}
                    placeholder="Password"
                  />
                  <Button onClick={handleCreateTenantUser} disabled={savingTenantUser}>
                    <Plus className="mr-1 h-3 w-3" />
                    {savingTenantUser ? "Đang tạo..." : "Tạo"}
                  </Button>
                </div>

                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="text-xs text-muted-foreground">Username</TableHead>
                      <TableHead className="text-xs text-muted-foreground">Vai trò</TableHead>
                      <TableHead className="text-right text-xs text-muted-foreground">Thao tác</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {tenantUsers.map((user) => (
                      <TableRow key={user.id}>
                        <TableCell className="font-medium">{user.username}</TableCell>
                        <TableCell className="text-sm">{user.role}</TableCell>
                        <TableCell className="text-right">
                          <Button size="sm" variant="destructive" onClick={() => handleDeleteTenantUser(user.username)}>
                            <Trash2 className="mr-1 h-3 w-3" /> Xóa
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </section>
            </div>
          ) : (
            <p className="mt-6 text-sm text-muted-foreground">Đang tải...</p>
          )}
        </SheetContent>
      </Sheet>
    </div>
  );
}
