import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { 
  Building2Icon, 
  DatabaseIcon, 
  BrainCircuitIcon, 
  ShieldCheckIcon,
  MessageSquareTextIcon,
  ArrowRightIcon,
  InfoIcon
} from "lucide-react";

export default function IntroductionGuidePage() {
  return (
    <div className="space-y-6 pb-12">
      <div>
        <div className="flex items-center gap-2">
          <h1 className="text-3xl font-bold tracking-tight">Giới thiệu nền tảng</h1>
          <Badge variant="default" className="text-xs">{process.env.NEXT_PUBLIC_APP_VERSION || "v1.0"}</Badge>
        </div>
        <p className="text-sm text-muted-foreground mt-1">
          Tài liệu Vận hành & Tích hợp dành cho Nền tảng hỏi đáp tài liệu tự động (RAG) đa khách hàng.
        </p>
      </div>

      <Alert className="bg-blue-50 border-blue-200">
        <InfoIcon className="h-4 w-4 text-blue-600" />
        <AlertTitle className="text-blue-800 font-bold">Dành cho ai?</AlertTitle>
        <AlertDescription className="text-blue-700 text-sm leading-6">
          Tài liệu này được thiết kế chuẩn mực dành cho cả hai nhóm:
          <br/>- <strong>Nhóm BA / Vận hành / Product Manager:</strong> Đọc để hiểu nguyên lý hoạt động, cách phân quyền, thao tác click chuột để tải file và quản lý khách hàng.
          <br/>- <strong>Nhóm Dev / Kỹ sư tích hợp:</strong> Đọc để nắm kiến trúc API, cơ chế Fallback (Dự phòng lỗi), cách mã hoá Token và gọi REST API.
        </AlertDescription>
      </Alert>

      <section className="space-y-4">
        <h2 className="text-xl font-semibold">1. RAG (Retrieval-Augmented Generation) là gì?</h2>
        <Card className="bg-slate-50/50">
          <CardContent className="pt-6 space-y-4 text-sm text-slate-700 leading-6">
            <p>
              Thay vì để AI tự &quot;bịa&quot; ra câu trả lời dựa trên kiến thức chung có sẵn trên mạng, nền tảng RAG hoạt động theo luồng:
            </p>
            <div className="flex flex-col md:flex-row items-center gap-4 bg-white p-4 rounded-lg border border-slate-200 justify-center">
              <div className="text-center font-medium bg-blue-100 text-blue-800 px-4 py-2 rounded">Người dùng hỏi</div>
              <ArrowRightIcon className="text-slate-400 hidden md:block" />
              <div className="text-center font-medium bg-purple-100 text-purple-800 px-4 py-2 rounded">Máy tìm kiếm tài liệu (Vector DB)</div>
              <ArrowRightIcon className="text-slate-400 hidden md:block" />
              <div className="text-center font-medium bg-emerald-100 text-emerald-800 px-4 py-2 rounded">AI đọc tài liệu & Trả lời</div>
            </div>
            <p>
              Nhờ vậy, câu trả lời luôn <strong>chính xác 100% theo tài liệu nội bộ</strong> của công ty, hoàn toàn không có hiện tượng ảo giác (hallucination).
            </p>
          </CardContent>
        </Card>
      </section>

      <section className="space-y-4">
        <h2 className="text-xl font-semibold">2. Sơ đồ Phân quyền (Roles)</h2>
        <p className="text-sm text-muted-foreground mb-4">
          Hệ thống được thiết kế dưới dạng SaaS Multi-tenant, cho phép một nền tảng duy nhất phục vụ nhiều công ty khác nhau hoàn toàn biệt lập và bảo mật. Có 2 vai trò cốt lõi cực kỳ rạch ròi:
        </p>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Card className="border-t-4 border-t-primary shadow-sm hover:shadow-md transition-shadow">
            <CardHeader>
              <ShieldCheckIcon className="w-8 h-8 text-primary mb-2" />
              <CardTitle>Platform Admin</CardTitle>
              <CardDescription>Quản trị viên Hạ tầng (Chủ nền tảng)</CardDescription>
            </CardHeader>
            <CardContent>
              <ul className="space-y-3 text-sm text-slate-700">
                <li className="flex items-start gap-2">
                  <div className="w-1.5 h-1.5 rounded-full bg-primary mt-1.5 shrink-0" /> 
                  <span><strong>Không gian làm việc:</strong> Có toàn quyền kiểm soát hệ thống kỹ thuật.</span>
                </li>
                <li className="flex items-start gap-2">
                  <div className="w-1.5 h-1.5 rounded-full bg-primary mt-1.5 shrink-0" /> 
                  <span><strong>Quản lý Khách hàng:</strong> Tạo mới các Tenant (Công ty) và cấp phát Quota (Giới hạn tài nguyên).</span>
                </li>
                <li className="flex items-start gap-2">
                  <div className="w-1.5 h-1.5 rounded-full bg-primary mt-1.5 shrink-0" /> 
                  <span><strong>Quản lý AI:</strong> Cấu hình kết nối tới OpenAI, NVIDIA, hoặc Docker Model Runner nội bộ. Quản lý chung chìa khoá AI của toàn hệ thống.</span>
                </li>
              </ul>
            </CardContent>
          </Card>

          <Card className="border-t-4 border-t-emerald-500 shadow-sm hover:shadow-md transition-shadow">
            <CardHeader>
              <Building2Icon className="w-8 h-8 text-emerald-500 mb-2" />
              <CardTitle>Tenant Admin</CardTitle>
              <CardDescription>Quản trị viên Doanh nghiệp (Khách hàng)</CardDescription>
            </CardHeader>
            <CardContent>
              <ul className="space-y-3 text-sm text-slate-700">
                <li className="flex items-start gap-2">
                  <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 mt-1.5 shrink-0" /> 
                  <span><strong>Không gian làm việc:</strong> Bị khoá chặt trong Tenant của mình. Không nhìn thấy dữ liệu của công ty khác.</span>
                </li>
                <li className="flex items-start gap-2">
                  <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 mt-1.5 shrink-0" /> 
                  <span><strong>Quản lý Dữ liệu:</strong> Tự Upload PDF, Word nội bộ. Hệ thống sẽ phân tích và lưu riêng biệt.</span>
                </li>
                <li className="flex items-start gap-2">
                  <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 mt-1.5 shrink-0" /> 
                  <span><strong>Cấp phát API:</strong> Tự sinh các mã API Key để đưa cho đội Dev của họ nhúng chatbot vào ứng dụng riêng.</span>
                </li>
              </ul>
            </CardContent>
          </Card>
        </div>
      </section>

      <section className="space-y-4">
        <h2 className="text-xl font-semibold">3. Kiến trúc API-First</h2>
        <Card className="shadow-sm">
          <CardContent className="pt-6 space-y-4 text-sm text-slate-700 leading-6">
            <div className="flex items-start gap-4">
              <MessageSquareTextIcon className="w-10 h-10 text-orange-500 shrink-0" />
              <div>
                <h3 className="font-semibold text-base mb-1">Bộ não vô hình (Headless Backend)</h3>
                <p>
                  Khác với ChatGPT có giao diện chat đồ sộ, nền tảng này được xây dựng theo kiến trúc <strong>API-First</strong>. Giao diện bạn đang xem (Webapp) thực chất chỉ là trang <strong>Quản trị viên (Admin Panel)</strong> để cấu hình dữ liệu và theo dõi luồng chạy.
                </p>
                <p className="mt-2">
                  Sức mạnh thực sự nằm ở các điểm phát sóng (API Endpoints). Các lập trình viên (Dev) của khách hàng sẽ sử dụng các API này để &quot;cấy&quot; bộ não AI vào bất kỳ đâu họ muốn: <em>App bán hàng trên điện thoại, Zalo Mini App, Phần mềm quản lý nhân sự (HRM) trên máy tính...</em>
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
