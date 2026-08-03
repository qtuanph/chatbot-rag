"use client";

import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { CheckCircle2Icon, KeyIcon, UsersIcon, ShieldAlertIcon, SettingsIcon, UserCheckIcon, Building2Icon, SparklesIcon, FilterIcon } from "lucide-react";

export default function TenantsGuidePage() {
  return (
    <div className="space-y-8 pb-16 max-w-4xl">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-foreground">Quản lý Tenant &amp; Phân quyền Đa Doanh nghiệp</h1>
        <p className="text-sm text-muted-foreground mt-2">
          Cơ chế cô lập đa người dùng (Multi-tenant Security Boundary), quản lý API Key và phân quyền FAQ theo từng công ty.
        </p>
      </div>

      {/* Guide Steps */}
      <section className="space-y-4">
        <h2 className="text-xl font-bold text-foreground flex items-center gap-2 border-b pb-2">
          <UsersIcon className="w-5 h-5 text-primary" />
          1. Quy trình thiết lập cho Platform Admin &amp; Tenant Admin
        </h2>

        <div className="space-y-3">
          {/* Step 1 */}
          <Accordion multiple className="border border-border rounded-xl shadow-sm bg-card">
            <AccordionItem value="step-1">
              <AccordionTrigger className="px-5 hover:no-underline font-semibold text-foreground text-sm">
                <div className="flex items-center gap-3">
                  <span className="w-6 h-6 rounded-full bg-primary text-primary-foreground text-xs font-bold flex items-center justify-center shrink-0">1</span>
                  Khởi tạo Tenant (Công ty / Khách hàng)
                </div>
              </AccordionTrigger>
              <AccordionContent className="px-5 pb-5 text-muted-foreground text-xs leading-relaxed space-y-2">
                <p>Chỉ tài khoản <strong>Platform Admin</strong> mới có quyền tạo mới Tenant:</p>
                <ul className="list-disc pl-4 space-y-1">
                  <li>Truy cập menu <code className="bg-muted px-1.5 py-0.5 rounded text-foreground">Quản lý Công ty (Tenants)</code> ở sidebar phía trái.</li>
                  <li>Bấm nút <strong>Tạo mới Tenant</strong> ở góc trên bên phải.</li>
                  <li>Nhập <strong>Tên Công ty</strong> (Ví dụ: <code>CÔNG TY CỔ PHẦN SSE ERP</code>).</li>
                  <li>Nhập <strong>Slug</strong> (Mã định danh duy nhất viết liền không dấu, ví dụ: <code>sse-erp</code>).</li>
                </ul>
              </AccordionContent>
            </AccordionItem>
          </Accordion>

          {/* Step 2 */}
          <Accordion multiple className="border border-border rounded-xl shadow-sm bg-card">
            <AccordionItem value="step-2">
              <AccordionTrigger className="px-5 hover:no-underline font-semibold text-foreground text-sm">
                <div className="flex items-center gap-3">
                  <span className="w-6 h-6 rounded-full bg-primary text-primary-foreground text-xs font-bold flex items-center justify-center shrink-0">2</span>
                  Phân quyền Tài liệu cho Tenant (Document Access Grant)
                </div>
              </AccordionTrigger>
              <AccordionContent className="px-5 pb-5 text-muted-foreground text-xs leading-relaxed space-y-2">
                <p>Một tài liệu trong Kho tài liệu chỉ phục vụ cho Tenant khi được gán quyền:</p>
                <ul className="list-disc pl-4 space-y-1">
                  <li>Vào trang <code className="bg-muted px-1.5 py-0.5 rounded text-foreground">Kho Tài liệu</code> ➔ Chọn tài liệu cần gán.</li>
                  <li>Chọn Tenant được phép truy cập tài liệu này.</li>
                  <li>Nếu Tenant chưa được phân quyền tài liệu nào, hệ thống AI sẽ kích hoạt <strong>Strict Empty Context Guardrail</strong> để bảo đảm không trả lời sai hay dùng kiến thức ngoài internet.</li>
                </ul>
              </AccordionContent>
            </AccordionItem>
          </Accordion>

          {/* Step 3 */}
          <Accordion multiple className="border border-border rounded-xl shadow-sm bg-card">
            <AccordionItem value="step-3">
              <AccordionTrigger className="px-5 hover:no-underline font-semibold text-foreground text-sm">
                <div className="flex items-center gap-3">
                  <span className="w-6 h-6 rounded-full bg-primary text-primary-foreground text-xs font-bold flex items-center justify-center shrink-0">3</span>
                  Áp dụng FAQ cho Nhiều Công ty (Multi-Tenant FAQ Grid)
                </div>
              </AccordionTrigger>
              <AccordionContent className="px-5 pb-5 text-muted-foreground text-xs leading-relaxed space-y-2">
                <p>Tối ưu hóa quản lý câu hỏi thường gặp cho hệ thống nhiều công ty:</p>
                <ul className="list-disc pl-4 space-y-1">
                  <li>Vào mục <code className="bg-muted px-1.5 py-0.5 rounded text-foreground">Nhật ký Hỏi &amp; Đáp</code> hoặc <code className="bg-muted px-1.5 py-0.5 rounded text-foreground">Quản lý FAQ</code>.</li>
                  <li>Khi tạo FAQ mới hoặc bấm <strong>Sparkles Tạo FAQ từ AI</strong>, hệ thống hiển thị lưới danh sách tích chọn Công ty (Multi-Tenant Grid).</li>
                  <li>Admin có thể tích chọn 1 hoặc nhiều Công ty cùng lúc để áp dụng bộ FAQ này đồng thời.</li>
                </ul>
              </AccordionContent>
            </AccordionItem>
          </Accordion>
        </div>
      </section>

      {/* API Key section */}
      <section className="space-y-4">
        <h2 className="text-xl font-bold text-foreground flex items-center gap-2 border-b pb-2">
          <KeyIcon className="w-5 h-5 text-primary" />
          2. API Key (Xác thực Chìa khóa kết nối)
        </h2>

        <div className="border border-border rounded-xl p-5 bg-card space-y-4">
          <div className="text-sm text-muted-foreground leading-relaxed space-y-3">
            <p>
              Để nhúng chatbot vào phần mềm ERP, CRM hoặc Website khách hàng, ứng dụng sẽ gọi API kèm theo <strong>Tenant API Key</strong> trong HTTP Header: <code>Authorization: Bearer trg_...</code>
            </p>
          </div>

          <div className="bg-zinc-950 dark:bg-zinc-900 p-4 rounded-xl flex flex-col gap-1 border border-border">
            <span className="text-zinc-500 text-[10px] uppercase font-semibold font-sans">API Key format (Bảo mật Hash DB)</span>
            <code className="text-xs font-mono text-emerald-400">trg_3210J-qApeNar4P5GwAxBMFNrF8XVyDjkVBSLlj8jLg</code>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
            <div className="border border-border rounded-lg p-4 bg-muted/20 space-y-2">
              <div className="flex items-center gap-2">
                <ShieldAlertIcon className="w-4 h-4 text-primary" />
                <h4 className="font-bold text-xs text-foreground">Định tuyến an toàn (Key Hash Lookup)</h4>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Backend chỉ lưu SHA-256 hash của Key trong database. Khi nhận request, hệ thống giải mã hash để xác định <code>tenant_id</code> và tự động lọc dữ liệu đúng phạm vi.
              </p>
            </div>

            <div className="border border-border rounded-lg p-4 bg-muted/20 space-y-2">
              <div className="flex items-center gap-2">
                <SettingsIcon className="w-4 h-4 text-primary" />
                <h4 className="font-bold text-xs text-foreground">Thu hồi khẩn cấp (Revoke)</h4>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Nếu một API Key bị lộ, Tenant Admin chỉ cần nhấn nút Thu hồi (Revoke). Key đó sẽ lập tức bị vô hiệu hóa tức thì mà không ảnh hưởng tới các Key khác.
              </p>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
