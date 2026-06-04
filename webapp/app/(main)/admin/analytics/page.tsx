"use client";

import { AnalyticsDashboard } from "@/components/analytics/analytics-dashboard";
import { TenantUsageTable } from "@/components/analytics/tenant-usage-table";

export default function AdminAnalyticsPage() {
  return (
    <div className="space-y-6">
      <AnalyticsDashboard
        title="Thống kê toàn platform"
        subtitle="Theo dõi usage tổng thể và phát hiện tenant đang tiêu tốn nhiều nhất."
        allowClear
      />
      <div className="px-6 pb-6">
        <TenantUsageTable />
      </div>
    </div>
  );
}
