"use client";

import { useEffect, useState, useCallback } from "react";
import { useSession } from "next-auth/react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { healthApi } from "@/lib/api-client";
import type { HealthData } from "@/types/api";
import {
  Database,
  HardDrive,
  Brain,
  Server,
  Cpu,
} from "lucide-react";

const serviceIcons: Record<string, React.ElementType> = {
  database: Database,
  redis: HardDrive,
  storage: Server,
  ai_provider: Brain,
  workers: Server,
  qdrant: Cpu,
};

const serviceLabels: Record<string, string> = {
  database: "PostgreSQL",
  redis: "Redis",
  storage: "RustFS",
  ai_provider: "AI Provider",
  workers: "Celery Workers",
  qdrant: "Qdrant",
};

function statusColor(status: string) {
  switch (status) {
    case "up":
    case "healthy":
      return "bg-green-500/15 text-green-700 dark:text-green-400 border-green-500/25";
    case "degraded":
      return "bg-yellow-500/15 text-yellow-700 dark:text-yellow-400 border-yellow-500/25";
    default:
      return "bg-red-500/15 text-red-700 dark:text-red-400 border-red-500/25";
  }
}

export default function AdminDashboard() {
  const { data: session } = useSession();
  const [data, setData] = useState<HealthData | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    if (!session?.accessToken) return;
    try {
      const result = await healthApi.getData(session.accessToken);
      setData(result);
    } catch {
      // Silently fail
    } finally {
      setLoading(false);
    }
  }, [session?.accessToken]);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [fetchData]);

  if (loading) {
    return (
      <div className="p-6 space-y-6">
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {[...Array(5)].map((_, i) => (
            <Skeleton key={i} className="h-32" />
          ))}
        </div>
      </div>
    );
  }

  const checks = data?.checks || {};

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <Badge variant="outline" className={statusColor(data?.status || "unknown")}>
          {data?.status || "unknown"}
        </Badge>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {Object.entries(checks).map(([key, value]) => {
          const Icon = serviceIcons[key] || Server;
          const status = typeof value === "object" ? value.status : "unknown";

          return (
            <Card key={key}>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium">
                  {serviceLabels[key] || key}
                </CardTitle>
                <Icon className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <Badge variant="outline" className={statusColor(status)}>
                  {status}
                </Badge>
              </CardContent>
            </Card>
          );
        })}

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Tài liệu</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{data?.active_docs ?? 0}</div>
            <p className="text-xs text-muted-foreground">
              {data?.total_docs ?? 0} tổng cộng
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
