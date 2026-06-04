"use client";

import type { TenantItem } from "@/types/api";
import { cn } from "@/lib/utils";
import { Select, SelectContent, SelectItem, SelectTrigger } from "@/components/ui/select";

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
  const selectedTenant = tenants.find((tenant) => tenant.id === value) || null;
  const displayLabel = selectedTenant?.name || (includeAll && !value ? allLabel : placeholder);

  return (
    <Select
      value={value || (includeAll ? "__all__" : undefined)}
      onValueChange={(nextValue) => onValueChange(nextValue === "__all__" ? null : nextValue)}
      disabled={disabled}
    >
      <SelectTrigger className={cn("w-full", triggerClassName)}>
        <span className={cn("truncate text-left", !selectedTenant && !(includeAll && !value) && "text-muted-foreground")}>
          {displayLabel}
        </span>
      </SelectTrigger>
      <SelectContent className={className}>
        {includeAll ? <SelectItem value="__all__">{allLabel}</SelectItem> : null}
        {tenants.map((tenant) => (
          <SelectItem key={tenant.id} value={tenant.id}>
            {tenant.name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
