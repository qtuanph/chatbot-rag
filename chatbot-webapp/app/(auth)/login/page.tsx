"use client";

import { Suspense } from "react";
import Image from "next/image";
import { Bot, Sparkles, ShieldCheck, Zap } from "lucide-react";

import { LoginForm } from "@/components/auth/login-form";

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-svh items-center justify-center text-sm text-muted-foreground">
          Đang tải...
        </div>
      }
    >
      <div className="grid min-h-svh lg:grid-cols-2">
        {/* Left Column: Form Section */}
        <div className="flex flex-col gap-4 p-6 md:p-10">
          <div className="flex justify-center gap-2 md:justify-start">
            <div className="flex items-center gap-2.5 font-medium">
              <div className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-sm">
                <Bot className="size-4.5" />
              </div>
              <div className="flex flex-col leading-tight">
                <span className="font-semibold text-sm">SSE Cloud ERP</span>
                <span className="text-[11px] text-muted-foreground">Enterprise RAG Platform</span>
              </div>
            </div>
          </div>
          <div className="flex flex-1 items-center justify-center">
            <div className="w-full max-w-xs">
              <LoginForm />
            </div>
          </div>
        </div>

        {/* Right Column: Cover Image & Feature Highlights */}
        <div className="relative hidden overflow-hidden bg-muted lg:flex lg:flex-col lg:justify-between p-12">
          {/* Decorative Gradient Background */}
          <div className="absolute inset-0 bg-gradient-to-br from-primary/95 via-primary/85 to-primary/75" />
          <div className="absolute inset-0 bg-[radial-gradient(#ffffff_1px,transparent_1px)] [background-size:20px_20px] opacity-15" />

          {/* Top Brand Tag */}
          <div className="relative z-10 flex items-center gap-2 text-primary-foreground/90">
            <div className="flex size-7 items-center justify-center rounded-md bg-primary-foreground/20 backdrop-blur-sm">
              <Sparkles className="size-3.5" />
            </div>
            <span className="text-xs font-semibold tracking-wide uppercase">Multi-Tenant AI Knowledge</span>
          </div>

          {/* Center/Bottom Highlight Content */}
          <div className="relative z-10 space-y-6 text-primary-foreground">
            <div className="space-y-3">
              <h2 className="text-3xl font-bold tracking-tight leading-tight">
                Hệ thống RAG Chatbot Doanh nghiệp SSE
              </h2>
              <p className="text-sm leading-relaxed text-primary-foreground/80 max-w-md">
                Quản trị tri thức tập trung, phân quyền đa tenant nghiêm ngặt, tích hợp widget chatbot dễ dàng vào mọi phần mềm.
              </p>
            </div>

            <div className="grid grid-cols-2 gap-4 pt-2">
              <div className="rounded-xl border border-primary-foreground/15 bg-primary-foreground/10 p-4 backdrop-blur-sm">
                <ShieldCheck className="size-5 mb-2 text-primary-foreground/90" />
                <div className="font-semibold text-xs">Bảo mật Đa Tenant</div>
                <div className="text-[11px] text-primary-foreground/70 mt-0.5">Dữ liệu phân lập tuyệt đối</div>
              </div>
              <div className="rounded-xl border border-primary-foreground/15 bg-primary-foreground/10 p-4 backdrop-blur-sm">
                <Zap className="size-5 mb-2 text-primary-foreground/90" />
                <div className="font-semibold text-xs">Tốc độ & Hybrid RAG</div>
                <div className="text-[11px] text-primary-foreground/70 mt-0.5">Phản hồi siêu tốc với Cache</div>
              </div>
            </div>
          </div>

          {/* Bottom Copyright */}
          <div className="relative z-10 text-xs text-primary-foreground/60">
            © 2026 SSE Software. All rights reserved.
          </div>
        </div>
      </div>
    </Suspense>
  );
}
