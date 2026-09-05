"use client";

import { useMemo } from "react";
import type { TenantItem } from "@/types/api";
import { cn } from "@/lib/utils";
import {
  Combobox,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxInput,
  ComboboxItem,
  ComboboxList,
} from "@/components/ui/combobox";

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

interface TenantOption {
  value: string;
  label: string;
}

export function TenantSelect({
  tenants,
  value,
  onValueChange,
  placeholder = "Tìm kiếm hoặc chọn tenant...",
  allLabel = "Tất cả công ty (Tenants)",
  includeAll = false,
  disabled = false,
  className,
  triggerClassName,
}: TenantSelectProps) {
  const items: TenantOption[] = useMemo(() => {
    const list = tenants.map((t) => ({ value: t.id, label: t.name }));
    if (includeAll) {
      return [{ value: "ALL", label: allLabel }, ...list];
    }
    return list;
  }, [tenants, includeAll, allLabel]);

  const selectedItem = useMemo(() => {
    if (!value) return null;
    return items.find((i) => i.value === value) ?? null;
  }, [items, value]);

  return (
    <Combobox
      items={items}
      value={selectedItem}
      onValueChange={(item: TenantOption | null) => {
        if (!item || item.value === "ALL" || !item.value) {
          onValueChange(null);
        } else {
          onValueChange(item.value);
        }
      }}
      disabled={disabled}
    >
      <ComboboxInput
        placeholder={placeholder}
        className={cn("h-9 rounded-xl", className, triggerClassName)}
        showClear={!!value}
      />
      <ComboboxContent>
        <ComboboxEmpty>Không tìm thấy công ty nào</ComboboxEmpty>
        <ComboboxList>
          {(item: TenantOption) => (
            <ComboboxItem key={item.value} value={item}>
              {item.label}
            </ComboboxItem>
          )}
        </ComboboxList>
      </ComboboxContent>
    </Combobox>
  );
}
