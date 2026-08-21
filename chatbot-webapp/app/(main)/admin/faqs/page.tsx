import { auth } from "@/lib/auth";
import { FaqManager } from "@/components/faqs/faq-manager";
import { tenantsApi, faqApi } from "@/lib/api-client";

export default async function AdminFaqsPage() {
  const session = await auth();
  const tenants = await tenantsApi.list(session?.accessToken).catch(() => []);
  const firstTenantId = tenants[0]?.id;
  const [initialFaqs, initialEscalations] = firstTenantId
    ? await Promise.all([
        faqApi.list(firstTenantId, session?.accessToken).catch(() => []),
        faqApi.listEscalations(firstTenantId, session?.accessToken).catch(() => []),
      ])
    : [[], []];

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-6 p-6 md:p-8 animate-in fade-in-50 duration-300">
      <FaqManager
        tenantOptions={tenants}
        initialFaqs={initialFaqs}
        initialEscalations={initialEscalations}
      />
    </div>
  );
}
