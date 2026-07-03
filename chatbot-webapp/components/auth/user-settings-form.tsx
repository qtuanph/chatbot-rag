"use client";

import { useState, useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { useSession, signOut } from "next-auth/react";
import { toast } from "sonner";

import { authApi } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { KeyRoundIcon, UserIcon } from "lucide-react";

const formSchema = z
  .object({
    username: z.string().min(3, "Tên đăng nhập tối thiểu 3 ký tự").max(64).optional().or(z.literal("")),
    current_password: z.string().optional(),
    new_password: z.string().optional(),
  })
  .refine(
    (data) => {
      // If setting a new password, current password is required
      if (data.new_password && !data.current_password) {
        return false;
      }
      return true;
    },
    {
      message: "Vui lòng nhập mật khẩu hiện tại để đổi mật khẩu mới",
      path: ["current_password"],
    }
  )
  .refine(
    (data) => {
      // If new password is provided, must be >= 6 chars
      if (data.new_password && data.new_password.length < 6) {
        return false;
      }
      return true;
    },
    {
      message: "Mật khẩu mới phải có tối thiểu 6 ký tự",
      path: ["new_password"],
    }
  );

export function UserSettingsForm() {
  const { data: session, update } = useSession();
  const [isSubmitting, setIsSubmitting] = useState(false);

  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      username: "",
      current_password: "",
      new_password: "",
    },
  });

  // Hydrate username once session is loaded
  useEffect(() => {
    if (session?.user?.name) {
      form.setValue("username", session.user.name);
    }
  }, [session, form]);

  const onSubmit = async (values: z.infer<typeof formSchema>) => {
    try {
      setIsSubmitting(true);
      
      const payload: any = {};
      let isUsernameChanged = false;
      let isPasswordChanged = false;

      if (values.username && values.username !== session?.user?.name) {
        payload.username = values.username;
        isUsernameChanged = true;
      }

      if (values.new_password) {
        payload.current_password = values.current_password;
        payload.new_password = values.new_password;
        isPasswordChanged = true;
      }

      if (Object.keys(payload).length === 0) {
        toast.info("Không có thay đổi nào để cập nhật");
        return;
      }

      await authApi.updateProfile(payload);
      
      if (isPasswordChanged) {
        toast.success("Đổi mật khẩu thành công. Vui lòng đăng nhập lại.");
        await signOut({ callbackUrl: "/login" });
      } else if (isUsernameChanged) {
        toast.success("Cập nhật tên đăng nhập thành công");
        await update({ name: values.username });
        form.reset({
          username: values.username,
          current_password: "",
          new_password: "",
        });
      }
    } catch (error: any) {
      toast.error("Cập nhật thất bại", {
        description: error.message || "Đã xảy ra lỗi không xác định",
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
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
            <FormField
              control={form.control}
              name="username"
              render={({ field }) => (
                <FormItem>
                  <FormLabel className="flex items-center gap-2">
                    <UserIcon className="size-4" />
                    Tên đăng nhập mới
                  </FormLabel>
                  <FormControl>
                    <Input placeholder="Nhập tên đăng nhập" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <div className="grid gap-4 sm:grid-cols-2 border-t pt-4">
              <FormField
                control={form.control}
                name="current_password"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className="flex items-center gap-2">
                      <KeyRoundIcon className="size-4" />
                      Mật khẩu hiện tại
                    </FormLabel>
                    <FormControl>
                      <Input type="password" placeholder="Nhập mật khẩu cũ (nếu muốn đổi)" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="new_password"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Mật khẩu mới</FormLabel>
                    <FormControl>
                      <Input type="password" placeholder="Mật khẩu mới (tối thiểu 6 ký tự)" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Đang cập nhật..." : "Lưu thay đổi"}
            </Button>
          </form>
        </Form>
      </CardContent>
    </Card>
  );
}
