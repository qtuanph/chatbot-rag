"use client";

import { AnalyticsDashboard } from "@/components/analytics/analytics-dashboard";

export default function AdminAnalyticsPage() {
  return (
    <div className="mx-auto max-w-7xl">
      <AnalyticsDashboard
        title="Báo cáo Thống kê Platform"
        subtitle="Theo dõi tổng thể lưu lượng sử dụng, dung lượng Token, độ trễ và chi phí ước tính."
        allowClear
      />
    </div>
  );
}
