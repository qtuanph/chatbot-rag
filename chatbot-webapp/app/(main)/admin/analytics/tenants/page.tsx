import { TenantUsageTable } from "@/components/analytics/tenant-usage-table";

export default function AdminAnalyticsTenantsPage() {
  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-6 p-6 md:p-8 animate-in fade-in-50 duration-300">
      <TenantUsageTable />
    </div>
  );
}
