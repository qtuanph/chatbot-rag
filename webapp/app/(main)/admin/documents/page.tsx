"use client";

import { useCallback, useEffect, useState } from "react";

import { tenantsApi } from "@/lib/api-client";
import type { TenantItem } from "@/types/api";
import { DocumentCatalog } from "@/components/documents/document-catalog";
import { PageHeader } from "@/components/layout/page-header";

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
    <div className="mx-auto max-w-7xl space-y-6 p-6">
      <PageHeader
        title="Quản lý tài liệu tenant"
        description="Chọn tenant ngay trong trang này để upload, retry, rechunk và xóa tài liệu đúng phạm vi."
      />
      <DocumentCatalog
        title="Kho tài liệu đa tenant"
        description="Anh có thể xem toàn bộ tenant hoặc khóa vào một tenant cụ thể. Khi upload, hệ thống sẽ chỉ cho phép thao tác khi đã chọn đúng tenant."
        tenantOptions={tenants}
        selectedTenantId={selectedTenantId}
        onSelectedTenantIdChange={setSelectedTenantId}
      />
    </div>
  );
}
