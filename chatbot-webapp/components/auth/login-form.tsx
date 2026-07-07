"use client";

import { useState } from "react";
import { signIn } from "next-auth/react";
import { useRouter, useSearchParams } from "next/navigation";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";

export function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const callbackUrl = searchParams.get("callbackUrl");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);

    const formData = new FormData(event.currentTarget);
    const username = String(formData.get("username") || "");
    const password = String(formData.get("password") || "");

    try {
      const result = await signIn("credentials", {
        username,
        password,
        redirect: false,
      });

      const hasError = result?.error || (result?.url ? new URL(result.url).searchParams.has("error") : false);

      if (hasError) {
        toast.error("Sai tên đăng nhập hoặc mật khẩu");
        return;
      }

      if (callbackUrl) {
        router.push(callbackUrl);
      } else {
        const response = await fetch("/api/auth/session");
        const session = await response.json();
        router.push(session?.role === "platform_admin" ? "/admin" : "/analytics");
      }

      router.refresh();
    } catch {
      toast.error("Không thể đăng nhập. Vui lòng thử lại.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <Card className="overflow-hidden p-0">
        <CardContent className="grid p-0 md:grid-cols-2">
          <form onSubmit={handleSubmit} className="p-6 md:p-8">
            <FieldGroup>
              <div className="flex flex-col items-center gap-2 text-center">
                <h1 className="text-2xl font-bold">Chào mừng quay lại</h1>
                <p className="text-balance text-muted-foreground">Đăng nhập để quản trị tenant và kiểm thử chatbot nội bộ.</p>
              </div>

              <Field>
                <FieldLabel htmlFor="username">Tên đăng nhập</FieldLabel>
                <Input id="username" name="username" placeholder="admin" autoComplete="username" required />
              </Field>

              <Field>
                <FieldLabel htmlFor="password">Mật khẩu</FieldLabel>
                <Input
                  id="password"
                  name="password"
                  type="password"
                  placeholder="••••••••"
                  autoComplete="current-password"
                  required
                />
              </Field>

              <Field>
                <Button type="submit" disabled={loading}>
                  {loading ? "Đang đăng nhập..." : "Đăng nhập"}
                </Button>
              </Field>

              <FieldDescription className="text-center">
                Nếu anh chưa thấy tài khoản tenant admin, hãy tạo từ khu quản trị tenant của platform.
              </FieldDescription>
            </FieldGroup>
          </form>

          <div className="relative hidden overflow-hidden md:block">
            <div className="absolute inset-0 bg-gradient-to-br from-primary/90 via-primary to-primary/80" />
            <div className="relative flex h-full flex-col justify-between gap-6 p-8 text-primary-foreground">
              <div className="flex items-center gap-3">
                <div className="flex size-10 items-center justify-center rounded-lg bg-primary-foreground/15 backdrop-blur-sm ring-1 ring-primary-foreground/20">
                  <span className="text-base font-bold tracking-tight">SSE</span>
                </div>
                <div className="flex flex-col leading-tight">
                  <span className="text-sm font-semibold">SSE Cloud ERP</span>
                  <span className="text-xs text-primary-foreground/70">Multi-tenant RAG Platform</span>
                </div>
              </div>

              <div className="space-y-3">
                <div className="inline-flex w-fit items-center gap-2 rounded-full border border-primary-foreground/20 bg-primary-foreground/10 px-3 py-1 text-xs font-medium text-primary-foreground/90 backdrop-blur">
                  <span className="size-1.5 rounded-full bg-primary-foreground/60" />
                  Nền tảng quản trị chatbot
                </div>
                <h2 className="text-2xl font-semibold leading-tight tracking-tight">
                  Quản trị gọn, chat mượt, tích hợp dễ.
                </h2>
                <p className="max-w-md text-sm leading-6 text-primary-foreground/80">
                  Hệ thống RAG chatbot dành cho doanh nghiệp SSE — quản trị tenant tập trung, tích hợp nhanh vào phần mềm khách hàng.
                </p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
