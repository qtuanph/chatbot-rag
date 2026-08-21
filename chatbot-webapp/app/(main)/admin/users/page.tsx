import { auth } from "@/lib/auth";
import { authApi, tenantsApi } from "@/lib/api-client";
import { UserManager } from "@/components/admin/user-manager";

export default async function AdminUsersPage() {
  const session = await auth();
  const [users, roles, tenants] = await Promise.all([
    authApi.getUsers(session?.accessToken).catch(() => []),
    authApi.getRoles(session?.accessToken).catch(() => []),
    tenantsApi.list(session?.accessToken).catch(() => []),
  ]);

  return (
    <UserManager
      initialUsers={users}
      initialRoles={roles}
      initialTenants={tenants}
    />
  );
}
