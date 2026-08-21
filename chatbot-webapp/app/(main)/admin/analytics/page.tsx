import { auth } from "@/lib/auth";
import { analyticsApi } from "@/lib/api-client";
import { AnalyticsDashboard } from "@/components/analytics/analytics-dashboard";

export default async function AdminAnalyticsPage() {
  const session = await auth();
  const initialStats = await analyticsApi.getStats(30, session?.accessToken).catch(() => null);

  return (
    <div className="mx-auto max-w-7xl">
      <AnalyticsDashboard
        title="Báo cáo Thống kê Platform"
        subtitle="Theo dõi tổng thể lưu lượng sử dụng, dung lượng Token, độ trễ và chi phí ước tính."
        allowClear
        initialStats={initialStats}
      />
    </div>
  );
}
