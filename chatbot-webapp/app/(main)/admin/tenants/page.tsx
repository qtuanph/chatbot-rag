import { auth } from "@/lib/auth";
import { tenantsApi } from "@/lib/api-client";
import { TenantManager } from "@/components/tenants/tenant-manager";

export default async function AdminTenantsPage() {
  const session = await auth();
  const initialTenants = await tenantsApi.list(session?.accessToken).catch(() => []);

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-6 p-6 md:p-8 animate-in fade-in-50 duration-300">
      <TenantManager initialTenants={initialTenants} />
    </div>
  );
}
