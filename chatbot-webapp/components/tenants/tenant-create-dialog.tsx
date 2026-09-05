"use client";

import { useState } from "react";
import { ChevronLeft, ChevronRight, Plus } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { StepBar, type StepItem } from "@/components/ui/stepper";
import { Textarea } from "@/components/ui/textarea";
import { tenantsApi } from "@/lib/api-client";
import { TenantCreateRequestSchema } from "@/lib/schemas";
import type { TenantCreateRequest, TenantItem } from "@/types/api";

const CREATE_TENANT_STEPS: StepItem[] = [
  { title: "Thông tin cơ bản", description: "Tên & nhận diện" },
  { title: "Hạn ngạch & CORS", description: "RPM, Tokens, Domain" },
  { title: "Quản trị viên", description: "Admin & Xác nhận" },
];

const EMPTY_FORM: TenantCreateRequest = {
  name: "",
  slug: "",
  description: "",
  rate_limit_rpm: 60,
  allowed_origins: [],
};

function parseAllowedOriginsDraft(draft: string): string[] {
  return draft.split(/\r?\n/).map((item) => item.trim()).filter(Boolean);
}

interface TenantCreateDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess: (newTenant: TenantItem, adminAccount?: { username: string; password: string }) => void;
}

export function TenantCreateDialog({ open, onOpenChange, onSuccess }: TenantCreateDialogProps) {
  const [step, setStep] = useState(1);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState<TenantCreateRequest>({ ...EMPTY_FORM, allowed_origins: [] });
  const [allowedOriginsDraft, setAllowedOriginsDraft] = useState("");
  const [adminUsername, setAdminUsername] = useState("");
  const [adminPassword, setAdminPassword] = useState("");

  const resetForm = () => {
    setForm({ ...EMPTY_FORM, allowed_origins: [] });
    setAllowedOriginsDraft("");
    setAdminUsername("");
    setAdminPassword("");
    setStep(1);
  };

  const handleOpenChange = (nextOpen: boolean) => {
    if (!nextOpen) resetForm();
    onOpenChange(nextOpen);
  };

  const handleNextStep = () => {
    if (step === 1) {
      if (!form.name.trim()) {
        toast.error("Vui lòng nhập tên tenant");
        return;
      }
    }
    setStep((prev) => Math.min(prev + 1, 3));
  };

  const handlePrevStep = () => {
    setStep((prev) => Math.max(prev - 1, 1));
  };

  const handleCreate = async () => {
    try {
      setSaving(true);
      const payload: TenantCreateRequest = {
        ...form,
        allowed_origins: parseAllowedOriginsDraft(allowedOriginsDraft),
        admin_username: adminUsername.trim() || undefined,
        admin_password: adminPassword || undefined,
      };

      const parsedPayload = TenantCreateRequestSchema.safeParse(payload);
      if (!parsedPayload.success) {
        toast.error("Dữ liệu tenant không hợp lệ");
        return;
      }

      const created = await tenantsApi.create(parsedPayload.data);
      const adminAcc =
        adminUsername.trim() && adminPassword
          ? { username: adminUsername.trim(), password: adminPassword }
          : undefined;

      toast.success("Đã tạo tenant mới thành công");
      handleOpenChange(false);
      onSuccess(created, adminAcc);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Không thể tạo tenant";
      toast.error(message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="w-full sm:max-w-xl max-h-[85vh] flex flex-col p-0 gap-0 overflow-hidden">
        <DialogHeader className="shrink-0 px-6 pt-5 pb-3 border-b">
          <DialogTitle>Tạo tenant mới</DialogTitle>
        </DialogHeader>

        {/* Stepper Navigation */}
        <div className="px-6 py-3.5 bg-muted/20 border-b">
          <StepBar
            steps={CREATE_TENANT_STEPS}
            activeStep={step}
            onStepClick={(targetStep: number) => {
              if (step === 1 && !form.name.trim() && targetStep > 1) {
                toast.error("Vui lòng nhập tên tenant trước");
                return;
              }
              setStep(targetStep);
            }}
          />
        </div>

        <div className="flex-1 min-h-0 overflow-y-auto px-6 py-5">
          {/* ── BƯỚC 1: THÔNG TIN CƠ BẢN ── */}
          {step === 1 && (
            <FieldGroup className="space-y-4">
              <Field>
                <FieldLabel>Tên tenant *</FieldLabel>
                <Input
                  value={form.name}
                  onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))}
                  placeholder="Công ty Cổ phần Mẫu"
                  autoFocus
                />
                <FieldDescription>Tên tổ chức hoặc doanh nghiệp đại diện.</FieldDescription>
              </Field>
              <Field>
                <FieldLabel>Mã định danh (Slug)</FieldLabel>
                <Input
                  value={form.slug || ""}
                  onChange={(e) => setForm((prev) => ({ ...prev, slug: e.target.value }))}
                  placeholder="mau-company (để trống backend tự sinh)"
                />
                <FieldDescription>Dùng cho đường dẫn URL và phân quyền API.</FieldDescription>
              </Field>
              <Field>
                <FieldLabel>Mô tả</FieldLabel>
                <Textarea
                  value={form.description || ""}
                  onChange={(e) => setForm((prev) => ({ ...prev, description: e.target.value }))}
                  placeholder="Mô tả phạm vi hoạt động của tenant..."
                  className="min-h-[85px]"
                />
              </Field>
            </FieldGroup>
          )}

          {/* ── BƯỚC 2: HẠN NGẠCH & CORS ── */}
          {step === 2 && (
            <FieldGroup className="space-y-4">
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                <Field>
                  <FieldLabel>Rate limit (RPM)</FieldLabel>
                  <Input
                    type="number"
                    value={form.rate_limit_rpm ?? 60}
                    onChange={(e) =>
                      setForm((prev) => ({ ...prev, rate_limit_rpm: Number(e.target.value) }))
                    }
                  />
                </Field>
                <Field>
                  <FieldLabel>Quota request</FieldLabel>
                  <Input
                    type="number"
                    value={form.monthly_request_quota ?? ""}
                    onChange={(e) =>
                      setForm((prev) => ({
                        ...prev,
                        monthly_request_quota: e.target.value ? Number(e.target.value) : undefined,
                      }))
                    }
                    placeholder="0 = không giới hạn"
                  />
                </Field>
                <Field>
                  <FieldLabel>Quota token</FieldLabel>
                  <Input
                    type="number"
                    value={form.monthly_token_quota ?? ""}
                    onChange={(e) =>
                      setForm((prev) => ({
                        ...prev,
                        monthly_token_quota: e.target.value ? Number(e.target.value) : undefined,
                      }))
                    }
                    placeholder="0 = không giới hạn"
                  />
                </Field>
              </div>
              <Field>
                <FieldLabel>Allowed origins (CORS domain)</FieldLabel>
                <Textarea
                  value={allowedOriginsDraft}
                  onChange={(e) => setAllowedOriginsDraft(e.target.value)}
                  placeholder={"https://app.example.com\nhttps://portal.example.com"}
                  className="min-h-[90px]"
                />
                <FieldDescription>Mỗi dòng một domain cho phép widget chatbot nhúng vào.</FieldDescription>
              </Field>
            </FieldGroup>
          )}

          {/* ── BƯỚC 3: QUẢN TRỊ VIÊN & XÁC NHẬN ── */}
          {step === 3 && (
            <div className="space-y-5">
              <div className="rounded-xl border bg-muted/20 p-4 space-y-2.5">
                <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Tóm tắt thông tin Tenant
                </div>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div>
                    <span className="text-muted-foreground">Tên:</span>{" "}
                    <span className="font-medium text-foreground">{form.name || "—"}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Slug:</span>{" "}
                    <span className="font-mono text-foreground">{form.slug || "(Tự sinh)"}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Rate limit:</span>{" "}
                    <span className="font-mono">{form.rate_limit_rpm ?? 60} RPM</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Origins:</span>{" "}
                    <span>{parseAllowedOriginsDraft(allowedOriginsDraft).length} domain</span>
                  </div>
                </div>
              </div>

              <div className="rounded-xl border p-4 space-y-3">
                <div>
                  <div className="text-sm font-semibold">Khởi tạo Quản trị viên Tenant</div>
                  <div className="text-xs text-muted-foreground">
                    Tùy chọn. Có thể để trống và khởi tạo sau trong màn hình chi tiết tenant.
                  </div>
                </div>
                <FieldGroup className="space-y-3">
                  <Field>
                    <FieldLabel>Username Admin</FieldLabel>
                    <Input
                      value={adminUsername}
                      onChange={(e) => setAdminUsername(e.target.value)}
                      placeholder="admin_tenant"
                      className="h-8 text-xs"
                    />
                  </Field>
                  <Field>
                    <FieldLabel>Mật khẩu</FieldLabel>
                    <Input
                      type="password"
                      value={adminPassword}
                      onChange={(e) => setAdminPassword(e.target.value)}
                      placeholder="••••••••"
                      className="h-8 text-xs"
                    />
                  </Field>
                </FieldGroup>
              </div>
            </div>
          )}
        </div>

        {/* Footer điều hướng */}
        <DialogFooter className="shrink-0 px-6 py-3 border-t bg-muted/10 flex flex-row items-center justify-between sm:justify-between">
          {step > 1 ? (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handlePrevStep}
              disabled={saving}
            >
              <ChevronLeft className="mr-1 size-3.5" /> Quay lại
            </Button>
          ) : (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => handleOpenChange(false)}
            >
              Hủy
            </Button>
          )}

          {step < 3 ? (
            <Button type="button" size="sm" onClick={handleNextStep}>
              Tiếp tục <ChevronRight className="ml-1 size-3.5" />
            </Button>
          ) : (
            <Button size="sm" disabled={saving} onClick={handleCreate}>
              <Plus className="mr-1.5 size-3.5" /> {saving ? "Đang tạo..." : "Xác nhận tạo tenant"}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
