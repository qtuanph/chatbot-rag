"use client";

import { useSession } from "next-auth/react";

import { TenantSettingsForm } from "@/components/tenants/tenant-settings-form";
import { UserSettingsForm } from "@/components/auth/user-settings-form";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { formatRoleLabel } from "@/lib/format";

export default function SettingsPage() {
  const { data: session } = useSession();
  const isPlatformAdmin = session?.role === "platform_admin";

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
        <Card>
        <CardHeader>
          <CardTitle>Ghi chú cho Platform Admin</CardTitle>
          <CardDescription>
            Instruction tenant được chỉnh trong màn quản lý tenant để tránh sửa nhầm phạm vi.
          </CardDescription>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          Vào mục quản lý tenant để chọn tenant và chỉnh chatbot display name, welcome message,
          instruction, API key và quota.
        </CardContent>
      </Card>
      ) : (
        <TenantSettingsForm mode="self" />
      )}
    </div>
  );
}
