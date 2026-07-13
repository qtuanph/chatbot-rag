"use client";

import type { TenantItem } from "@/types/api";
import { cn } from "@/lib/utils";
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";

interface TenantSelectProps {
  tenants: TenantItem[];
  value?: string | null;
  onValueChange: (tenantId: string | null) => void;
  placeholder?: string;
  allLabel?: string;
  includeAll?: boolean;
  disabled?: boolean;
  className?: string;
  triggerClassName?: string;
}

export function TenantSelect({
  tenants,
  value,
  onValueChange,
  placeholder = "Chọn tenant",
  allLabel = "Tất cả tenant",
  includeAll = false,
  disabled = false,
  className,
  triggerClassName,
}: TenantSelectProps) {
  return (
    <NativeSelect
      value={value ?? ""}
      onChange={(e) => onValueChange(e.target.value || null)}
      disabled={disabled}
      className={cn(className, triggerClassName)}
    >
      {includeAll ? (
        <NativeSelectOption value="">{allLabel}</NativeSelectOption>
      ) : null}
      {tenants.map((tenant) => (
        <NativeSelectOption key={tenant.id} value={tenant.id}>
          {tenant.name}
        </NativeSelectOption>
      ))}
    </NativeSelect>
  );
}
