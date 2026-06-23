"use client";

import { useCallback, useEffect, useState } from "react";

import { tenantsApi } from "@/lib/api-client";
import type { TenantItem } from "@/types/api";
import { DocumentCatalog } from "@/components/documents/document-catalog";

export default function AdminDocumentsPage() {
  const [tenants, setTenants] = useState<TenantItem[]>([]);
  const [selectedTenantId, setSelectedTenantId] = useState<string>("");

  const loadTenants = useCallback(async () => {
    const rows = await tenantsApi.list();
    setTenants(rows);
    setSelectedTenantId((current) => (current && rows.some((tenant) => tenant.id === current) ? current : ""));
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
        <h1 className="text-2xl font-bold">Quản lý tài liệu</h1>
        <p className="text-sm text-muted-foreground">Anh có thể xem toàn bộ tenant hoặc khóa vào một tenant cụ thể. Khi upload, hệ thống sẽ chỉ cho phép thao tác khi đã chọn đúng tenant.</p>
      </div>
      <DocumentCatalog
        tenantOptions={tenants}
        selectedTenantId={selectedTenantId}
        onSelectedTenantIdChange={setSelectedTenantId}
      />
    </div>
  );
}
