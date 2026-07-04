"use client";

import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { CheckCircle2Icon, KeyIcon, UsersIcon, ShieldAlertIcon, SettingsIcon, UserCheckIcon } from "lucide-react";

export default function TenantsGuidePage() {
  return (
    <div className="space-y-8 pb-16 max-w-4xl">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-foreground">Quản lý Tenant &amp; API Key</h1>
        <p className="text-sm text-muted-foreground mt-2">
          Tìm hiểu cơ chế đa người dùng (Multi-tenant) và cách cấp phát khóa kết nối API.
        </p>
      </div>

      {/* Guide Steps - Separate Accordions to avoid nested card boxing */}
      <section className="space-y-4">
        <h2 className="text-xl font-bold text-foreground flex items-center gap-2 border-b pb-2">
          <UsersIcon className="w-5 h-5 text-primary" />
          Hướng dẫn thiết lập cho Platform Admin
        </h2>

        <div className="space-y-3">
          {/* Step 1 */}
          <Accordion multiple className="border border-border rounded-xl shadow-sm bg-card">
            <AccordionItem value="step-1">
              <AccordionTrigger className="px-5 hover:no-underline font-semibold text-foreground text-sm">
                <div className="flex items-center gap-3">
                  <span className="w-6 h-6 rounded-full bg-primary text-primary-foreground text-xs font-bold flex items-center justify-center shrink-0">1</span>
                  Khởi tạo Tenant (Doanh nghiệp)
                </div>
              </AccordionTrigger>
              <AccordionContent className="px-5 pb-5 text-muted-foreground text-xs leading-relaxed space-y-2">
                <p>Chỉ tài khoản <strong>Platform Admin</strong> mới có quyền tạo mới Tenant:</p>
                <ul className="list-disc pl-4 space-y-1">
                  <li>Truy cập menu <code className="bg-muted px-1.5 py-0.5 rounded text-foreground">Tenant</code> ở mục quản trị phía trái.</li>
                  <li>Bấm nút <strong>Tạo mới</strong> ở góc trên bên phải.</li>
                  <li>Nhập <strong>Tên Tenant</strong> (Ví dụ: <code>Tổng công ty ABC</code>).</li>
                  <li>Nhập <strong>Slug</strong> (Mã định danh viết liền không dấu, dùng để mapping dữ liệu).</li>
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
                  Thiết lập hạn ngạch sử dụng (Quota)
                </div>
              </AccordionTrigger>
              <AccordionContent className="px-5 pb-5 text-muted-foreground text-xs leading-relaxed space-y-2">
                <p>Mỗi Tenant cần được giới hạn tài nguyên để bảo vệ hạ tầng chung:</p>
                <ul className="list-disc pl-4 space-y-1">
                  <li><strong>Monthly Token Quota:</strong> Số lượng token tối đa LLM được sử dụng mỗi tháng.</li>
                  <li><strong>Monthly Request Quota:</strong> Số lượt gọi API tối đa mỗi tháng.</li>
                  <li><strong>Rate Limit RPM:</strong> Tốc độ gọi tối đa (Requests Per Minute). Khi vượt quá, hệ thống trả về lỗi <code className="text-destructive font-mono">429 Too Many Requests</code>.</li>
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
                  Cấp tài khoản Tenant Admin
                </div>
              </AccordionTrigger>
              <AccordionContent className="px-5 pb-5 text-muted-foreground text-xs leading-relaxed space-y-2">
                <p>Giao quyền quản lý Tenant cho khách hàng:</p>
                <ul className="list-disc pl-4 space-y-1">
                  <li>Vào mục <code className="bg-muted px-1.5 py-0.5 rounded text-foreground">Người dùng</code>.</li>
                  <li>Tạo tài khoản mới với vai trò là <strong>Tenant Admin</strong>.</li>
                  <li>Liên kết tài khoản này với Tenant tương ứng đã tạo ở bước 1.</li>
                </ul>
                <div className="bg-accent text-accent-foreground p-3 rounded-lg mt-2 flex items-start gap-2 text-xs border border-border">
                  <UserCheckIcon className="w-4 h-4 shrink-0 mt-0.5" />
                  <div>
                    <strong>Tự động phân quyền:</strong> Khi Tenant Admin đăng nhập, họ chỉ có thể quản lý tài liệu, cài đặt chatbot, và sinh API Key thuộc về Tenant đó. Họ hoàn toàn bị cô lập khỏi dữ liệu của Tenant khác.
                  </div>
                </div>
              </AccordionContent>
            </AccordionItem>
          </Accordion>
        </div>
      </section>

      {/* API Key section */}
      <section className="space-y-4">
        <h2 className="text-xl font-bold text-foreground flex items-center gap-2 border-b pb-2">
          <KeyIcon className="w-5 h-5 text-primary" />
          API Key (Chìa khóa kết nối)
        </h2>

        <div className="border border-border rounded-xl p-5 bg-card space-y-4">
          <div className="text-sm text-muted-foreground leading-relaxed space-y-3">
            <p>
              Khi muốn tích hợp chatbot vào các phần mềm bên ngoài (ví dụ như ERP, CRM, mobile app), bạn không dùng tài khoản/mật khẩu thông thường vì lý do bảo mật. Thay vào đó, bạn sử dụng <strong>API Key</strong>.
            </p>
            <p>
              Tenant Admin có thể tạo nhiều API Key khác nhau trong phần <strong>Cấu hình Tenant</strong>. Các key này có prefix là <code>trg_</code> để phân biệt:
            </p>
          </div>

          <div className="bg-zinc-950 dark:bg-zinc-900 p-4 rounded-xl flex flex-col gap-1 border border-border">
            <span className="text-zinc-500 text-[10px] uppercase font-semibold font-sans">API Key format (Chỉ hiển thị 1 lần)</span>
            <code className="text-xs font-mono text-emerald-400">trg_fkbZ8COIca3X9F7Kmp3Bw9O52evXaFryFz...</code>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
            <div className="border border-border rounded-lg p-4 bg-muted/20 space-y-2">
              <div className="flex items-center gap-2">
                <ShieldAlertIcon className="w-4 h-4 text-primary" />
                <h4 className="font-bold text-xs text-foreground">Tự động định tuyến (Auto-routing)</h4>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Hệ thống lưu hash của API Key trong DB. Khi có request gửi lên, hệ thống tự động giải mã để biết request thuộc về Tenant nào và áp dụng đúng cấu hình, tài liệu RAG của Tenant đó.
              </p>
            </div>

            <div className="border border-border rounded-lg p-4 bg-muted/20 space-y-2">
              <div className="flex items-center gap-2">
                <SettingsIcon className="w-4 h-4 text-primary" />
                <h4 className="font-bold text-xs text-foreground">Thu hồi dễ dàng (Revoke)</h4>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Nếu một API Key bị lộ hoặc không còn sử dụng, Tenant Admin chỉ cần nhấn nút Thu hồi (Revoke). Key đó sẽ lập tức bị vô hiệu hóa mà không ảnh hưởng đến các key khác hay tài khoản đăng nhập.
              </p>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
