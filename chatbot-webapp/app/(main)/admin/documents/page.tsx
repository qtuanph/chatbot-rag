import { auth } from "@/lib/auth";
import { DocumentCatalog } from "@/components/documents/document-catalog";
import { tenantsApi, documentsApi } from "@/lib/api-client";

export default async function AdminDocumentsPage() {
  const session = await auth();
  const [tenants, docsRes] = await Promise.all([
    tenantsApi.list(session?.accessToken).catch(() => []),
    documentsApi.list(undefined, session?.accessToken).catch(() => ({ items: [] })),
  ]);

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-6 p-6 md:p-8 animate-in fade-in-50 duration-300">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Quản lý tài liệu dùng chung (Knowledge Base)</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Upload tài liệu dùng chung lên hệ thống, sau đó phân quyền cho từng công ty (Tenant) được phép tra cứu thông tin. Vector được lưu duy nhất 1 lần.
        </p>
      </div>
      <DocumentCatalog tenantOptions={tenants} initialDocuments={docsRes.items} />
    </div>
  );
}
