import { auth } from "@/lib/auth";
import { tenantsApi, conversationsApi } from "@/lib/api-client";
import { ConversationAuditManager } from "@/components/conversations/conversation-audit-manager";

export default async function AdminConversationsPage() {
  const session = await auth();
  const [tenants, convRes] = await Promise.all([
    tenantsApi.list(session?.accessToken).catch(() => []),
    conversationsApi.list(0, 50, undefined, session?.accessToken).catch(() => ({ items: [] })),
  ]);

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-6 p-6 md:p-8 animate-in fade-in-50 duration-300">
      <ConversationAuditManager
        initialTenants={tenants}
        initialConversations={convRes.items}
      />
    </div>
  );
}
