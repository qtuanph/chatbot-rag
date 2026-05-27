"use client";

import { AnalyticsDashboard } from "@/components/analytics/analytics-dashboard";

export default function MemberAnalyticsPage() {
  return <AnalyticsDashboard title="Thống kê của tôi" subtitle="Số liệu AI theo tài khoản của bạn" allowClear={false} />;
}

