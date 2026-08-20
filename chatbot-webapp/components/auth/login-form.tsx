"use client";

import { useEffect, useState } from "react";
import { signIn } from "next-auth/react";
import { useRouter, useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { LoginRequestSchema } from "@/lib/schemas";

export function LoginForm({
  className,
  ...props
}: React.ComponentProps<"form">) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const callbackUrl = searchParams.get("callbackUrl");
  const errorParam = searchParams.get("error");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (errorParam === "SessionExpired") {
      toast.warning("Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.");
    }
  }, [errorParam]);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);

    const formData = new FormData(event.currentTarget);
    const payloadResult = LoginRequestSchema.safeParse({
      username: String(formData.get("username") || ""),
      password: String(formData.get("password") || ""),
    });

    if (!payloadResult.success) {
      toast.error("Vui lòng nhập đầy đủ tên đăng nhập và mật khẩu");
      setLoading(false);
      return;
    }

    const { username, password } = payloadResult.data;

    try {
      const result = await signIn("credentials", {
        username,
        password,
        redirect: false,
      });

      const hasError =
        result?.error ||
        (result?.url ? new URL(result.url).searchParams.has("error") : false);

      if (hasError) {
        toast.error("Sai tên đăng nhập hoặc mật khẩu");
        return;
      }

      if (callbackUrl) {
        router.push(callbackUrl);
      } else {
        const response = await fetch("/api/auth/session");
        const session = await response.json();
        router.push(
          session?.role === "platform_admin" ? "/admin" : "/analytics"
        );
      }

      router.refresh();
    } catch {
      toast.error("Không thể đăng nhập. Vui lòng thử lại.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className={cn("flex flex-col gap-6", className)}
      {...props}
    >
      <FieldGroup>
        <div className="flex flex-col items-center gap-1 text-center">
          <h1 className="text-2xl font-bold">Đăng nhập tài khoản</h1>
          <p className="text-balance text-sm text-muted-foreground">
            Nhập thông tin đăng nhập để quản trị hệ thống và kiểm thử AI
          </p>
        </div>

        <Field>
          <FieldLabel htmlFor="username">Tên đăng nhập</FieldLabel>
          <Input
            id="username"
            name="username"
            type="text"
            placeholder="admin"
            autoComplete="username"
            required
            disabled={loading}
          />
        </Field>

        <Field>
          <div className="flex items-center">
            <FieldLabel htmlFor="password">Mật khẩu</FieldLabel>
          </div>
          <Input
            id="password"
            name="password"
            type="password"
            placeholder="••••••••"
            autoComplete="current-password"
            required
            disabled={loading}
          />
        </Field>

        <Field>
          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Đang đăng nhập...
              </>
            ) : (
              "Đăng nhập"
            )}
          </Button>
        </Field>

        <FieldDescription className="text-center text-xs text-muted-foreground">
          Nếu chưa có tài khoản Tenant Admin, vui lòng liên hệ Platform Administrator để được cấp quyền.
        </FieldDescription>
      </FieldGroup>
    </form>
  );
}
