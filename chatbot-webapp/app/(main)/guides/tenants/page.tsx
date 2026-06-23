import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { CheckCircle2Icon, KeyIcon, UsersIcon } from "lucide-react";

export default function TenantsGuidePage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Quản lý Tenant & API Key</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Hướng dẫn tạo không gian làm việc (Workspace) cho khách hàng và cấp phát chìa khoá kết nối.
        </p>
      </div>

      <section className="space-y-4">
        <h2 className="text-lg font-semibold flex items-center gap-2">
          <UsersIcon className="w-5 h-5 text-primary" />
          Quy trình cấp phát Tenant mới
        </h2>
        
        <Accordion type="single" className="w-full">
          <AccordionItem value="step-1">
            <AccordionTrigger className="text-sm font-medium">Bước 1: Tạo Tenant mới</AccordionTrigger>
            <AccordionContent className="text-muted-foreground text-sm leading-6">
              <p>Chỉ <strong>Platform Admin</strong> mới có quyền tạo Tenant. Truy cập vào menu <code>Quản trị &gt; Tenant</code> và bấm <strong>Thêm mới</strong>.</p>
              <ul className="mt-3 space-y-2 list-disc pl-5">
                <li><strong>Tên Tenant:</strong> Tên công ty hoặc dự án (VD: Công ty TNHH ABC)</li>
                <li><strong>Slug:</strong> Chuỗi URL thân thiện viết liền không dấu (VD: <code>cong-ty-abc</code>). Hệ thống sẽ tự động tự tạo slug dựa trên tên khi bạn ấn phím cách (Space).</li>
              </ul>
            </AccordionContent>
          </AccordionItem>

          <AccordionItem value="step-2">
            <AccordionTrigger className="text-sm font-medium">Bước 2: Cấp Quota (Giới hạn tài nguyên)</AccordionTrigger>
            <AccordionContent className="text-muted-foreground text-sm leading-6">
              <p>Để đảm bảo công ty khách hàng không dùng lạm lố tài nguyên hệ thống (như Token AI, dung lượng ổ cứng), Platform Admin cần cấu hình <strong>Settings</strong> của Tenant đó.</p>
              <p className="mt-2">Bạn có thể cài đặt số lượng Token tối đa được dùng trong ngày, hoặc giới hạn băng thông truy cập. Nếu Tenant dùng vượt quá Quota, API sẽ báo lỗi <code>429 Too Many Requests</code>.</p>
            </AccordionContent>
          </AccordionItem>

          <AccordionItem value="step-3">
            <AccordionTrigger className="text-sm font-medium">Bước 3: Gán Tài khoản (Tenant Admin)</AccordionTrigger>
            <AccordionContent className="text-muted-foreground text-sm leading-6">
              <p>Mỗi Tenant cần có một người quản trị. Bạn vào menu <code>Người dùng</code>, tạo một tài khoản mới và chọn Role là <strong>Tenant Admin</strong>, sau đó chọn Tenant vừa tạo để gắn tài khoản này vào.</p>
              <p className="mt-2">Khi người đó đăng nhập, giao diện Menu Sidebar sẽ tự động đổi sang chế độ <strong>Tenant</strong>, ẩn đi toàn bộ các chức năng cấu hình hệ thống chuyên sâu.</p>
            </AccordionContent>
          </AccordionItem>
        </Accordion>
      </section>

      <section className="space-y-4 mt-8">
        <h2 className="text-lg font-semibold flex items-center gap-2">
          <KeyIcon className="w-5 h-5 text-amber-500" />
          Khái niệm về API Key
        </h2>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Chìa khoá giao tiếp vạn năng</CardTitle>
            <CardDescription className="text-xs">API Key dùng để chứng thực danh tính khi phần mềm gọi lệnh.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 text-sm text-slate-700 leading-6">
            <p>
              Thay vì bắt phần mềm của khách hàng phải gõ Tài khoản / Mật khẩu (rất dễ lộ và khó code), hệ thống sử dụng <strong>API Key</strong> (một chuỗi ký tự dài ngẫu nhiên).
            </p>
            <div className="bg-slate-100 p-4 rounded-lg flex items-center justify-between border border-slate-200">
              <code className="text-sm font-mono text-amber-600">trg_fkbZ8COIca3X9F7Kmp3Bw...</code>
              <Badge variant="outline">Chuẩn Token</Badge>
            </div>
            <ul className="space-y-3 mt-4">
              <li className="flex gap-3 items-start">
                <CheckCircle2Icon className="w-5 h-5 text-green-500 mt-1 shrink-0" />
                <span><strong>Bảo mật:</strong> Nếu bị lộ, Tenant Admin có thể vào Cài đặt xoá Key cũ đi và tạo ngay Key mới trong 1 giây. Không ảnh hưởng đến mật khẩu của tài khoản.</span>
              </li>
              <li className="flex gap-3 items-start">
                <CheckCircle2Icon className="w-5 h-5 text-green-500 mt-1 shrink-0" />
                <span><strong>Định danh ngầm:</strong> Hệ thống tự động nhận biết đoạn mã này thuộc về Công ty nào. Nên không cần truyền lên ID rắc rối.</span>
              </li>
            </ul>
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
