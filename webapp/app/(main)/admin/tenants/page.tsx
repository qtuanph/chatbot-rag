"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Copy, KeyRound, Plus, Save, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/layout/page-header";
import { TenantSettingsForm } from "@/components/tenants/tenant-settings-form";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, FieldContent, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { authApi, tenantsApi } from "@/lib/api-client";
import { formatDateTimeVN } from "@/lib/format";
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
  return {
    ...EMPTY_FORM,
    allowed_origins: [],
  };
}

function stringifyAllowedOrigins(origins?: string[] | null): string {
  return (origins || []).join("\n");
}

function parseAllowedOriginsDraft(draft: string): string[] {
  return draft
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export default function AdminTenantsPage() {
  const [tenants, setTenants] = useState<TenantItem[]>([]);
  const [selectedTenantId, setSelectedTenantId] = useState<string>("");
  const [isCreatingTenant, setIsCreatingTenant] = useState(false);
  const [tenantForm, setTenantForm] = useState<TenantCreateRequest>(createEmptyForm);
  const [allowedOriginsDraft, setAllowedOriginsDraft] = useState("");
  const [apiKeys, setApiKeys] = useState<TenantApiKeyItem[]>([]);
  const [newApiKey, setNewApiKey] = useState<TenantApiKeyCreateRequest>({ name: "" });
  const [rawApiKey, setRawApiKey] = useState<string>("");
  const [tenantUsers, setTenantUsers] = useState<UserItem[]>([]);
  const [tenantAdminUsername, setTenantAdminUsername] = useState("");
  const [tenantAdminPassword, setTenantAdminPassword] = useState("");
  const [lastCreatedTenantAdmin, setLastCreatedTenantAdmin] = useState<{ username: string; password: string } | null>(
    null,
  );
  const [loading, setLoading] = useState(true);
  const [savingTenant, setSavingTenant] = useState(false);
  const [savingApiKey, setSavingApiKey] = useState(false);
  const [savingTenantUser, setSavingTenantUser] = useState(false);

  const selectedTenant = useMemo(
    () => tenants.find((tenant) => tenant.id === selectedTenantId) || null,
    [selectedTenantId, tenants],
  );

  const loadTenants = useCallback(async () => {
    try {
      setLoading(true);
      const rows = await tenantsApi.list();
      setTenants(rows);
      if (isCreatingTenant) {
        return;
      }
      const hasCurrentSelection = selectedTenantId && rows.some((tenant) => tenant.id === selectedTenantId);
      setSelectedTenantId(hasCurrentSelection ? selectedTenantId : rows[0]?.id || "");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Không thể tải danh sách tenant";
      toast.error(message);
    } finally {
      setLoading(false);
    }
  }, [isCreatingTenant, selectedTenantId]);

  const loadTenantDetails = useCallback(async () => {
    if (!selectedTenantId || isCreatingTenant) return;
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
      setTenantUsers(users.filter((user) => user.tenant_id === selectedTenantId));
    } catch (error) {
      const message = error instanceof Error ? error.message : "Không thể tải chi tiết tenant";
      toast.error(message);
    }
  }, [isCreatingTenant, selectedTenantId]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadTenants();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadTenants]);

  useEffect(() => {
    if (!selectedTenantId || isCreatingTenant) return;
    const timer = window.setTimeout(() => {
      void loadTenantDetails();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [isCreatingTenant, loadTenantDetails, selectedTenantId]);

  const handleStartCreate = useCallback(() => {
    setIsCreatingTenant(true);
    setSelectedTenantId("");
    setTenantForm(createEmptyForm());
    setAllowedOriginsDraft("");
    setApiKeys([]);
    setTenantUsers([]);
    setRawApiKey("");
    setNewApiKey({ name: "" });
    setTenantAdminUsername("");
    setTenantAdminPassword("");
    setLastCreatedTenantAdmin(null);
  }, []);

  const handleSelectTenant = useCallback((tenantId: string) => {
    setIsCreatingTenant(false);
    setSelectedTenantId(tenantId);
    setRawApiKey("");
    setLastCreatedTenantAdmin(null);
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
      const created = await tenantsApi.create(payload);
      setTenants((current) => [created, ...current.filter((tenant) => tenant.id !== created.id)]);
      setIsCreatingTenant(false);
      setSelectedTenantId(created.id);
      setTenantForm({
        name: created.name,
        slug: created.slug,
        description: created.description || "",
        monthly_request_quota: created.monthly_request_quota,
        monthly_token_quota: created.monthly_token_quota,
        rate_limit_rpm: created.rate_limit_rpm,
        allowed_origins: created.allowed_origins,
      });
      setAllowedOriginsDraft(stringifyAllowedOrigins(created.allowed_origins));
      setApiKeys([]);
      setTenantUsers([]);
      setRawApiKey("");
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
  }, [allowedOriginsDraft, tenantAdminPassword, tenantAdminUsername, tenantForm]);

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
      const updated = await tenantsApi.update(selectedTenantId, payload);
      setTenants((current) => current.map((tenant) => (tenant.id === updated.id ? updated : tenant)));
      setTenantForm((current) => ({
        ...current,
        slug: updated.slug,
        allowed_origins: updated.allowed_origins,
      }));
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
      const result: TenantApiKeyCreateResponse = await tenantsApi.createApiKey(selectedTenantId, {
        name: newApiKey.name.trim(),
        expires_at: newApiKey.expires_at || null,
      });
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

  const handleRevokeApiKey = useCallback(
    async (keyId: string) => {
      if (!selectedTenantId) return;
      try {
        const revoked = await tenantsApi.revokeApiKey(selectedTenantId, keyId);
        setApiKeys((current) => current.map((item) => (item.id === revoked.id ? revoked : item)));
        toast.success("Đã thu hồi API key");
      } catch (error) {
        const message = error instanceof Error ? error.message : "Không thể thu hồi API key";
        toast.error(message);
      }
    },
    [selectedTenantId],
  );

  const handleCreateTenantUser = useCallback(async () => {
    if (!selectedTenantId || !tenantAdminUsername.trim() || !tenantAdminPassword.trim()) return;
    try {
      setSavingTenantUser(true);
      const created = await authApi.createUser({
        username: tenantAdminUsername.trim(),
        password: tenantAdminPassword,
        role: "tenant_admin",
        tenant_id: selectedTenantId,
      });
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
      setTenantUsers((current) => current.filter((user) => user.username !== username));
      toast.success("Đã xóa tenant admin");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Không thể xóa tenant admin";
      toast.error(message);
    }
  }, []);

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-6 p-6">
      <PageHeader
        title="Quản lý tenant"
        description="Chọn tenant để quản lý cấu hình, instruction, API key và tài khoản tenant admin."
        actions={
          <Button variant="outline" className="rounded-2xl" onClick={handleStartCreate}>
            <Plus className="mr-2 h-4 w-4" />
            Tạo tenant mới
          </Button>
        }
      />

      <div className="grid gap-6 xl:grid-cols-[300px_minmax(0,1fr)]">
        <Card className="rounded-3xl border-border/60 shadow-sm">
          <CardHeader>
            <CardTitle>Danh sách tenant</CardTitle>
            <CardDescription>Chọn tenant để xem chi tiết hoặc chuyển sang chế độ tạo mới.</CardDescription>
          </CardHeader>
          <CardContent>
            <ScrollArea className="max-h-[70vh] pr-3">
              <div className="flex flex-col gap-2">
                {loading ? (
                  <div className="text-sm text-muted-foreground">Đang tải tenant...</div>
                ) : tenants.length === 0 ? (
                  <div className="text-sm text-muted-foreground">Chưa có tenant nào.</div>
                ) : (
                  tenants.map((tenant) => (
                    <Button
                      key={tenant.id}
                      type="button"
                      variant="ghost"
                      onClick={() => handleSelectTenant(tenant.id)}
                      className={`h-auto w-full justify-start rounded-2xl border px-4 py-3 text-left ${
                        !isCreatingTenant && tenant.id === selectedTenantId
                          ? "border-primary/60 bg-primary/5 shadow-sm hover:bg-primary/5"
                          : "hover:bg-muted/70"
                      }`}
                    >
                      <div>
                        <div className="font-medium">{tenant.name}</div>
                        <div className="text-xs text-muted-foreground">{tenant.slug}</div>
                      </div>
                    </Button>
                  ))
                )}
              </div>
            </ScrollArea>
          </CardContent>
        </Card>

        <div className="flex flex-col gap-6">
          <Card className="rounded-3xl border-border/60 shadow-sm">
            <CardHeader>
              <CardTitle>{!isCreatingTenant && selectedTenant ? `Tenant: ${selectedTenant.name}` : "Tạo tenant mới"}</CardTitle>
              <CardDescription>Khối cấu hình lõi cho quota, rate limit và thông tin tenant.</CardDescription>
            </CardHeader>
            <CardContent>
              <FieldGroup className="grid gap-4 md:grid-cols-2">
                <Field>
                  <FieldContent>
                    <FieldLabel htmlFor="tenant_name">Tên tenant</FieldLabel>
                    <Input
                      id="tenant_name"
                      value={tenantForm.name || ""}
                      onChange={(event) => setTenantForm((current) => ({ ...current, name: event.target.value }))}
                    />
                  </FieldContent>
                </Field>

                <Field>
                  <FieldContent>
                    <FieldLabel htmlFor="tenant_slug">Slug</FieldLabel>
                    <Input
                      id="tenant_slug"
                      value={tenantForm.slug || ""}
                      onChange={(event) => setTenantForm((current) => ({ ...current, slug: event.target.value }))}
                      placeholder="Ví dụ: acme-corp"
                    />
                    <FieldDescription>
                      Slug là mã định danh ổn định của tenant, gần giống username hoặc public alias của công ty.
                    </FieldDescription>
                  </FieldContent>
                </Field>

                <Field className="md:col-span-2">
                  <FieldContent>
                    <FieldLabel htmlFor="tenant_description">Mô tả</FieldLabel>
                    <Textarea
                      id="tenant_description"
                      rows={3}
                      value={tenantForm.description || ""}
                      onChange={(event) => setTenantForm((current) => ({ ...current, description: event.target.value }))}
                    />
                  </FieldContent>
                </Field>

                <Field>
                  <FieldContent>
                    <FieldLabel htmlFor="monthly_request_quota">Quota request / tháng</FieldLabel>
                    <Input
                      id="monthly_request_quota"
                      type="number"
                      value={tenantForm.monthly_request_quota ?? 0}
                      onChange={(event) =>
                        setTenantForm((current) => ({
                          ...current,
                          monthly_request_quota: Number(event.target.value || 0),
                        }))
                      }
                    />
                  </FieldContent>
                </Field>

                <Field>
                  <FieldContent>
                    <FieldLabel htmlFor="monthly_token_quota">Quota token / tháng</FieldLabel>
                    <Input
                      id="monthly_token_quota"
                      type="number"
                      value={tenantForm.monthly_token_quota ?? 0}
                      onChange={(event) =>
                        setTenantForm((current) => ({
                          ...current,
                          monthly_token_quota: Number(event.target.value || 0),
                        }))
                      }
                    />
                  </FieldContent>
                </Field>

                <Field>
                  <FieldContent>
                    <FieldLabel htmlFor="rate_limit_rpm">Rate limit RPM</FieldLabel>
                    <Input
                      id="rate_limit_rpm"
                      type="number"
                      value={tenantForm.rate_limit_rpm ?? 60}
                      onChange={(event) =>
                        setTenantForm((current) => ({
                          ...current,
                          rate_limit_rpm: Number(event.target.value || 60),
                        }))
                      }
                    />
                  </FieldContent>
                </Field>

                <Field className="md:col-span-2">
                  <FieldContent>
                    <FieldLabel htmlFor="allowed_origins">Allowed origins</FieldLabel>
                    <Textarea
                      id="allowed_origins"
                      rows={4}
                      value={allowedOriginsDraft}
                      onChange={(event) => setAllowedOriginsDraft(event.target.value)}
                      placeholder={"https://erp.company-a.vn\nhttps://portal.company-a.vn"}
                    />
                    <FieldDescription>
                      Đây là danh sách domain được phép gọi widget hoặc API của tenant này. Mỗi dòng một origin.
                    </FieldDescription>
                  </FieldContent>
                </Field>

                {isCreatingTenant ? (
                  <>
                    <Field>
                      <FieldContent>
                        <FieldLabel htmlFor="tenant_admin_username">Tenant admin username</FieldLabel>
                        <Input
                          id="tenant_admin_username"
                          value={tenantAdminUsername}
                          onChange={(event) => setTenantAdminUsername(event.target.value)}
                          placeholder="Ví dụ: acme.admin"
                        />
                      </FieldContent>
                    </Field>

                    <Field>
                      <FieldContent>
                        <FieldLabel htmlFor="tenant_admin_password">Tenant admin password</FieldLabel>
                        <Input
                          id="tenant_admin_password"
                          type="password"
                          value={tenantAdminPassword}
                          onChange={(event) => setTenantAdminPassword(event.target.value)}
                          placeholder="Ít nhất 6 ký tự"
                        />
                      </FieldContent>
                    </Field>
                  </>
                ) : null}

                <div className="flex justify-end md:col-span-2">
                  {isCreatingTenant ? (
                    <Button className="rounded-2xl" onClick={handleCreateTenant} disabled={savingTenant}>
                      <Plus className="mr-2 h-4 w-4" />
                      {savingTenant ? "Đang tạo..." : "Tạo tenant"}
                    </Button>
                  ) : (
                    <Button className="rounded-2xl" onClick={handleUpdateTenant} disabled={savingTenant || !selectedTenantId}>
                      <Save className="mr-2 h-4 w-4" />
                      {savingTenant ? "Đang lưu..." : "Lưu tenant"}
                    </Button>
                  )}
                </div>
              </FieldGroup>
            </CardContent>
          </Card>

          {lastCreatedTenantAdmin ? (
            <Card className="rounded-3xl border-border/60 shadow-sm">
              <CardHeader>
                <CardTitle>Tài khoản tenant admin vừa tạo</CardTitle>
                <CardDescription>
                  Mật khẩu chỉ nên xem và copy ở thời điểm tạo. Hệ thống chỉ lưu hash nên không thể xem lại sau này.
                </CardDescription>
              </CardHeader>
              <CardContent className="grid gap-4 md:grid-cols-2">
                <div className="rounded-2xl border p-3">
                  <div className="text-xs text-muted-foreground">Username</div>
                  <div className="font-medium">{lastCreatedTenantAdmin.username}</div>
                </div>
                <div className="rounded-2xl border p-3">
                  <div className="text-xs text-muted-foreground">Mật khẩu</div>
                  <div className="font-medium">{lastCreatedTenantAdmin.password}</div>
                </div>
              </CardContent>
            </Card>
          ) : null}

          {!isCreatingTenant && selectedTenantId ? (
            <>
              <TenantSettingsForm
                mode="tenant"
                tenantId={selectedTenantId}
                description="Quản lý tên chatbot, lời chào và instruction riêng của tenant. Các giá trị này được nạp vào system prompt khi chatbot trả lời."
              />

              <Card className="rounded-3xl border-border/60 shadow-sm">
                <CardHeader>
                  <CardTitle>API key của tenant</CardTitle>
                  <CardDescription>Raw API key chỉ hiển thị đúng một lần sau khi tạo. Hãy copy và lưu an toàn.</CardDescription>
                </CardHeader>
                <CardContent className="flex flex-col gap-4">
                  <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_220px_auto]">
                    <Input
                      value={newApiKey.name || ""}
                      onChange={(event) => setNewApiKey({ ...newApiKey, name: event.target.value })}
                      placeholder="Tên key, ví dụ: ERP Production"
                    />
                    <Input
                      type="datetime-local"
                      value={newApiKey.expires_at || ""}
                      onChange={(event) => setNewApiKey({ ...newApiKey, expires_at: event.target.value || null })}
                    />
                    <Button className="rounded-2xl" onClick={handleCreateApiKey} disabled={savingApiKey}>
                      <KeyRound className="mr-2 h-4 w-4" />
                      {savingApiKey ? "Đang tạo..." : "Tạo API key"}
                    </Button>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Ô ngày giờ là hạn dùng của API key. Bỏ trống nếu muốn key dùng vô thời hạn cho đến khi bị thu hồi.
                  </p>

                  {rawApiKey ? (
                    <div className="rounded-2xl border border-dashed p-3 text-sm">
                      <div className="mb-2 font-medium">Raw API key mới tạo</div>
                      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                        <code className="overflow-x-auto rounded bg-muted px-3 py-2 text-xs">{rawApiKey}</code>
                        <Button
                          variant="outline"
                          className="rounded-2xl"
                          onClick={async () => {
                            await navigator.clipboard.writeText(rawApiKey);
                            toast.success("Đã copy API key");
                          }}
                        >
                          <Copy className="mr-2 h-4 w-4" />
                          Copy
                        </Button>
                      </div>
                    </div>
                  ) : null}

                  <Table className="min-w-[760px]">
                    <TableHeader>
                      <TableRow>
                        <TableHead className="pr-4 text-xs text-muted-foreground">Tên key</TableHead>
                        <TableHead className="pr-4 text-xs text-muted-foreground">Prefix</TableHead>
                        <TableHead className="pr-4 text-xs text-muted-foreground">Trạng thái</TableHead>
                        <TableHead className="pr-4 text-xs text-muted-foreground">Lần dùng cuối</TableHead>
                        <TableHead className="pr-4 text-xs text-muted-foreground">Hết hạn</TableHead>
                        <TableHead className="text-right text-xs text-muted-foreground">Thao tác</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {apiKeys.map((item) => (
                        <TableRow key={item.id}>
                          <TableCell className="pr-4">{item.name}</TableCell>
                          <TableCell className="pr-4 font-mono text-xs">{item.key_prefix}</TableCell>
                          <TableCell className="pr-4">{item.status}</TableCell>
                          <TableCell className="pr-4 text-sm text-muted-foreground">{formatDateTimeVN(item.last_used_at)}</TableCell>
                          <TableCell className="pr-4 text-sm text-muted-foreground">{formatDateTimeVN(item.expires_at)}</TableCell>
                          <TableCell className="text-right">
                            {item.status === "active" ? (
                              <Button size="sm" variant="destructive" className="rounded-2xl" onClick={() => handleRevokeApiKey(item.id)}>
                                <Trash2 className="mr-2 h-4 w-4" />
                                Thu hồi
                              </Button>
                            ) : (
                              <span className="text-xs text-muted-foreground">Đã thu hồi</span>
                            )}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>

              <Card className="rounded-3xl border-border/60 shadow-sm">
                <CardHeader>
                  <CardTitle>Tài khoản trong tenant</CardTitle>
                  <CardDescription>Platform admin có thể xem và quản lý ngay các tenant admin thuộc tenant đang chọn.</CardDescription>
                </CardHeader>
                <CardContent className="flex flex-col gap-4">
                  <p className="text-xs text-muted-foreground">
                    Mật khẩu không có nút “xem lại” vì backend chỉ lưu hash. Nếu cần, hãy tạo user mới với mật khẩu biết trước.
                  </p>

                  <FieldGroup className="grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]">
                    <Field>
                      <FieldContent>
                        <FieldLabel htmlFor="tenant_admin_username_inline">Username tenant admin</FieldLabel>
                        <Input
                          id="tenant_admin_username_inline"
                          value={tenantAdminUsername}
                          onChange={(event) => setTenantAdminUsername(event.target.value)}
                          placeholder="Username tenant admin"
                        />
                      </FieldContent>
                    </Field>

                    <Field>
                      <FieldContent>
                        <FieldLabel htmlFor="tenant_admin_password_inline">Mật khẩu tenant admin</FieldLabel>
                        <Input
                          id="tenant_admin_password_inline"
                          type="password"
                          value={tenantAdminPassword}
                          onChange={(event) => setTenantAdminPassword(event.target.value)}
                          placeholder="Mật khẩu tenant admin"
                        />
                      </FieldContent>
                    </Field>

                    <div className="flex items-end">
                      <Button className="rounded-2xl" onClick={handleCreateTenantUser} disabled={savingTenantUser}>
                        <Plus className="mr-2 h-4 w-4" />
                        {savingTenantUser ? "Đang tạo..." : "Tạo tenant admin"}
                      </Button>
                    </div>
                  </FieldGroup>

                  <Table className="min-w-[640px]">
                    <TableHeader>
                      <TableRow>
                        <TableHead className="pr-4 text-xs text-muted-foreground">Username</TableHead>
                        <TableHead className="pr-4 text-xs text-muted-foreground">Vai trò</TableHead>
                        <TableHead className="text-right text-xs text-muted-foreground">Thao tác</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {tenantUsers.map((user) => (
                        <TableRow key={user.id}>
                          <TableCell className="pr-4 font-medium">{user.username}</TableCell>
                          <TableCell className="pr-4 text-sm">{user.role}</TableCell>
                          <TableCell className="text-right">
                            <Button
                              size="sm"
                              variant="destructive"
                              className="rounded-2xl"
                              onClick={() => handleDeleteTenantUser(user.username)}
                            >
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
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
}
