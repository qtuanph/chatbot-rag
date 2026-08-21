import { auth } from "@/lib/auth";
import { faqApi } from "@/lib/api-client";
import { FaqManager } from "@/components/faqs/faq-manager";

export default async function TenantFaqsPage() {
  const session = await auth();
  const tenantId = session?.tenantId || undefined;
  const [initialFaqs, initialEscalations] = tenantId
    ? await Promise.all([
        faqApi.list(tenantId, session?.accessToken).catch(() => []),
        faqApi.listEscalations(tenantId, session?.accessToken).catch(() => []),
      ])
    : [[], []];

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-6 p-6 md:p-8 animate-in fade-in-50 duration-300">
      <FaqManager
        selectedTenantId={tenantId || null}
        initialFaqs={initialFaqs}
        initialEscalations={initialEscalations}
      />
    </div>
  );
}
