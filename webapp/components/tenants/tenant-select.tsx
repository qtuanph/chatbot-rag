"use client";

import type { TenantItem } from "@/types/api";
import { cn } from "@/lib/utils";
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

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
  const items = {
    ...(includeAll ? { __all__: allLabel } : {}),
    ...Object.fromEntries(tenants.map((tenant) => [tenant.id, tenant.name] as const)),
  };

  return (
    <Select
      items={items}
      value={value || (includeAll ? "__all__" : undefined)}
      onValueChange={(nextValue) => onValueChange(nextValue === "__all__" ? null : nextValue)}
      disabled={disabled}
    >
      <SelectTrigger className={cn("w-full min-w-0", triggerClassName)}>
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent className={className}>
        <SelectGroup>
          {includeAll ? <SelectItem value="__all__">{allLabel}</SelectItem> : null}
          {tenants.map((tenant) => (
            <SelectItem key={tenant.id} value={tenant.id}>
              {tenant.name}
            </SelectItem>
          ))}
        </SelectGroup>
      </SelectContent>
    </Select>
  );
}
