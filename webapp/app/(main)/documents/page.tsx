"use client";

import { useSession } from "next-auth/react";

import { DocumentCatalog } from "@/components/documents/document-catalog";
import { PageHeader } from "@/components/layout/page-header";

export default function TenantDocumentsPage() {
  const { data: session } = useSession();

  return (
    <div className="space-y-6 p-6">
      <PageHeader
        title="Tài liệu của tenant"
        description="Danh sách tài liệu hiện được chatbot dùng để trả lời trong tenant hiện tại."
      />
      <DocumentCatalog
        title="Kho tài liệu"
        description="Chế độ chỉ xem dành cho tenant admin. Upload/xóa/rechunk được quản lý ở phía platform."
        readOnly
        selectedTenantId={session?.tenantId || null}
      />
    </div>
  );
}
