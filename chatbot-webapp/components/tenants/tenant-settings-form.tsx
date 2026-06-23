"use client";

import { useCallback, useEffect, useState } from "react";
import { Save } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, FieldContent, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { tenantsApi } from "@/lib/api-client";
import { formatDateTimeVN } from "@/lib/format";
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
    chatbot_display_name: "",
    welcome_message: "",
    system_instruction: "",
  });

  const loadSetting = useCallback(async () => {
    try {
      setLoading(true);
      const result =
        props.mode === "self" ? await tenantsApi.getMySettings() : await tenantsApi.getSettings(tenantId as string);

      setSetting(result);
      setForm({
        chatbot_display_name: result.chatbot_display_name,
        welcome_message: result.welcome_message,
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
        chatbot_display_name: form.chatbot_display_name?.trim() || undefined,
        welcome_message: form.welcome_message?.trim() || undefined,
        system_instruction: form.system_instruction?.trim() || undefined,
      };

      const result =
        props.mode === "self"
          ? await tenantsApi.updateMySettings(payload)
          : await tenantsApi.updateSettings(tenantId as string, payload);

      setSetting(result);
      setForm({
        chatbot_display_name: result.chatbot_display_name,
        welcome_message: result.welcome_message,
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
            <FieldLabel htmlFor="chatbot_display_name">Tên chatbot</FieldLabel>
            <Input
              id="chatbot_display_name"
              value={form.chatbot_display_name || ""}
              onChange={(event) => setForm((current) => ({ ...current, chatbot_display_name: event.target.value }))}
              placeholder="Ví dụ: Trợ lý nội bộ Công ty A"
            />
          </FieldContent>
        </Field>

        <Field>
          <FieldContent>
            <FieldLabel htmlFor="welcome_message">Lời chào</FieldLabel>
            <Textarea
              id="welcome_message"
              value={form.welcome_message || ""}
              onChange={(event) => setForm((current) => ({ ...current, welcome_message: event.target.value }))}
              placeholder="Ví dụ: Xin chào, tôi có thể hỗ trợ gì cho anh/chị?"
              rows={3}
            />
          </FieldContent>
        </Field>

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
          {props.description || "Quản lý tên chatbot, lời chào và instruction riêng của tenant."}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">{content}</CardContent>
    </Card>
  );
}
