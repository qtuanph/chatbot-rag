import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { CheckCircle2Icon, KeyIcon, UsersIcon, ShieldAlertIcon } from "lucide-react";

export default function TenantsGuidePage() {
  return (
    <div className="space-y-6 pb-12">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Quản lý Khách hàng & API Key</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Hệ thống được thiết kế theo chuẩn <strong>Multi-tenant</strong>. Mỗi Tenant tương đương với một Công ty/Tổ chức độc lập.
        </p>
      </div>

      <section className="space-y-4 mt-6">
        <h2 className="text-xl font-semibold flex items-center gap-2 border-b pb-2">
          <UsersIcon className="w-5 h-5 text-primary" />
          Hướng dẫn Tạo Tenant (Cho BA / Sales)
        </h2>
        
        <Accordion className="w-full bg-white rounded-lg border">
          <AccordionItem value="step-1" className="px-4">
            <AccordionTrigger className="text-base font-semibold hover:text-primary">
              Bước 1: Khởi tạo Workspace cho khách hàng
            </AccordionTrigger>
            <AccordionContent className="text-slate-700 text-sm leading-6 space-y-2">
              <p>Chỉ <strong>Platform Admin</strong> (Chủ hệ thống) mới có quyền tạo Tenant. Thực hiện như sau:</p>
              <ul className="list-disc pl-5 space-y-1">
                <li>Truy cập vào menu <strong>Quản trị &gt; Tenants</strong> ở thanh bên trái.</li>
                <li>Bấm nút <strong>+ Thêm mới</strong> ở góc phải trên cùng.</li>
                <li>Nhập <strong>Tên Tenant</strong> (VD: Công ty TNHH Bất động sản ABC).</li>
                <li>Phần <strong>Slug</strong> hệ thống sẽ tự động tạo ra một chuỗi viết liền không dấu để làm định danh chuẩn (VD: <code>cong-ty-tnhh-bat-dong-san-abc</code>). Bạn có thể sửa lại cho ngắn gọn tuỳ ý.</li>
              </ul>
            </AccordionContent>
          </AccordionItem>

          <AccordionItem value="step-2" className="px-4">
            <AccordionTrigger className="text-base font-semibold hover:text-primary">
              Bước 2: Cấp Quota (Giới hạn tài nguyên)
            </AccordionTrigger>
            <AccordionContent className="text-slate-700 text-sm leading-6 space-y-2">
              <p>Để tránh việc công ty khách hàng sử dụng lạm lố băng thông API hoặc nhét quá nhiều file rác vào Vector Database, bạn cần thiết lập giới hạn:</p>
              <ul className="list-disc pl-5 space-y-1">
                <li>Mở Tenant vừa tạo, chuyển sang tab <strong>Settings (Cài đặt)</strong>.</li>
                <li>Thiết lập số lượng Token AI tối đa mỗi ngày.</li>
                <li>Thiết lập dung lượng Upload tối đa.</li>
                <li><em>(Nếu khách hàng xài quá mức, API của họ sẽ tự động văng lỗi <code>429 Too Many Requests</code>).</em></li>
              </ul>
            </AccordionContent>
          </AccordionItem>

          <AccordionItem value="step-3" className="px-4 border-b-0">
            <AccordionTrigger className="text-base font-semibold hover:text-primary">
              Bước 3: Gắn Tài khoản Quản trị cho khách (Tenant Admin)
            </AccordionTrigger>
            <AccordionContent className="text-slate-700 text-sm leading-6 space-y-2">
              <p>Sau khi có &quot;Không gian&quot; (Tenant), bạn phải giao chìa khoá cho một người dùng để họ quản lý không gian đó:</p>
              <ul className="list-disc pl-5 space-y-1">
                <li>Truy cập menu <strong>Quản trị &gt; Users (Người dùng)</strong>.</li>
                <li>Tạo một tài khoản (Email, Password) cho khách.</li>
                <li>Ở ô Role (Quyền hạn), chọn là <strong>Tenant Admin</strong>.</li>
                <li>Hệ thống sẽ hiện ra một ô chọn Tenant. Lúc này, bạn chỉ định tài khoản này thuộc về công ty <em>&quot;Công ty TNHH Bất động sản ABC&quot;</em>.</li>
              </ul>
              <div className="bg-emerald-50 text-emerald-800 p-3 rounded mt-2 flex items-start gap-2">
                <CheckCircle2Icon className="w-5 h-5 shrink-0 mt-0.5" />
                <p>Khi người khách này đăng nhập, giao diện Menu Sidebar sẽ tự động <strong>chuyển sang màu khác</strong> và ẩn đi toàn bộ các chức năng &quot;Quản trị hệ thống&quot;. Họ chỉ nhìn thấy mục Quản lý Tài liệu và API Keys của riêng họ!</p>
              </div>
            </AccordionContent>
          </AccordionItem>
        </Accordion>
      </section>

      <section className="space-y-4 mt-8">
        <h2 className="text-xl font-semibold flex items-center gap-2 border-b pb-2">
          <KeyIcon className="w-5 h-5 text-amber-500" />
          API Key (Dành cho Dev của khách hàng)
        </h2>
        <Card className="shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-lg">Chìa khoá kết nối vạn năng</CardTitle>
            <CardDescription>Tại sao phải dùng API Key thay vì Tài khoản / Mật khẩu?</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 text-sm text-slate-700 leading-6">
            <p>
              Khi đội Dev của khách hàng muốn viết code (Python, Node.js, C#) để lấy Chatbot nhúng vào app điện thoại của họ, họ KHÔNG THỂ gửi kèm Tên đăng nhập và Mật khẩu trong mã nguồn vì cực kỳ rủi ro lộ lọt.
            </p>
            <p>
              Thay vào đó, <strong>Tenant Admin</strong> sẽ vào màn hình <code>API Keys</code>, bấm nút <strong>+ Tạo Key mới</strong>.
            </p>
            <div className="bg-slate-950 p-4 rounded-lg flex flex-col gap-2">
              <span className="text-slate-400 text-xs">Mã API Key (Chỉ hiển thị 1 lần duy nhất)</span>
              <code className="text-base font-mono text-emerald-400">trg_fkbZ8COIca3X9F7Kmp3Bw...</code>
            </div>
            
            <h3 className="font-semibold text-base mt-6 mb-2">Ưu điểm của API Key:</h3>
            <ul className="space-y-3">
              <li className="flex gap-3 items-start">
                <ShieldAlertIcon className="w-5 h-5 text-indigo-500 mt-1 shrink-0" />
                <span><strong>Định danh ngầm (Auto-routing):</strong> Server đọc mã Key `trg_fkb...` là biết ngay request này gọi từ Công ty Bất động sản ABC. Mọi vector search, RAG, trừ tiền Token đều tự động được tính cho công ty ABC mà Dev không cần truyền lên ID rườm rà.</span>
              </li>
              <li className="flex gap-3 items-start">
                <ShieldAlertIcon className="w-5 h-5 text-indigo-500 mt-1 shrink-0" />
                <span><strong>Xoá dấu vết (Revoke):</strong> Nếu vô tình ông Dev làm lộ Key lên Github, ông Tenant Admin chỉ việc bấm nút Thùng rác để xoá Key đó đi và tạo Key khác trong 1 giây. Không ảnh hưởng gì đến mật khẩu đăng nhập của ông Admin.</span>
              </li>
            </ul>
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
