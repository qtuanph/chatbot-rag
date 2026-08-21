import { auth } from "@/lib/auth";
import { analyticsApi } from "@/lib/api-client";
import { AnalyticsDashboard } from "@/components/analytics/analytics-dashboard";

export default async function TenantAnalyticsPage() {
  const session = await auth();
  const initialStats = await analyticsApi.getStats(30, session?.accessToken).catch(() => null);

  return (
    <AnalyticsDashboard
      title="Thống kê tenant của tôi"
      subtitle="Theo dõi mức sử dụng AI nội bộ theo đúng tenant hiện tại."
      initialStats={initialStats}
    />
  );
}
