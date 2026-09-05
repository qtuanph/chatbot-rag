"use client";

import { useState } from "react";
import { useSession, signOut } from "next-auth/react";
import { toast } from "sonner";

import { authApi } from "@/lib/api-client";
import { UpdateProfileRequestSchema } from "@/lib/schemas";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";


export function UserSettingsForm({ noCard = false }: { noCard?: boolean }) {
  const { data: session, update } = useSession();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [username, setUsername] = useState(session?.user?.name || "");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSubmitting) return;

    try {
      setIsSubmitting(true);

      const payload: Record<string, string> = {};
      let isUsernameChanged = false;
      let isPasswordChanged = false;

      if (username && username !== session?.user?.name) {
        payload.username = username;
        isUsernameChanged = true;
      }

      if (newPassword) {
        if (newPassword.length < 6) {
          toast.error("Mật khẩu mới phải có tối thiểu 6 ký tự");
          return;
        }
        if (!currentPassword) {
          toast.error("Vui lòng nhập mật khẩu hiện tại để đổi mật khẩu mới");
          return;
        }
        payload.current_password = currentPassword;
        payload.new_password = newPassword;
        isPasswordChanged = true;
      }

      if (Object.keys(payload).length === 0) {
        toast.info("Không có thay đổi nào để cập nhật");
        return;
      }

      const parsedPayload = UpdateProfileRequestSchema.safeParse(payload);
      if (!parsedPayload.success) {
        toast.error("Dữ liệu cập nhật không hợp lệ");
        return;
      }

      await authApi.updateProfile(parsedPayload.data);

      if (isPasswordChanged) {
        toast.success("Đổi mật khẩu thành công. Vui lòng đăng nhập lại.");
        await signOut({ callbackUrl: "/login" });
      } else if (isUsernameChanged) {
        toast.success("Cập nhật tên đăng nhập thành công");
        await update({ name: username });
        setCurrentPassword("");
        setNewPassword("");
      }
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "Đã xảy ra lỗi không xác định";
      toast.error("Cập nhật thất bại", {
        description: message,
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const formContent = (
    <form onSubmit={onSubmit} className="space-y-6">
      <div className="space-y-1.5">
        <Label className="text-xs">Tên đăng nhập mới</Label>
        <Input
          placeholder="Nhập tên đăng nhập"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          className="h-8 text-xs max-w-sm"
        />
      </div>

      <div className="space-y-3 pt-2 border-t">
        <h4 className="text-xs font-semibold text-foreground uppercase tracking-wider">
          Đổi mật khẩu
        </h4>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label className="text-xs">Mật khẩu hiện tại</Label>
            <Input
              type="password"
              placeholder="Nhập mật khẩu cũ (nếu muốn đổi)"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              className="h-8 text-xs"
            />
          </div>

          <div className="space-y-1.5">
            <Label className="text-xs">Mật khẩu mới</Label>
            <Input
              type="password"
              placeholder="Mật khẩu mới (tối thiểu 6 ký tự)"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              className="h-8 text-xs"
            />
          </div>
        </div>
      </div>

      <div className="pt-2">
        <Button size="sm" type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Đang cập nhật..." : "Lưu thay đổi"}
        </Button>
      </div>
    </form>
  );

  if (noCard) {
    return (
      <div className="space-y-6">
        <div className="space-y-1">
          <h3 className="text-sm font-medium">Bảo mật tài khoản</h3>
          <p className="text-xs text-muted-foreground">
            Thay đổi tên đăng nhập hoặc mật khẩu cho tài khoản của bạn.
          </p>
        </div>
        {formContent}
      </div>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Cập nhật hồ sơ cá nhân</CardTitle>
        <CardDescription>
          Thay đổi tên đăng nhập hoặc mật khẩu cho tài khoản của bạn.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {formContent}
      </CardContent>
    </Card>
  );
}
