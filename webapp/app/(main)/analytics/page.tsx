"use client";

import { AnalyticsDashboard } from "@/components/analytics/analytics-dashboard";

export default function TenantAnalyticsPage() {
  return (
    <AnalyticsDashboard
      title="Thống kê tenant của tôi"
      subtitle="Theo dõi mức sử dụng AI nội bộ theo đúng tenant hiện tại."
    />
  );
}
