import { auth } from "@/lib/auth";
import { analyticsApi } from "@/lib/api-client";
import { AnalyticsTrends } from "@/components/analytics/analytics-trends";

export default async function AdminAnalyticsTrendsPage() {
  const session = await auth();
  const initialStats = await analyticsApi.getStats(30, session?.accessToken).catch(() => null);

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-6 p-6 md:p-8 animate-in fade-in-50 duration-300">
      <AnalyticsTrends initialStats={initialStats} />
    </div>
  );
}
