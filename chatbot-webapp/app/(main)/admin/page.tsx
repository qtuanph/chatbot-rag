import { auth } from "@/lib/auth";
import { healthApi } from "@/lib/api-client";
import { AdminOverview } from "@/components/admin/admin-overview";

export default async function AdminDashboardPage() {
  const session = await auth();
  const initialHealth = await healthApi.getData(session?.accessToken).catch(() => null);

  return <AdminOverview initialHealth={initialHealth} />;
}
