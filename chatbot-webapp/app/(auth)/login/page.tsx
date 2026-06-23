"use client";

import { Suspense } from "react";

import { LoginForm } from "@/components/auth/login-form";

export default function LoginPage() {
  return (
    <Suspense fallback={<div className="flex min-h-svh items-center justify-center text-sm text-muted-foreground">Đang tải...</div>}>
      <div className="flex min-h-svh flex-col items-center justify-center bg-muted p-6 md:p-10">
        <div className="w-full max-w-sm md:max-w-5xl">
          <LoginForm />
        </div>
      </div>
    </Suspense>
  );
}
