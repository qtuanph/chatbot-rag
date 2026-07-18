"use client";

import { useState, useEffect } from "react";
import { useSession, signOut } from "next-auth/react";
import { toast } from "sonner";

import { authApi } from "@/lib/api-client";
import { UpdateProfileRequestSchema } from "@/lib/schemas";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { KeyRoundIcon, UserIcon } from "lucide-react";

export function UserSettingsForm() {
  const { data: session, update } = useSession();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [username, setUsername] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");

  useEffect(() => {
    if (session?.user?.name) {
      setUsername(session.user.name);
    }
  }, [session]);

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

  return (
    <Card>
      <CardHeader>
        <CardTitle>Cập nhật hồ sơ cá nhân</CardTitle>
        <CardDescription>
          Thay đổi tên đăng nhập hoặc mật khẩu cho tài khoản của bạn.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={onSubmit} className="space-y-6">
          <div className="space-y-2">
            <label className="text-sm font-medium flex items-center gap-2">
              <UserIcon className="size-4" />
              Tên đăng nhập mới
            </label>
            <Input
              placeholder="Nhập tên đăng nhập"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
            />
          </div>

          <div className="grid gap-4 sm:grid-cols-2 border-t pt-4">
            <div className="space-y-2">
              <label className="text-sm font-medium flex items-center gap-2">
                <KeyRoundIcon className="size-4" />
                Mật khẩu hiện tại
              </label>
              <Input
                type="password"
                placeholder="Nhập mật khẩu cũ (nếu muốn đổi)"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">Mật khẩu mới</label>
              <Input
                type="password"
                placeholder="Mật khẩu mới (tối thiểu 6 ký tự)"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
              />
            </div>
          </div>

          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Đang cập nhật..." : "Lưu thay đổi"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
