import { auth } from "@/lib/auth";
import { documentsApi } from "@/lib/api-client";
import { DocumentCatalog } from "@/components/documents/document-catalog";

export default async function TenantDocumentsPage() {
  const session = await auth();
  const tenantId = session?.tenantId || undefined;
  const docsRes = await documentsApi.list(tenantId, session?.accessToken).catch(() => ({ items: [] }));

  return (
    <div className="flex max-w-7xl flex-col gap-6 p-6 md:p-8 animate-in fade-in-50 duration-300">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Tài liệu của tenant</h1>
        <p className="text-sm text-muted-foreground mt-1">Danh sách tài liệu hiện được chatbot dùng để trả lời trong tenant hiện tại.</p>
      </div>
      <DocumentCatalog
        readOnly
        selectedTenantId={tenantId || null}
        initialDocuments={docsRes.items}
      />
    </div>
  );
}
