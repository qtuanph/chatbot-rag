"use client";

import { useCallback, useEffect, useState } from "react";

import { DocumentCatalog } from "@/components/documents/document-catalog";
import { tenantsApi } from "@/lib/api-client";
import type { TenantItem } from "@/types/api";

export default function AdminDocumentsPage() {
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
      <div>
        <h1 className="text-2xl font-bold">Quản lý tài liệu dùng chung (Knowledge Base)</h1>
        <p className="text-sm text-muted-foreground">
          Upload tài liệu dùng chung lên hệ thống, sau đó phân quyền cho từng công ty (Tenant) được phép tra cứu thông tin. Vector được lưu duy nhất 1 lần.
        </p>
      </div>
      <DocumentCatalog tenantOptions={tenants} />
    </div>
  );
}
