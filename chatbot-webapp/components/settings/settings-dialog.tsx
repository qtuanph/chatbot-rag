"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { useTheme } from "next-themes";
import {
  Building2,
  CreditCard,
  Laptop,
  Loader2,
  Moon,
  Search,
  Server,
  Settings2,
  Shield,
  ShieldCheck,
  Sun,
  User,
} from "lucide-react";
import { toast } from "sonner";
import { UserSettingsForm } from "@/components/auth/user-settings-form";
import { TenantSettingsForm } from "@/components/tenants/tenant-settings-form";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { Input } from "@/components/ui/input";
import {
  Item,
  ItemActions,
  ItemContent,
  ItemDescription,
  ItemGroup,
  ItemTitle,
} from "@/components/ui/item";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { settingsApi } from "@/lib/api-client";
import { formatRoleLabel } from "@/lib/format";
import type { BillingSettings } from "@/types/api";
import { useSettingsDialog, type SettingsTab } from "./settings-dialog-context";

export function SettingsDialog() {
  const { open, setOpen, activeTab, setActiveTab } = useSettingsDialog();
  const { data: session } = useSession();
  const { theme, setTheme } = useTheme();

  const [searchQuery, setSearchQuery] = useState("");
  const isPlatformAdmin = session?.role === "platform_admin";
  const isTenantAdmin = session?.role === "tenant_admin";

  // Billing & Quota state (Platform Admin)
  const [billingData, setBillingData] = useState<BillingSettings | null>(null);
  const [billingLoading, setBillingLoading] = useState(false);
  const [billingSaving, setBillingSaving] = useState(false);

  useEffect(() => {
    if (open && isPlatformAdmin && !billingData) {
      setBillingLoading(true);
      settingsApi
        .getBilling()
        .then(setBillingData)
        .catch(() => {
          toast.error("Không thể tải cấu hình billing");
        })
        .finally(() => setBillingLoading(false));
    }
  }, [open, isPlatformAdmin, billingData]);

  const saveBilling = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!billingData) return;

    if (
      billingData.quota_cost_alert_pct_warn > billingData.quota_cost_alert_pct_alert ||
      billingData.quota_cost_alert_pct_alert > billingData.quota_cost_alert_pct_cutoff
    ) {
      toast.error("Lỗi: Warn <= Alert <= Cutoff");
      return;
    }

    setBillingSaving(true);
    try {
      const updated = await settingsApi.updateBilling(billingData);
      setBillingData(updated);
      toast.success("Đã lưu cấu hình platform billing & quota");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Không thể lưu cấu hình");
    } finally {
      setBillingSaving(false);
    }
  };

  const handleBillingChange = (field: keyof BillingSettings, val: string) => {
    setBillingData((prev) => {
      if (!prev) return null;
      let parsed = parseInt(val) || 0;
      if (field === "quota_user_rate_per_min") parsed = Math.max(1, Math.min(1000, parseInt(val) || 1));
      return { ...prev, [field]: parsed };
    });
  };

  const navItems = [
    { id: "general" as SettingsTab, label: "Chung", icon: Settings2 },
    { id: "account" as SettingsTab, label: "Tài khoản", icon: User },
    ...(isPlatformAdmin
      ? [{ id: "system" as SettingsTab, label: "Hệ thống & Quota", icon: Server }]
      : isTenantAdmin
      ? [{ id: "system" as SettingsTab, label: "Hạn ngạch Tenant", icon: Building2 }]
      : []),
    { id: "security" as SettingsTab, label: "Bảo mật", icon: ShieldCheck },
  ];

  const filteredNavItems = navItems.filter((item) =>
    item.label.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const activeTitle = navItems.find((t) => t.id === activeTab)?.label || "Cài đặt";

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent
        className="sm:max-w-4xl h-[580px] max-h-[90vh] p-0 overflow-hidden gap-0 flex flex-row rounded-2xl border bg-background shadow-2xl"
      >
        <DialogTitle className="sr-only">Cài đặt ứng dụng</DialogTitle>

        {/* ── CỘT TRÁI: SIDEBAR ĐIỀU HƯỚNG (100% SHADCN COMPONENTS) ── */}
        <div className="w-56 sm:w-60 bg-muted/30 border-r flex flex-col shrink-0">
          {/* Thanh tìm kiếm */}
          <div className="p-3">
            <div className="relative">
              <Search className="absolute left-2.5 top-2.5 size-3.5 text-muted-foreground pointer-events-none" />
              <Input
                placeholder="Tìm kiếm cài đặt..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="h-8 pl-8 text-xs bg-background shadow-none"
              />
            </div>
          </div>

          <Separator />

          {/* Danh sách tab navigation */}
          <ScrollArea className="flex-1 p-2">
            <div className="flex flex-col gap-1">
              {filteredNavItems.map((item) => {
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

          {/* Chân trang thông tin user */}
          <div className="p-3 flex items-center justify-between text-xs text-muted-foreground">
            <span className="truncate max-w-[130px] font-medium text-foreground">{session?.user?.name}</span>
            <Badge variant="outline" className="text-[10px] shrink-0 font-normal">
              {formatRoleLabel(session?.role)}
            </Badge>
          </div>
        </div>

        {/* ── CỘT PHẢI: NỘI DUNG CHI TIẾT (100% SHADCN COMPONENTS) ── */}
        <div className="flex-1 flex flex-col min-w-0 bg-background">
          {/* Header với DialogHeader và DialogTitle chuẩn */}
          <DialogHeader className="px-6 py-4 border-b shrink-0 flex flex-row items-center justify-between space-y-0">
            <DialogTitle className="text-base font-semibold">{activeTitle}</DialogTitle>
          </DialogHeader>

          {/* Vùng nội dung cuộn bằng ScrollArea */}
          <ScrollArea className="flex-1 p-6">
            <div className="max-w-xl space-y-6">
              {/* ── TAB 1: CHUNG ── */}
              {activeTab === "general" && (
                <div className="space-y-6">
                  {/* Card giới thiệu */}
                  <Card className="bg-muted/40 border shadow-none">
                    <CardHeader className="p-4 space-y-1">
                      <div className="flex items-center gap-2">
                        <Shield className="size-4 text-primary" />
                        <CardTitle className="text-sm font-medium">Cài đặt ứng dụng</CardTitle>
                      </div>
                      <CardDescription className="text-xs leading-relaxed">
                        Tùy chỉnh chủ đề hiển thị, ngôn ngữ và giao diện làm việc trên toàn bộ hệ thống chatbot.
                      </CardDescription>
                    </CardHeader>
                  </Card>

                  {/* Danh sách cài đặt dùng Item & ItemGroup chuẩn Shadcn */}
                  <ItemGroup className="gap-0 divide-y border-y">
                    <Item variant="default" className="justify-between px-0 py-3.5 border-none rounded-none">
                      <ItemContent className="gap-0.5">
                        <ItemTitle className="text-sm font-medium">Giao diện</ItemTitle>
                        <ItemDescription className="text-xs text-muted-foreground">
                          Chọn chế độ màu sáng hoặc tối
                        </ItemDescription>
                      </ItemContent>
                      <ItemActions>
                        <Select
                          value={theme || "system"}
                          onValueChange={(val) => {
                            if (val) setTheme(val);
                          }}
                        >
                          <SelectTrigger className="w-40 h-8 text-xs">
                            <SelectValue>
                              {(val) => {
                                if (val === "system") {
                                  return (
                                    <span className="flex items-center gap-1.5">
                                      <Laptop className="size-3.5 text-muted-foreground" />
                                      <span>Hệ thống</span>
                                    </span>
                                  );
                                }
                                if (val === "light") {
                                  return (
                                    <span className="flex items-center gap-1.5">
                                      <Sun className="size-3.5 text-amber-500" />
                                      <span>Sáng</span>
                                    </span>
                                  );
                                }
                                if (val === "dark") {
                                  return (
                                    <span className="flex items-center gap-1.5">
                                      <Moon className="size-3.5 text-blue-400" />
                                      <span>Tối</span>
                                    </span>
                                  );
                                }
                                return val;
                              }}
                            </SelectValue>
                          </SelectTrigger>
                          <SelectContent alignItemWithTrigger={false} align="end" side="bottom" sideOffset={4}>
                            <SelectItem value="system">
                              <div className="flex items-center gap-2">
                                <Laptop className="size-3.5 text-muted-foreground" />
                                <span>Hệ thống</span>
                              </div>
                            </SelectItem>
                            <SelectItem value="light">
                              <div className="flex items-center gap-2">
                                <Sun className="size-3.5 text-amber-500" />
                                <span>Sáng</span>
                              </div>
                            </SelectItem>
                            <SelectItem value="dark">
                              <div className="flex items-center gap-2">
                                <Moon className="size-3.5 text-blue-400" />
                                <span>Tối</span>
                              </div>
                            </SelectItem>
                          </SelectContent>
                        </Select>
                      </ItemActions>
                    </Item>

                    <Item variant="default" className="justify-between px-0 py-3.5 border-none rounded-none">
                      <ItemContent className="gap-0.5">
                        <ItemTitle className="text-sm font-medium">Độ tương phản</ItemTitle>
                        <ItemDescription className="text-xs text-muted-foreground">
                          Tối ưu độ rõ nét các đường viền
                        </ItemDescription>
                      </ItemContent>
                      <ItemActions>
                        <Select defaultValue="system">
                          <SelectTrigger className="w-40 h-8 text-xs">
                            <SelectValue>
                              {(val) => (val === "high" ? "Tương phản cao" : "Hệ thống")}
                            </SelectValue>
                          </SelectTrigger>
                          <SelectContent alignItemWithTrigger={false} align="end" side="bottom" sideOffset={4}>
                            <SelectItem value="system">Hệ thống</SelectItem>
                            <SelectItem value="high">Tương phản cao</SelectItem>
                          </SelectContent>
                        </Select>
                      </ItemActions>
                    </Item>

                    <Item variant="default" className="justify-between px-0 py-3.5 border-none rounded-none">
                      <ItemContent className="gap-0.5">
                        <ItemTitle className="text-sm font-medium">Ngôn ngữ</ItemTitle>
                        <ItemDescription className="text-xs text-muted-foreground">
                          Ngôn ngữ hiển thị bảng điều khiển
                        </ItemDescription>
                      </ItemContent>
                      <ItemActions>
                        <Select defaultValue="vi">
                          <SelectTrigger className="w-40 h-8 text-xs">
                            <SelectValue>
                              {(val) => (val === "en" ? "English" : "Tiếng Việt")}
                            </SelectValue>
                          </SelectTrigger>
                          <SelectContent alignItemWithTrigger={false} align="end" side="bottom" sideOffset={4}>
                            <SelectItem value="vi">Tiếng Việt</SelectItem>
                            <SelectItem value="en">English</SelectItem>
                          </SelectContent>
                        </Select>
                      </ItemActions>
                    </Item>
                  </ItemGroup>
                </div>
              )}

              {/* ── TAB 2: TÀI KHOẢN ── */}
              {activeTab === "account" && (
                <ItemGroup className="gap-0 divide-y border-y">
                  <Item variant="default" className="justify-between px-0 py-3.5 border-none rounded-none">
                    <ItemTitle className="text-xs text-muted-foreground">Tên đăng nhập</ItemTitle>
                    <ItemActions>
                      <span className="text-xs font-medium">{session?.user?.name || "—"}</span>
                    </ItemActions>
                  </Item>
                  <Item variant="default" className="justify-between px-0 py-3.5 border-none rounded-none">
                    <ItemTitle className="text-xs text-muted-foreground">Email</ItemTitle>
                    <ItemActions>
                      <span className="text-xs font-mono font-medium">{session?.user?.email || "—"}</span>
                    </ItemActions>
                  </Item>
                  <Item variant="default" className="justify-between px-0 py-3.5 border-none rounded-none">
                    <ItemTitle className="text-xs text-muted-foreground">Vai trò</ItemTitle>
                    <ItemActions>
                      <Badge variant="secondary" className="text-xs font-normal">
                        {formatRoleLabel(session?.role)}
                      </Badge>
                    </ItemActions>
                  </Item>
                  <Item variant="default" className="justify-between px-0 py-3.5 border-none rounded-none">
                    <ItemTitle className="text-xs text-muted-foreground">Tenant ID</ItemTitle>
                    <ItemActions>
                      <span className="text-xs font-mono text-muted-foreground">
                        {session?.tenantId || "Toàn hệ thống (Platform)"}
                      </span>
                    </ItemActions>
                  </Item>
                </ItemGroup>
              )}

              {/* ── TAB 3: HỆ THỐNG & QUOTA ── */}
              {activeTab === "system" && (
                <div>
                  {isPlatformAdmin ? (
                    <form onSubmit={saveBilling} className="space-y-6">
                      {billingLoading ? (
                        <div className="space-y-4 py-4">
                          <Skeleton className="h-6 w-40 rounded-lg" />
                          <Skeleton className="h-16 w-full rounded-xl" />
                          <Skeleton className="h-16 w-full rounded-xl" />
                        </div>
                      ) : billingData ? (
                        <div className="space-y-6">
                          <div className="space-y-3">
                            <h4 className="text-xs font-semibold text-foreground uppercase tracking-wider">
                              Đơn Giá Token LLM (₫ / 1M)
                            </h4>
                            <div className="grid gap-4 sm:grid-cols-2">
                              <div className="space-y-1.5">
                                <Label className="text-xs">Giá Token Đầu Vào</Label>
                                <Input
                                  type="number"
                                  className="h-8 text-xs font-mono"
                                  value={billingData.ai_input_price_vnd_per_1m}
                                  onChange={(e) =>
                                    handleBillingChange("ai_input_price_vnd_per_1m", e.target.value)
                                  }
                                />
                              </div>
                              <div className="space-y-1.5">
                                <Label className="text-xs">Giá Token Đầu Ra</Label>
                                <Input
                                  type="number"
                                  className="h-8 text-xs font-mono"
                                  value={billingData.ai_output_price_vnd_per_1m}
                                  onChange={(e) =>
                                    handleBillingChange("ai_output_price_vnd_per_1m", e.target.value)
                                  }
                                />
                              </div>
                            </div>
                          </div>

                          <Separator />

                          <div className="space-y-3">
                            <h4 className="text-xs font-semibold text-foreground uppercase tracking-wider">
                              Giới Hạn &amp; Ngân Sách
                            </h4>
                            <div className="grid gap-4 sm:grid-cols-2">
                              <div className="space-y-1.5">
                                <Label className="text-xs">Hard Budget (₫/tháng)</Label>
                                <Input
                                  type="number"
                                  className="h-8 text-xs font-mono"
                                  value={billingData.quota_hard_budget_vnd}
                                  onChange={(e) =>
                                    handleBillingChange("quota_hard_budget_vnd", e.target.value)
                                  }
                                />
                              </div>
                              <div className="space-y-1.5">
                                <Label className="text-xs">Rate limit (câu/phút)</Label>
                                <Input
                                  type="number"
                                  min="1"
                                  max="1000"
                                  className="h-8 text-xs font-mono"
                                  value={billingData.quota_user_rate_per_min}
                                  onChange={(e) =>
                                    handleBillingChange("quota_user_rate_per_min", e.target.value)
                                  }
                                />
                              </div>
                            </div>
                          </div>

                          <Separator />

                          <div className="space-y-3">
                            <h4 className="text-xs font-semibold text-foreground uppercase tracking-wider">
                              Ngưỡng Cảnh Báo Ngân Sách (%)
                            </h4>
                            <div className="grid gap-4 grid-cols-3">
                              <div className="space-y-1.5">
                                <Label className="text-xs">Cảnh báo sớm</Label>
                                <Input
                                  type="number"
                                  min="1"
                                  max="99"
                                  className="h-8 text-xs font-mono"
                                  value={billingData.quota_cost_alert_pct_warn}
                                  onChange={(e) =>
                                    handleBillingChange("quota_cost_alert_pct_warn", e.target.value)
                                  }
                                />
                              </div>
                              <div className="space-y-1.5">
                                <Label className="text-xs">Mức độ cao</Label>
                                <Input
                                  type="number"
                                  min="1"
                                  max="99"
                                  className="h-8 text-xs font-mono"
                                  value={billingData.quota_cost_alert_pct_alert}
                                  onChange={(e) =>
                                    handleBillingChange("quota_cost_alert_pct_alert", e.target.value)
                                  }
                                />
                              </div>
                              <div className="space-y-1.5">
                                <Label className="text-xs">Ngắt dịch vụ</Label>
                                <Input
                                  type="number"
                                  min="1"
                                  max="100"
                                  className="h-8 text-xs font-mono"
                                  value={billingData.quota_cost_alert_pct_cutoff}
                                  onChange={(e) =>
                                    handleBillingChange("quota_cost_alert_pct_cutoff", e.target.value)
                                  }
                                />
                              </div>
                            </div>
                          </div>

                          <div className="flex justify-end pt-2">
                            <Button size="sm" type="submit" disabled={billingSaving}>
                              {billingSaving && <Loader2 className="mr-2 size-3.5 animate-spin" />}
                              Lưu cấu hình
                            </Button>
                          </div>
                        </div>
                      ) : (
                        <Empty className="border border-dashed rounded-xl py-8">
                          <EmptyMedia variant="icon">
                            <CreditCard className="size-5 text-muted-foreground" />
                          </EmptyMedia>
                          <EmptyHeader>
                            <EmptyTitle className="text-xs">Không tìm thấy dữ liệu</EmptyTitle>
                            <EmptyDescription className="text-xs">
                              Không thể tải cài đặt billing từ máy chủ.
                            </EmptyDescription>
                          </EmptyHeader>
                        </Empty>
                      )}
                    </form>
                  ) : isTenantAdmin ? (
                    <TenantSettingsForm mode="self" noCard={true} />
                  ) : null}
                </div>
              )}

              {/* ── TAB 4: BẢO MẬT ── */}
              {activeTab === "security" && <UserSettingsForm noCard={true} />}
            </div>
          </ScrollArea>
        </div>
      </DialogContent>
    </Dialog>
  );
}
