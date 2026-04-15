"use client";

import { useSession } from "next-auth/react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";

export default function SettingsPage() {
  const { data: session } = useSession();

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Cài đặt</h1>

      <Card>
        <CardHeader>
          <CardTitle>Thông tin tài khoản</CardTitle>
          <CardDescription>Thông tin người dùng hiện tại</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-3 items-center gap-4">
            <Label className="text-muted-foreground">Tên đăng nhập</Label>
            <div className="col-span-2 font-medium">{session?.user?.name}</div>
          </div>
          <div className="grid grid-cols-3 items-center gap-4">
            <Label className="text-muted-foreground">Vai trò</Label>
            <div className="col-span-2">
              <Badge variant="secondary">{session?.role}</Badge>
            </div>
          </div>
          <div className="grid grid-cols-3 items-center gap-4">
            <Label className="text-muted-foreground">ID</Label>
            <div className="col-span-2 text-sm text-muted-foreground font-mono">
              {session?.userId}
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
