"use client";

import { useCallback, useEffect, useState } from "react";
import { FaqManager } from "@/components/faqs/faq-manager";
import { tenantsApi } from "@/lib/api-client";
import type { TenantItem } from "@/types/api";

export default function AdminFaqsPage() {
  const [tenants, setTenants] = useState<TenantItem[]>([]);

  const loadTenants = useCallback(async () => {
    try {
      const rows = await tenantsApi.list();
      setTenants(rows);
    } catch (err) {
      console.error("Không thể tải danh sách công ty", err);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadTenants();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadTenants]);

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-6 p-6">
      <FaqManager tenantOptions={tenants} />
    </div>
  );
}
