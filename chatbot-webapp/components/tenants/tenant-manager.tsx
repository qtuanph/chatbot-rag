"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Copy, Key, Plus, Save, Trash2, Info, Columns, RefreshCw } from "lucide-react";
import { toast } from "sonner";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
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

interface TenantManagerProps {
  initialTenants?: TenantItem[];
}

export function TenantManager({ initialTenants = [] }: TenantManagerProps) {
  const [tenants, setTenants] = useState<TenantItem[]>(initialTenants);
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
  const [loading, setLoading] = useState(initialTenants.length === 0);
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
    void loadTenants();
  }, [loadTenants]);

  useEffect(() => {
    if (!selectedTenantId || !sheetOpen) return;
    void loadTenantDetails();
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
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Quản lý các công ty (Tenants)</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Mỗi công ty/tổ chức (Tenant) là một không gian độc lập. Quản trị viên tại đây có thể tạo tài khoản Tenant Admin và cấu hình API Key cho từng đối tác.
          </p>
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

          <Button
            className="rounded-xl"
            onClick={() => {
              setTenantForm(createEmptyForm());
              setAllowedOriginsDraft("");
              setTenantAdminUsername("");
              setTenantAdminPassword("");
              setCreateOpen(true);
            }}
          >
            <Plus className="mr-2 h-4 w-4" /> Tạo tenant
          </Button>
          <Button className="rounded-xl" variant="outline" onClick={() => loadTenants(false)} disabled={loading}>
            <RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} /> Làm mới
          </Button>
        </div>
      </div>

      {loading && tenants.length === 0 ? (
        <div className="text-sm text-muted-foreground">Đang tải danh sách tenant...</div>
      ) : tenants.length === 0 ? (
        <div className="rounded-xl border border-dashed p-6 text-sm text-muted-foreground">
          Chưa có tenant nào. Hãy tạo tenant đầu tiên.
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              {visibleColumns["Tên tenant"] && <TableHead className="pr-4 text-xs text-muted-foreground">Tên tenant</TableHead>}
              {visibleColumns["Slug"] && <TableHead className="pr-4 text-xs text-muted-foreground">Slug</TableHead>}
              {visibleColumns["Mô tả"] && <TableHead className="pr-4 text-xs text-muted-foreground">Mô tả</TableHead>}
              {visibleColumns["RPM"] && <TableHead className="pr-4 text-right text-xs text-muted-foreground">RPM</TableHead>}
              {visibleColumns["Quota request"] && <TableHead className="pr-4 text-right text-xs text-muted-foreground">Quota request/tháng</TableHead>}
              {visibleColumns["Quota token"] && <TableHead className="pr-4 text-right text-xs text-muted-foreground">Quota token/tháng</TableHead>}
              {visibleColumns["Ngày tạo"] && <TableHead className="pr-4 text-xs text-muted-foreground">Ngày tạo</TableHead>}
              <TableHead className="text-right text-xs text-muted-foreground">Thao tác</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {tenants.map((tenant) => (
              <TableRow
                key={tenant.id}
                className="cursor-pointer transition-colors hover:bg-muted/50"
                onClick={() => openTenant(tenant.id)}
              >
                {visibleColumns["Tên tenant"] && (
                  <TableCell className="pr-4">
                    <div className="font-medium">{tenant.name}</div>
                    <div className="text-xs text-muted-foreground">{tenant.id}</div>
                  </TableCell>
                )}
                {visibleColumns["Slug"] && <TableCell className="pr-4 font-mono text-sm">{tenant.slug}</TableCell>}
                {visibleColumns["Mô tả"] && (
                  <TableCell className="max-w-[240px] truncate pr-4 text-sm text-muted-foreground">
                    {tenant.description || "—"}
                  </TableCell>
                )}
                {visibleColumns["RPM"] && <TableCell className="pr-4 text-right text-sm">{tenant.rate_limit_rpm}</TableCell>}
                {visibleColumns["Quota request"] && (
                  <TableCell className="pr-4 text-right text-sm">
                    {tenant.monthly_request_quota ? tenant.monthly_request_quota.toLocaleString() : "Không giới hạn"}
                  </TableCell>
                )}
                {visibleColumns["Quota token"] && (
                  <TableCell className="pr-4 text-right text-sm">
                    {tenant.monthly_token_quota ? tenant.monthly_token_quota.toLocaleString() : "Không giới hạn"}
                  </TableCell>
                )}
                {visibleColumns["Ngày tạo"] && (
                  <TableCell className="pr-4 text-sm text-muted-foreground">
                    {formatDateTimeVN(tenant.created_at)}
                  </TableCell>
                )}
                <TableCell className="text-right">
                  <Button
                    size="sm"
                    variant="outline"
                    className="rounded-xl"
                    onClick={(event) => {
                      event.stopPropagation();
                      openTenant(tenant.id);
                    }}
                  >
                    Chi tiết
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      {/* Sheet tạo tenant */}
      <Sheet open={createOpen} onOpenChange={setCreateOpen}>
        <SheetContent className="w-full sm:max-w-xl">
          <SheetHeader>
            <SheetTitle>Tạo tenant mới</SheetTitle>
          </SheetHeader>
          <ScrollArea className="h-[calc(100vh-8rem)] pr-4">
            <div className="space-y-6 py-4">
              <FieldGroup className="space-y-4">
                <Field>
                  <FieldLabel>Tên tenant *</FieldLabel>
                  <Input
                    value={tenantForm.name}
                    onChange={(event) => setTenantForm((prev) => ({ ...prev, name: event.target.value }))}
                    placeholder="Công ty Cổ phần Mẫu"
                  />
                </Field>
                <Field>
                  <FieldLabel>Slug</FieldLabel>
                  <Input
                    value={tenantForm.slug || ""}
                    onChange={(event) => setTenantForm((prev) => ({ ...prev, slug: event.target.value }))}
                    placeholder="mau-company (để trống backend tự sinh)"
                  />
                </Field>
                <Field>
                  <FieldLabel>Mô tả</FieldLabel>
                  <Textarea
                    value={tenantForm.description || ""}
                    onChange={(event) => setTenantForm((prev) => ({ ...prev, description: event.target.value }))}
                    placeholder="Mô tả phạm vi hoạt động của tenant..."
                  />
                </Field>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                  <Field>
                    <FieldLabel>Rate limit (RPM)</FieldLabel>
                    <Input
                      type="number"
                      value={tenantForm.rate_limit_rpm ?? 60}
                      onChange={(event) =>
                        setTenantForm((prev) => ({ ...prev, rate_limit_rpm: Number(event.target.value) }))
                      }
                    />
                  </Field>
                  <Field>
                    <FieldLabel>Quota request</FieldLabel>
                    <Input
                      type="number"
                      value={tenantForm.monthly_request_quota ?? ""}
                      onChange={(event) =>
                        setTenantForm((prev) => ({
                          ...prev,
                          monthly_request_quota: event.target.value ? Number(event.target.value) : undefined,
                        }))
                      }
                      placeholder="0 = không giới hạn"
                    />
                  </Field>
                  <Field>
                    <FieldLabel>Quota token</FieldLabel>
                    <Input
                      type="number"
                      value={tenantForm.monthly_token_quota ?? ""}
                      onChange={(event) =>
                        setTenantForm((prev) => ({
                          ...prev,
                          monthly_token_quota: event.target.value ? Number(event.target.value) : undefined,
                        }))
                      }
                      placeholder="0 = không giới hạn"
                    />
                  </Field>
                </div>
                <Field>
                  <FieldLabel>Allowed origins</FieldLabel>
                  <Textarea
                    value={allowedOriginsDraft}
                    onChange={(event) => setAllowedOriginsDraft(event.target.value)}
                    placeholder={"https://app.example.com\nhttps://portal.example.com"}
                  />
                  <FieldDescription>Mỗi dòng một origin cho phép widget nhúng.</FieldDescription>
                </Field>
              </FieldGroup>

              <div className="rounded-xl border border-dashed p-4 space-y-4">
                <div>
                  <div className="font-semibold">Khởi tạo tài khoản Quản trị viên Tenant</div>
                  <div className="text-xs text-muted-foreground">
                    Có thể để trống và tạo sau trong màn hình chi tiết tenant.
                  </div>
                </div>
                <FieldGroup className="space-y-4">
                  <Field>
                    <FieldLabel>Username Admin</FieldLabel>
                    <Input
                      value={tenantAdminUsername}
                      onChange={(event) => setTenantAdminUsername(event.target.value)}
                      placeholder="admin_tenant"
                    />
                  </Field>
                  <Field>
                    <FieldLabel>Mật khẩu</FieldLabel>
                    <Input
                      type="password"
                      value={tenantAdminPassword}
                      onChange={(event) => setTenantAdminPassword(event.target.value)}
                      placeholder="••••••••"
                    />
                  </Field>
                </FieldGroup>
              </div>

              <Button className="w-full rounded-xl" disabled={savingTenant} onClick={handleCreateTenant}>
                <Plus className="mr-2 h-4 w-4" /> {savingTenant ? "Đang tạo..." : "Xác nhận tạo tenant"}
              </Button>
            </div>
          </ScrollArea>
        </SheetContent>
      </Sheet>

      {/* Sheet chi tiết tenant */}
      <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
        <SheetContent className="w-full sm:max-w-2xl">
          <SheetHeader>
            <SheetTitle>Chi tiết tenant: {selectedTenant?.name}</SheetTitle>
          </SheetHeader>
          <ScrollArea className="h-[calc(100vh-8rem)] pr-4">
            <div className="space-y-8 py-4">
              {/* Thông tin cơ bản */}
              <div className="space-y-4">
                <div className="font-semibold text-lg">1. Thông tin chung & Quota</div>
                <FieldGroup className="space-y-4">
                  <Field>
                    <FieldLabel>Tên tenant *</FieldLabel>
                    <Input
                      value={tenantForm.name}
                      onChange={(event) => setTenantForm((prev) => ({ ...prev, name: event.target.value }))}
                    />
                  </Field>
                  <Field>
                    <FieldLabel>Slug</FieldLabel>
                    <Input
                      value={tenantForm.slug || ""}
                      onChange={(event) => setTenantForm((prev) => ({ ...prev, slug: event.target.value }))}
                    />
                  </Field>
                  <Field>
                    <FieldLabel>Mô tả</FieldLabel>
                    <Textarea
                      value={tenantForm.description || ""}
                      onChange={(event) => setTenantForm((prev) => ({ ...prev, description: event.target.value }))}
                    />
                  </Field>
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                    <Field>
                      <FieldLabel>RPM</FieldLabel>
                      <Input
                        type="number"
                        value={tenantForm.rate_limit_rpm ?? 60}
                        onChange={(event) =>
                          setTenantForm((prev) => ({ ...prev, rate_limit_rpm: Number(event.target.value) }))
                        }
                      />
                    </Field>
                    <Field>
                      <FieldLabel>Quota request</FieldLabel>
                      <Input
                        type="number"
                        value={tenantForm.monthly_request_quota ?? ""}
                        onChange={(event) =>
                          setTenantForm((prev) => ({
                            ...prev,
                            monthly_request_quota: event.target.value ? Number(event.target.value) : undefined,
                          }))
                        }
                      />
                    </Field>
                    <Field>
                      <FieldLabel>Quota token</FieldLabel>
                      <Input
                        type="number"
                        value={tenantForm.monthly_token_quota ?? ""}
                        onChange={(event) =>
                          setTenantForm((prev) => ({
                            ...prev,
                            monthly_token_quota: event.target.value ? Number(event.target.value) : undefined,
                          }))
                        }
                      />
                    </Field>
                  </div>
                  <Field>
                    <FieldLabel>Allowed origins</FieldLabel>
                    <Textarea
                      value={allowedOriginsDraft}
                      onChange={(event) => setAllowedOriginsDraft(event.target.value)}
                    />
                  </Field>
                  <Button className="rounded-xl" disabled={savingTenant} onClick={handleUpdateTenant}>
                    <Save className="mr-2 h-4 w-4" /> {savingTenant ? "Đang lưu..." : "Lưu thông tin tenant"}
                  </Button>
                </FieldGroup>
              </div>

              {/* Cài đặt Chatbot (TenantSettingsForm) */}
              {selectedTenantId && (
                <div className="space-y-4 border-t pt-6">
                  <div className="font-semibold text-lg">2. Cấu hình Prompt & Tham số AI</div>
                  <TenantSettingsForm mode="tenant" tenantId={selectedTenantId} />
                </div>
              )}

              {/* Quản lý API Key */}
              <div className="space-y-4 border-t pt-6">
                <div className="font-semibold text-lg">3. API Keys tích hợp Widget/API</div>
                {rawApiKey && (
                  <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3 text-xs">
                    <div className="font-semibold text-emerald-600 dark:text-emerald-400">
                      API Key mới tạo (Chỉ hiển thị 1 lần duy nhất):
                    </div>
                    <div className="mt-1 flex items-center justify-between font-mono break-all">
                      <span>{rawApiKey}</span>
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-6 w-6 ml-2"
                        onClick={() => {
                          navigator.clipboard.writeText(rawApiKey);
                          toast.success("Đã copy API key");
                        }}
                      >
                        <Copy className="h-3 w-3" />
                      </Button>
                    </div>
                  </div>
                )}
                <div className="flex gap-2">
                  <Input
                    value={newApiKey.name}
                    onChange={(event) => setNewApiKey({ name: event.target.value })}
                    placeholder="Tên API Key (ví dụ: Website Widget Key)"
                  />
                  <Button className="rounded-xl shrink-0" disabled={savingApiKey} onClick={handleCreateApiKey}>
                    <Key className="mr-2 h-4 w-4" /> Tạo Key
                  </Button>
                </div>
                {apiKeys.length === 0 ? (
                  <div className="text-xs text-muted-foreground">Chưa có API key nào cho tenant này.</div>
                ) : (
                  <div className="space-y-2">
                    {apiKeys.map((k) => (
                      <div key={k.id} className="flex items-center justify-between rounded-xl border p-3 text-xs">
                        <div>
                          <div className="font-medium">{k.name}</div>
                          <div className="font-mono text-muted-foreground">{k.key_prefix}...</div>
                        </div>
                        <div className="flex items-center gap-2">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] uppercase font-bold ${
                              k.status === "active" ? "bg-emerald-500/10 text-emerald-500" : "bg-muted text-muted-foreground"
                            }`}
                          >
                            {k.status}
                          </span>
                          {k.status === "active" && (
                            <Button
                              size="sm"
                              variant="destructive"
                              className="h-7 text-xs rounded-lg"
                              onClick={() => handleRevokeApiKey(k.id)}
                            >
                              Thu hồi
                            </Button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Tài khoản Quản trị viên Tenant */}
              <div className="space-y-4 border-t pt-6">
                <div className="font-semibold text-lg">4. Tài khoản Tenant Admin</div>
                {lastCreatedTenantAdmin && (
                  <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3 text-xs">
                    <div className="font-semibold text-emerald-600 dark:text-emerald-400">
                      Tài khoản Tenant Admin vừa tạo:
                    </div>
                    <div className="mt-1 font-mono">
                      Username: {lastCreatedTenantAdmin.username} | Password: {lastCreatedTenantAdmin.password}
                    </div>
                  </div>
                )}
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  <Input
                    value={tenantAdminUsername}
                    onChange={(event) => setTenantAdminUsername(event.target.value)}
                    placeholder="Username mới"
                  />
                  <Input
                    type="password"
                    value={tenantAdminPassword}
                    onChange={(event) => setTenantAdminPassword(event.target.value)}
                    placeholder="Mật khẩu mới"
                  />
                </div>
                <Button className="w-full rounded-xl" disabled={savingTenantUser} onClick={handleCreateTenantUser}>
                  <Plus className="mr-2 h-4 w-4" /> Tạo Tenant Admin
                </Button>
                {tenantUsers.length === 0 ? (
                  <div className="text-xs text-muted-foreground">Chưa có user quản trị nào thuộc tenant này.</div>
                ) : (
                  <div className="space-y-2">
                    {tenantUsers.map((u) => (
                      <div key={u.id} className="flex items-center justify-between rounded-xl border p-3 text-xs">
                        <div>
                          <div className="font-medium">{u.username}</div>
                          <div className="text-[10px] text-muted-foreground">{u.role}</div>
                        </div>
                        <Button
                          size="icon"
                          variant="destructive"
                          className="h-7 w-7 rounded-lg"
                          onClick={() => handleDeleteTenantUser(u.username)}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </ScrollArea>
        </SheetContent>
      </Sheet>
    </div>
  );
}
