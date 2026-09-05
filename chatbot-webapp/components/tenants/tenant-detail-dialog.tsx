"use client";

import { useCallback, useEffect, useState } from "react";
import {
  ArrowDownToLine,
  Building2,
  Check,
  Coins,
  Copy,
  FileText,
  Globe,
  Key,
  Link2,
  Loader2,
  MessageSquareCode,
  Plus,
  Save,
  ShieldAlert,
  ShieldCheck,
  Trash2,
  UserPlus,
  Users,
  Zap,
} from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { authApi, tenantsApi } from "@/lib/api-client";
import { TenantUpdateRequestSchema } from "@/lib/schemas";
import type { TenantApiKeyItem, TenantItem, TenantUpdateRequest, UserItem } from "@/types/api";

import { TenantSettingsForm } from "./tenant-settings-form";

// ==============================================================================
// Tab 1: Thông tin cơ bản & Quota
// ==============================================================================

interface GeneralTabProps {
  tenant: TenantItem;
  onUpdated: (updated: TenantItem) => void;
}

function stringifyAllowedOrigins(origins?: string[] | null): string {
  return (origins || []).join("\n");
}

function parseAllowedOriginsDraft(draft: string): string[] {
  return draft.split(/\r?\n/).map((item) => item.trim()).filter(Boolean);
}

function GeneralTab({ tenant, onUpdated }: GeneralTabProps) {
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState<TenantUpdateRequest>({
    name: tenant.name,
    slug: tenant.slug,
    description: tenant.description || "",
    rate_limit_rpm: tenant.rate_limit_rpm,
    monthly_request_quota: tenant.monthly_request_quota,
    monthly_token_quota: tenant.monthly_token_quota,
    allowed_origins: tenant.allowed_origins,
  });
  const [allowedOriginsDraft, setAllowedOriginsDraft] = useState(
    stringifyAllowedOrigins(tenant.allowed_origins)
  );

  useEffect(() => {
    setForm({
      name: tenant.name,
      slug: tenant.slug,
      description: tenant.description || "",
      rate_limit_rpm: tenant.rate_limit_rpm,
      monthly_request_quota: tenant.monthly_request_quota,
      monthly_token_quota: tenant.monthly_token_quota,
      allowed_origins: tenant.allowed_origins,
    });
    setAllowedOriginsDraft(stringifyAllowedOrigins(tenant.allowed_origins));
  }, [tenant]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setSaving(true);
      const payload: TenantUpdateRequest = {
        ...form,
        allowed_origins: parseAllowedOriginsDraft(allowedOriginsDraft),
      };

      const parsedPayload = TenantUpdateRequestSchema.safeParse(payload);
      if (!parsedPayload.success) {
        toast.error("Dữ liệu cập nhật tenant không hợp lệ");
        return;
      }

      const updated = await tenantsApi.update(tenant.id, parsedPayload.data);
      onUpdated(updated);
      toast.success("Đã cập nhật thông tin tenant");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Không thể cập nhật tenant";
      toast.error(message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <form id="general-tenant-form" onSubmit={handleSave} className="space-y-4">
      <FieldGroup className="space-y-3.5">
        <Field>
          <FieldLabel className="text-xs flex items-center gap-1.5 font-medium">
            <Building2 className="size-3.5 text-primary" />
            Tên tenant *
          </FieldLabel>
          <Input
            value={form.name}
            onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))}
            className="h-8 text-xs"
          />
        </Field>

        <Field>
          <FieldLabel className="text-xs flex items-center gap-1.5 font-medium">
            <Link2 className="size-3.5 text-primary" />
            Slug (Mã định danh)
          </FieldLabel>
          <Input
            value={form.slug || ""}
            onChange={(e) => setForm((prev) => ({ ...prev, slug: e.target.value }))}
            className="h-8 text-xs font-mono"
            placeholder="mau-company"
          />
        </Field>

        <Field>
          <FieldLabel className="text-xs flex items-center gap-1.5 font-medium">
            <FileText className="size-3.5 text-primary" />
            Mô tả
          </FieldLabel>
          <Textarea
            value={form.description || ""}
            onChange={(e) => setForm((prev) => ({ ...prev, description: e.target.value }))}
            className="min-h-[60px] text-xs resize-none"
            placeholder="Mô tả phạm vi hoạt động..."
          />
        </Field>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3 pt-1">
          <Field>
            <FieldLabel className="text-xs flex items-center gap-1.5 font-medium">
              <Zap className="size-3.5 text-amber-500" />
              Rate limit (RPM)
            </FieldLabel>
            <Input
              type="number"
              value={form.rate_limit_rpm ?? 60}
              onChange={(e) =>
                setForm((prev) => ({ ...prev, rate_limit_rpm: Number(e.target.value) }))
              }
              className="h-8 text-xs font-mono"
            />
          </Field>
          <Field>
            <FieldLabel className="text-xs flex items-center gap-1.5 font-medium">
              <ArrowDownToLine className="size-3.5 text-blue-500" />
              Req/tháng
            </FieldLabel>
            <Input
              type="number"
              value={form.monthly_request_quota ?? ""}
              onChange={(e) =>
                setForm((prev) => ({
                  ...prev,
                  monthly_request_quota: e.target.value ? Number(e.target.value) : undefined,
                }))
              }
              placeholder="0 = không giới hạn"
              className="h-8 text-xs font-mono"
            />
          </Field>
          <Field>
            <FieldLabel className="text-xs flex items-center gap-1.5 font-medium">
              <Coins className="size-3.5 text-emerald-500" />
              Token/tháng
            </FieldLabel>
            <Input
              type="number"
              value={form.monthly_token_quota ?? ""}
              onChange={(e) =>
                setForm((prev) => ({
                  ...prev,
                  monthly_token_quota: e.target.value ? Number(e.target.value) : undefined,
                }))
              }
              placeholder="0 = không giới hạn"
              className="h-8 text-xs font-mono"
            />
          </Field>
        </div>

        <Field className="pt-1">
          <FieldLabel className="text-xs flex items-center gap-1.5 font-medium">
            <Globe className="size-3.5 text-indigo-500" />
            Tên miền CORS
          </FieldLabel>
          <Textarea
            value={allowedOriginsDraft}
            onChange={(e) => setAllowedOriginsDraft(e.target.value)}
            placeholder={"https://app.example.com\nhttps://portal.example.com"}
            className="min-h-[60px] text-xs font-mono resize-none"
          />
        </Field>
      </FieldGroup>

      <div className="flex justify-end pt-3 pb-1 border-t">
        <Button size="sm" type="submit" disabled={saving} className="h-8 px-4 text-xs gap-1.5">
          {saving ? (
            <Loader2 className="size-3.5 animate-spin" />
          ) : (
            <Save className="size-3.5" />
          )}
          Lưu
        </Button>
      </div>
    </form>
  );
}

// ==============================================================================
// Tab 2: Quản lý Khóa API (API Keys)
// ==============================================================================

interface ApiKeysTabProps {
  tenantId: string;
}

function ApiKeysTab({ tenantId }: ApiKeysTabProps) {
  const [keys, setKeys] = useState<TenantApiKeyItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [revokingId, setRevokingId] = useState<string | null>(null);
  const [newKeyName, setNewKeyName] = useState("");
  const [rawApiKey, setRawApiKey] = useState("");
  const [copied, setCopied] = useState(false);

  const loadKeys = useCallback(async () => {
    try {
      setLoading(true);
      const data = await tenantsApi.listApiKeys(tenantId);
      setKeys(data);
    } catch {
      toast.error("Không thể tải danh sách API key");
    } finally {
      setLoading(false);
    }
  }, [tenantId]);

  useEffect(() => {
    void loadKeys();
  }, [loadKeys]);

  const handleCreateKey = async (e: React.FormEvent) => {
    e.preventDefault();
    const name = newKeyName.trim() || "Website Widget Key";
    try {
      setCreating(true);
      const created = await tenantsApi.createApiKey(tenantId, { name });
      setRawApiKey(created.raw_api_key || "");
      setNewKeyName("");
      toast.success("Đã tạo API key mới thành công");
      await loadKeys();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Không thể tạo API key";
      toast.error(message);
    } finally {
      setCreating(false);
    }
  };

  const handleRevokeKey = async (keyId: string) => {
    if (!confirm("Bạn có chắc muốn thu hồi API key này? Hành động này không thể hoàn tác.")) {
      return;
    }
    try {
      setRevokingId(keyId);
      await tenantsApi.revokeApiKey(tenantId, keyId);
      toast.success("Đã thu hồi API key");
      await loadKeys();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Không thể thu hồi API key";
      toast.error(message);
    } finally {
      setRevokingId(null);
    }
  };

  const copyRawKey = () => {
    if (!rawApiKey) return;
    navigator.clipboard.writeText(rawApiKey);
    setCopied(true);
    toast.success("Đã sao chép API key vào clipboard");
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-sm font-medium">Khóa API Tích Hợp</h3>
        <p className="text-xs text-muted-foreground mt-0.5">
          Quản lý các khóa truy cập (API Keys) dùng để nhúng widget chatbot vào website hoặc tích hợp qua backend API.
        </p>
      </div>

      {rawApiKey && (
        <Card className="border-emerald-500/30 bg-emerald-500/10 p-3.5 space-y-2">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-emerald-600 dark:text-emerald-400">
            <ShieldAlert className="size-3.5 shrink-0" />
            <span>Khóa bí mật vừa tạo (Chỉ hiển thị 1 lần duy nhất):</span>
          </div>
          <div className="flex items-center gap-2">
            <code className="flex-1 rounded-md bg-background px-2.5 py-1.5 text-xs font-mono select-all break-all border">
              {rawApiKey}
            </code>
            <Button size="sm" variant="outline" onClick={copyRawKey} className="shrink-0 h-8 gap-1.5 text-xs">
              {copied ? <Check className="size-3.5 text-emerald-500" /> : <Copy className="size-3.5" />}
              <span>{copied ? "Đã copy" : "Copy"}</span>
            </Button>
          </div>
        </Card>
      )}

      <form onSubmit={handleCreateKey} className="flex gap-2">
        <Input
          placeholder="Tên định danh (vd: Website Widget, ERP Integration...)"
          value={newKeyName}
          onChange={(e) => setNewKeyName(e.target.value)}
          className="h-8 text-xs flex-1"
        />
        <Button size="sm" type="submit" disabled={creating} className="h-8 text-xs shrink-0">
          {creating ? (
            <Loader2 className="mr-1.5 size-3.5 animate-spin" />
          ) : (
            <Plus className="mr-1.5 size-3.5" />
          )}
          Tạo khóa mới
        </Button>
      </form>

      <div className="space-y-3">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Danh sách khóa đã cấp ({keys.length})
        </h4>

        {loading ? (
          <div className="space-y-2">
            <Skeleton className="h-12 w-full rounded-xl" />
            <Skeleton className="h-12 w-full rounded-xl" />
          </div>
        ) : keys.length === 0 ? (
          <Empty className="border border-dashed rounded-xl py-8">
            <EmptyMedia variant="icon">
              <Key className="size-5 text-muted-foreground" />
            </EmptyMedia>
            <EmptyHeader>
              <EmptyTitle className="text-xs">Chưa có API key nào</EmptyTitle>
              <EmptyDescription className="text-xs">
                Tạo một API key ở trên để bắt đầu kết nối chatbot với website hoặc hệ thống khác.
              </EmptyDescription>
            </EmptyHeader>
          </Empty>
        ) : (
          <div className="space-y-2">
            {keys.map((k) => (
              <div
                key={k.id}
                className="flex items-center justify-between rounded-xl border p-3 text-xs bg-muted/20"
              >
                <div className="space-y-0.5">
                  <div className="font-medium text-foreground">{k.name}</div>
                  <div className="font-mono text-[11px] text-muted-foreground">
                    Tiền tố: {k.key_prefix}...
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <Badge
                    variant={k.status === "active" ? "default" : "secondary"}
                    className="text-[10px] font-normal uppercase"
                  >
                    {k.status}
                  </Badge>

                  {k.status === "active" && (
                    <Button
                      size="sm"
                      variant="destructive"
                      className="h-7 text-xs"
                      disabled={revokingId === k.id}
                      onClick={() => handleRevokeKey(k.id)}
                    >
                      {revokingId === k.id ? "Đang thu hồi..." : "Thu hồi"}
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ==============================================================================
// Tab 3: Quản lý Quản trị viên Tenant (Admins)
// ==============================================================================

interface AdminsTabProps {
  tenantId: string;
  initialAdminAccount?: { username: string; password: string } | null;
}

function AdminsTab({ tenantId, initialAdminAccount }: AdminsTabProps) {
  const [users, setUsers] = useState<UserItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [deletingUsername, setDeletingUsername] = useState<string | null>(null);

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [lastCreated, setLastCreated] = useState<{ username: string; password: string } | null>(
    initialAdminAccount || null
  );

  const loadUsers = useCallback(async () => {
    try {
      setLoading(true);
      const allUsers = await authApi.getUsers();
      setUsers(allUsers.filter((u) => u.tenant_id === tenantId));
    } catch {
      toast.error("Không thể tải danh sách tài khoản tenant");
    } finally {
      setLoading(false);
    }
  }, [tenantId]);

  useEffect(() => {
    void loadUsers();
  }, [loadUsers]);

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password) {
      toast.error("Vui lòng nhập đầy đủ tên đăng nhập và mật khẩu");
      return;
    }

    try {
      setCreating(true);
      await authApi.createUser({
        username: username.trim(),
        password,
        role: "tenant_admin",
        tenant_id: tenantId,
      });

      setLastCreated({ username: username.trim(), password });
      setUsername("");
      setPassword("");
      toast.success("Đã tạo tài khoản Quản trị viên Tenant thành công");
      await loadUsers();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Không thể tạo tài khoản";
      toast.error(message);
    } finally {
      setCreating(false);
    }
  };

  const handleDeleteUser = async (userUsername: string) => {
    if (!confirm(`Bạn có chắc muốn xóa tài khoản "${userUsername}" không?`)) {
      return;
    }

    try {
      setDeletingUsername(userUsername);
      await authApi.deleteUser(userUsername);
      toast.success(`Đã xóa tài khoản "${userUsername}"`);
      await loadUsers();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Không thể xóa tài khoản";
      toast.error(message);
    } finally {
      setDeletingUsername(null);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-sm font-medium">Quản Trị Viên Tenant</h3>
        <p className="text-xs text-muted-foreground mt-0.5">
          Quản lý các tài khoản có quyền đăng nhập vào dashboard để quản lý tài liệu, câu hỏi FAQ và cấu hình của tenant này.
        </p>
      </div>

      {lastCreated && (
        <Card className="border-emerald-500/30 bg-emerald-500/10 p-3.5 space-y-1.5">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-emerald-600 dark:text-emerald-400">
            <ShieldCheck className="size-3.5 shrink-0" />
            <span>Tài khoản Quản trị viên vừa khởi tạo:</span>
          </div>
          <div className="text-xs font-mono">
            <span>Username: </span>
            <strong className="text-foreground select-all">{lastCreated.username}</strong>
            <span className="mx-2 text-muted-foreground">|</span>
            <span>Password: </span>
            <strong className="text-foreground select-all">{lastCreated.password}</strong>
          </div>
        </Card>
      )}

      <form onSubmit={handleCreateUser} className="space-y-4 rounded-xl border p-4 bg-muted/20">
        <div className="flex items-center gap-2">
          <UserPlus className="size-4 text-primary" />
          <h4 className="text-xs font-semibold uppercase tracking-wider text-foreground">
            Thêm Quản trị viên mới
          </h4>
        </div>

        <FieldGroup className="grid gap-3 sm:grid-cols-2">
          <Field>
            <FieldLabel className="text-xs">Tên đăng nhập *</FieldLabel>
            <Input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="admin_company"
              className="h-8 text-xs"
            />
          </Field>

          <Field>
            <FieldLabel className="text-xs">Mật khẩu ban đầu *</FieldLabel>
            <Input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className="h-8 text-xs"
            />
          </Field>
        </FieldGroup>

        <div className="flex justify-end pt-1">
          <Button size="sm" type="submit" disabled={creating} className="h-8 text-xs">
            {creating ? (
              <Loader2 className="mr-1.5 size-3.5 animate-spin" />
            ) : (
              <Plus className="mr-1.5 size-3.5" />
            )}
            Tạo tài khoản Admin
          </Button>
        </div>
      </form>

      <div className="space-y-3">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Danh sách tài khoản trực thuộc ({users.length})
        </h4>

        {loading ? (
          <div className="space-y-2">
            <Skeleton className="h-12 w-full rounded-xl" />
          </div>
        ) : users.length === 0 ? (
          <Empty className="border border-dashed rounded-xl py-8">
            <EmptyMedia variant="icon">
              <Users className="size-5 text-muted-foreground" />
            </EmptyMedia>
            <EmptyHeader>
              <EmptyTitle className="text-xs">Chưa có tài khoản quản trị nào</EmptyTitle>
              <EmptyDescription className="text-xs">
                Sử dụng form bên trên để tạo tài khoản đăng nhập cho quản trị viên của tenant này.
              </EmptyDescription>
            </EmptyHeader>
          </Empty>
        ) : (
          <div className="space-y-2">
            {users.map((u) => (
              <div
                key={u.id}
                className="flex items-center justify-between rounded-xl border p-3 text-xs bg-muted/20"
              >
                <div className="space-y-0.5">
                  <div className="font-medium text-foreground">{u.username}</div>
                  <div className="text-[11px] text-muted-foreground">
                    Quản trị viên trực thuộc
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <Badge variant="outline" className="text-[10px] font-normal">
                    {u.role === "tenant_admin" ? "Quản trị viên" : u.role}
                  </Badge>

                  <Button
                    size="icon"
                    variant="ghost"
                    className="h-7 w-7 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                    disabled={deletingUsername === u.username}
                    onClick={() => handleDeleteUser(u.username)}
                    title="Xóa tài khoản"
                  >
                    <Trash2 className="size-3.5" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ==============================================================================
// Master Component: TenantDetailDialog (Giao diện 2 cột phong cách ChatGPT Settings)
// ==============================================================================

type DetailTab = "general" | "prompt" | "keys" | "admins";

export interface TenantDetailDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  tenantId: string | null;
  initialAdminAccount?: { username: string; password: string } | null;
  onTenantUpdated: (updated: TenantItem) => void;
}

export function TenantDetailDialog({
  open,
  onOpenChange,
  tenantId,
  initialAdminAccount,
  onTenantUpdated,
}: TenantDetailDialogProps) {
  const [activeTab, setActiveTab] = useState<DetailTab>("general");
  const [tenant, setTenant] = useState<TenantItem | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (open && tenantId) {
      setLoading(true);
      tenantsApi
        .get(tenantId)
        .then(setTenant)
        .catch(() => {
          setTenant(null);
        })
        .finally(() => setLoading(false));
    } else if (!open) {
      setActiveTab("general");
    }
  }, [open, tenantId]);

  const navItems = [
    { id: "general" as DetailTab, label: "Thông tin & Quota", icon: Building2 },
    { id: "prompt" as DetailTab, label: "Cấu hình AI Prompt", icon: MessageSquareCode },
    { id: "keys" as DetailTab, label: "Khóa API", icon: Key },
    { id: "admins" as DetailTab, label: "Quản trị viên", icon: Users },
  ];

  const activeTitle = navItems.find((t) => t.id === activeTab)?.label || "Cấu hình";

  const handleTenantUpdated = (updated: TenantItem) => {
    setTenant(updated);
    onTenantUpdated(updated);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-4xl h-[620px] max-h-[90vh] p-0 overflow-hidden gap-0 flex flex-row rounded-2xl border bg-background shadow-2xl">
        <DialogTitle className="sr-only">Cấu hình Tenant</DialogTitle>

        {/* ── CỘT TRÁI: SIDEBAR ĐIỀU HƯỚNG TABS ── */}
        <div className="w-56 sm:w-60 bg-muted/30 border-r flex flex-col shrink-0">
          <div className="p-3.5 space-y-1 border-b">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              Tenant
            </div>
            <div className="font-semibold text-sm text-foreground truncate">
              {tenant?.name || "Đang tải..."}
            </div>
            {tenant?.slug && (
              <div className="font-mono text-[10px] text-muted-foreground truncate">
                slug: {tenant.slug}
              </div>
            )}
          </div>

          <ScrollArea className="flex-1 p-2">
            <div className="flex flex-col gap-1">
              {navItems.map((item) => {
                const Icon = item.icon;
                const isActive = activeTab === item.id;
                return (
                  <Button
                    key={item.id}
                    variant={isActive ? "secondary" : "ghost"}
                    size="sm"
                    onClick={() => setActiveTab(item.id)}
                    className="w-full justify-start gap-2.5 font-normal h-8 text-xs"
                  >
                    <Icon className="size-3.5 shrink-0 text-muted-foreground" />
                    <span className="truncate">{item.label}</span>
                  </Button>
                );
              })}
            </div>
          </ScrollArea>

          <Separator />

          <div className="p-3 flex items-center justify-between text-xs text-muted-foreground">
            <span className="truncate max-w-[130px] font-mono text-[10px]">
              {tenant?.id ? tenant.id.slice(0, 8) + "..." : ""}
            </span>
            <Badge
              variant={tenant?.status === "active" ? "default" : "secondary"}
              className="text-[10px] shrink-0 font-normal uppercase"
            >
              {tenant?.status || "—"}
            </Badge>
          </div>
        </div>

        {/* ── CỘT PHẢI: VÙNG NỘI DUNG CHI TIẾT THEO TAB ── */}
        <div className="flex-1 flex flex-col min-h-0 min-w-0 overflow-hidden bg-background">
          <DialogHeader className="px-6 py-3.5 border-b shrink-0 flex flex-row items-center gap-2 space-y-0">
            {(() => {
              const ActiveIcon = navItems.find((t) => t.id === activeTab)?.icon || Building2;
              return <ActiveIcon className="size-4 text-primary" />;
            })()}
            <DialogTitle className="text-base font-semibold">{activeTitle}</DialogTitle>
          </DialogHeader>

          <div className="flex-1 min-h-0 overflow-y-auto px-6 py-4">
            <div className="max-w-2xl space-y-4">
              {loading ? (
                <div className="space-y-4 py-4">
                  <Skeleton className="h-6 w-40 rounded-lg" />
                  <Skeleton className="h-24 w-full rounded-xl" />
                  <Skeleton className="h-24 w-full rounded-xl" />
                </div>
              ) : tenant && tenantId ? (
                <>
                  {activeTab === "general" && (
                    <GeneralTab tenant={tenant} onUpdated={handleTenantUpdated} />
                  )}

                  {activeTab === "prompt" && (
                    <div className="space-y-4">
                      <TenantSettingsForm mode="tenant" tenantId={tenantId} noCard={true} />
                    </div>
                  )}

                  {activeTab === "keys" && <ApiKeysTab tenantId={tenantId} />}

                  {activeTab === "admins" && (
                    <AdminsTab
                      tenantId={tenantId}
                      initialAdminAccount={initialAdminAccount}
                    />
                  )}
                </>
              ) : (
                <div className="py-12 text-center text-xs text-muted-foreground">
                  Không thể tìm thấy thông tin tenant này.
                </div>
              )}
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
