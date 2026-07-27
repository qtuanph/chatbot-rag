"use client";

import { useSession } from "next-auth/react";
import { AlertCircle } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

export default function TenantFaqsPage() {
  useSession();
  return (
    <div className="mx-auto max-w-4xl p-6">
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" />
        <AlertTitle>Không có quyền truy cập</AlertTitle>
        <AlertDescription>
          Tính năng Quản lý FAQ &amp; Chuyển tiếp câu hỏi hiện chỉ dành riêng cho Quản trị viên hệ thống (Platform Admin).
        </AlertDescription>
      </Alert>
    </div>
  );
}
