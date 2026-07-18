"use client";

import { useCallback, useEffect, useState } from "react";
import { Save } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, FieldContent, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Textarea } from "@/components/ui/textarea";
import { tenantsApi } from "@/lib/api-client";
import { formatDateTimeVN } from "@/lib/format";
import { TenantSettingUpdateRequestSchema } from "@/lib/schemas";
import type { TenantSetting, TenantSettingUpdateRequest } from "@/types/api";

type TenantSettingsFormProps =
  | {
      mode: "self";
      title?: string;
      description?: string;
      noCard?: boolean;
    }
  | {
      mode: "tenant";
      tenantId: string;
      title?: string;
      description?: string;
      noCard?: boolean;
    };

export function TenantSettingsForm(props: TenantSettingsFormProps) {
  const tenantId = props.mode === "tenant" ? props.tenantId : null;
  const [setting, setSetting] = useState<TenantSetting | null>(null);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState<TenantSettingUpdateRequest>({
    system_instruction: "",
  });

  const loadSetting = useCallback(async () => {
    try {
      setLoading(true);
      const result =
        props.mode === "self" ? await tenantsApi.getMySettings() : await tenantsApi.getSettings(tenantId as string);

      setSetting(result);
      setForm({
        system_instruction: result.system_instruction,
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : "Không thể tải cấu hình tenant";
      toast.error(message);
    } finally {
      setLoading(false);
    }
  }, [props.mode, tenantId]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadSetting();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadSetting]);

  const handleSave = useCallback(async () => {
    try {
      setSaving(true);
      const payload: TenantSettingUpdateRequest = {
        system_instruction: form.system_instruction?.trim() || undefined,
      };

      const parsedPayload = TenantSettingUpdateRequestSchema.safeParse(payload);
      if (!parsedPayload.success) {
        toast.error("Nội dung instruction không hợp lệ");
        return;
      }

      const result =
        props.mode === "self"
          ? await tenantsApi.updateMySettings(parsedPayload.data)
          : await tenantsApi.updateSettings(tenantId as string, parsedPayload.data);

      setSetting(result);
      setForm({
        system_instruction: result.system_instruction,
      });
      toast.success("Đã lưu cấu hình tenant");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Không thể lưu cấu hình tenant";
      toast.error(message);
    } finally {
      setSaving(false);
    }
  }, [form, props.mode, tenantId]);

  const content = loading ? (
    <div className="text-sm text-muted-foreground">Đang tải cấu hình...</div>
  ) : (
    <>
      <FieldGroup>
        <Field>
          <FieldContent>
            <FieldLabel htmlFor="system_instruction">Instruction tenant</FieldLabel>
            <Textarea
              id="system_instruction"
              value={form.system_instruction || ""}
              onChange={(event) => setForm((current) => ({ ...current, system_instruction: event.target.value }))}
              placeholder="Mô tả cách AI nên trả lời cho tenant này..."
              rows={10}
            />
            <FieldDescription>
              Nội dung này sẽ được ghép vào system instruction của chatbot trong phạm vi tenant hiện tại.
            </FieldDescription>
          </FieldContent>
        </Field>
      </FieldGroup>

      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>Cập nhật lần cuối: {formatDateTimeVN(setting?.updated_at)}</span>
        <Button onClick={handleSave} disabled={saving}>
          <Save className="mr-2 h-4 w-4" />
          {saving ? "Đang lưu..." : "Lưu cấu hình"}
        </Button>
      </div>
    </>
  );

  if (props.noCard) return content;

  return (
    <Card>
      <CardHeader>
        <CardTitle>{props.title || "Cấu hình chatbot"}</CardTitle>
        <CardDescription>
          {props.description || "Quản lý instruction riêng của tenant."}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">{content}</CardContent>
    </Card>
  );
}
