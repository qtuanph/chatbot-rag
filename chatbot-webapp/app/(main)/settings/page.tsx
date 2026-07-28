"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";

import { TenantSettingsForm } from "@/components/tenants/tenant-settings-form";
import { UserSettingsForm } from "@/components/auth/user-settings-form";
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { formatRoleLabel } from "@/lib/format";
import { settingsApi } from "@/lib/api-client";
import type { BillingSettings } from "@/types/api";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";

export default function SettingsPage() {
  const { data: session } = useSession();
  const isPlatformAdmin = session?.role === "platform_admin";

  const [billingData, setBillingData] = useState<BillingSettings | null>(null);
  const [billingLoading, setBillingLoading] = useState(false);
  const [billingSaving, setBillingSaving] = useState(false);

  useEffect(() => {
    if (isPlatformAdmin) {
      setBillingLoading(true);
      settingsApi.getBilling()
        .then(setBillingData)
        .catch((err) => {
          console.error(err);
          toast.error("Không thể tải cài đặt billing");
        })
        .finally(() => setBillingLoading(false));
    }
  }, [isPlatformAdmin]);

  const saveBilling = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!billingData) return;
    setBillingSaving(true);
    try {
      const updated = await settingsApi.updateBilling(billingData);
      setBillingData(updated);
      toast.success("Đã lưu cấu hình platform billing & quota");
    } catch (err: any) {
      toast.error(err.message || "Không thể lưu cấu hình");
    } finally {
      setBillingSaving(false);
    }
  };

  const handleBillingChange = (field: keyof BillingSettings, val: string) => {
    setBillingData(prev => prev ? { ...prev, [field]: parseInt(val) || 0 } : null);
  };

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-6 p-6">
      <div>
        <h1 className="text-2xl font-bold">Cài đặt</h1>
        <p className="text-sm text-muted-foreground">Thông tin tài khoản và cấu hình chatbot theo phạm vi quyền hiện tại.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Tài khoản hiện tại</CardTitle>
          <CardDescription>Thông tin phiên đăng nhập đang sử dụng trên webapp.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4 text-sm">
          <div className="flex items-center justify-between gap-4 border-b pb-3">
            <span className="text-muted-foreground">Tên đăng nhập</span>
            <span className="font-medium">{session?.user?.name || "—"}</span>
          </div>
          <div className="flex items-center justify-between gap-4 border-b pb-3">
            <span className="text-muted-foreground">Vai trò</span>
            <Badge variant="secondary">{formatRoleLabel(session?.role)}</Badge>
          </div>
          <div className="flex items-center justify-between gap-4">
            <span className="text-muted-foreground">Tenant ID</span>
            <span className="font-mono text-xs">{session?.tenantId || "Không áp dụng"}</span>
          </div>
        </CardContent>
      </Card>

      <UserSettingsForm />

      {isPlatformAdmin ? (
        <form onSubmit={saveBilling} className="flex flex-col gap-6">
          <Card>
            <CardHeader>
              <CardTitle>Cài đặt Platform & Billing</CardTitle>
              <CardDescription>
                Cấu hình giá token và giới hạn cho toàn hệ thống.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {billingLoading ? (
                <div className="flex items-center justify-center p-6">
                  <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                </div>
              ) : billingData ? (
                <div className="space-y-6">
                  <div className="space-y-4">
                    <h3 className="font-medium text-sm">Giá Token API</h3>
                    <div className="grid gap-4 sm:grid-cols-2">
                      <div className="space-y-2">
                        <Label>Input Price (VND/1M tokens)</Label>
                        <Input
                          type="number"
                          value={billingData.ai_input_price_vnd_per_1m}
                          onChange={(e) => handleBillingChange("ai_input_price_vnd_per_1m", e.target.value)}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label>Output Price (VND/1M tokens)</Label>
                        <Input
                          type="number"
                          value={billingData.ai_output_price_vnd_per_1m}
                          onChange={(e) => handleBillingChange("ai_output_price_vnd_per_1m", e.target.value)}
                        />
                      </div>
                    </div>
                  </div>

                  <div className="space-y-4">
                    <h3 className="font-medium text-sm">Giới hạn & Ngân sách</h3>
                    <div className="grid gap-4 sm:grid-cols-2">
                      <div className="space-y-2">
                        <Label>Hard budget (VND/tháng)</Label>
                        <Input
                          type="number"
                          value={billingData.quota_hard_budget_vnd}
                          onChange={(e) => handleBillingChange("quota_hard_budget_vnd", e.target.value)}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label>User rate per min</Label>
                        <Input
                          type="number"
                          value={billingData.quota_user_rate_per_min}
                          onChange={(e) => handleBillingChange("quota_user_rate_per_min", e.target.value)}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label>User daily requests</Label>
                        <Input
                          type="number"
                          value={billingData.quota_user_daily_requests}
                          onChange={(e) => handleBillingChange("quota_user_daily_requests", e.target.value)}
                        />
                      </div>
                    </div>
                    
                    <div className="grid gap-4 sm:grid-cols-3">
                      <div className="space-y-2">
                        <Label>Warn Threshold (%)</Label>
                        <Input
                          type="number"
                          value={billingData.quota_cost_alert_pct_warn}
                          onChange={(e) => handleBillingChange("quota_cost_alert_pct_warn", e.target.value)}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label>Alert Threshold (%)</Label>
                        <Input
                          type="number"
                          value={billingData.quota_cost_alert_pct_alert}
                          onChange={(e) => handleBillingChange("quota_cost_alert_pct_alert", e.target.value)}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label>Cutoff Threshold (%)</Label>
                        <Input
                          type="number"
                          value={billingData.quota_cost_alert_pct_cutoff}
                          onChange={(e) => handleBillingChange("quota_cost_alert_pct_cutoff", e.target.value)}
                        />
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="text-sm text-muted-foreground">Không có dữ liệu.</div>
              )}
            </CardContent>
            {billingData && (
              <CardFooter className="flex justify-end border-t pt-6">
                <Button type="submit" disabled={billingSaving}>
                  {billingSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  Lưu thay đổi
                </Button>
              </CardFooter>
            )}
          </Card>
        </form>
      ) : (
        <TenantSettingsForm mode="self" />
      )}
    </div>
  );
}
