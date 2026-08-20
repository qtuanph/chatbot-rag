"use client";

import { useEffect } from "react";
import { AlertCircle, RefreshCw, Home } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Route runtime error:", error);
  }, [error]);

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center p-6 text-center animate-in fade-in-50 duration-300">
      <div className="flex size-14 items-center justify-center rounded-2xl bg-destructive/10 text-destructive mb-4 shadow-xs">
        <AlertCircle className="size-7" />
      </div>
      <h2 className="text-xl font-bold tracking-tight">Đã xảy ra lỗi khi tải trang</h2>
      <p className="mt-2 max-w-md text-sm text-muted-foreground">
        Hệ thống không thể tải dữ liệu của phân hệ này. Vui lòng thử tải lại hoặc quay về trang chính.
      </p>
      <div className="mt-6 flex gap-3">
        <Button onClick={() => reset()} variant="outline" className="gap-2">
          <RefreshCw className="size-4" />
          Thử lại
        </Button>
        <Link href="/" className="inline-flex items-center justify-center gap-2 rounded-md text-sm font-medium h-9 px-4 py-2 bg-primary text-primary-foreground hover:bg-primary/90">
          <Home className="size-4" />
          Trang chủ
        </Link>
      </div>
    </div>
  );
}
