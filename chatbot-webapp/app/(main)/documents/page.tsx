"use client";

import { useSession } from "next-auth/react";

import { DocumentCatalog } from "@/components/documents/document-catalog";

export default function TenantDocumentsPage() {
  const { data: session } = useSession();

  return (
    <div className="flex max-w-7xl flex-col gap-6 p-6">
      <div>
        <h1 className="text-2xl font-bold">Tài liệu của tenant</h1>
        <p className="text-sm text-muted-foreground">Danh sách tài liệu hiện được chatbot dùng để trả lời trong tenant hiện tại.</p>
      </div>
      <DocumentCatalog
        readOnly
        selectedTenantId={session?.tenantId || null}
      />
    </div>
  );
}
