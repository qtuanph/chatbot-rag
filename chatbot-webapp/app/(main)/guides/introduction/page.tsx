import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { 
  Building2Icon, 
  DatabaseIcon, 
  BrainCircuitIcon, 
  ShieldCheckIcon,
  MessageSquareTextIcon
} from "lucide-react";

export default function IntroductionGuidePage() {
  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold">RAG Platform</h1>
          <Badge variant="default" className="text-xs">v1.0</Badge>
        </div>
        <p className="text-sm text-muted-foreground mt-1">
          Nền tảng hỏi đáp tài liệu tự động (Retrieval-Augmented Generation) dành cho hệ thống Doanh nghiệp Đa người dùng.
        </p>
      </div>

      <section className="space-y-4">
        <h2 className="text-lg font-semibold">RAG là gì?</h2>
        <Card className="bg-slate-50/50">
          <CardContent className="pt-6">
            <p className="text-sm text-slate-700">
              <strong>RAG (Retrieval-Augmented Generation)</strong> là công nghệ kết hợp giữa Tìm kiếm dữ liệu (Retrieval) và Trí tuệ nhân tạo (Generation). 
              Thay vì để AI tự "bịa" ra câu trả lời dựa trên kiến thức chung có sẵn, nền tảng RAG sẽ tự động tìm kiếm các đoạn thông tin chính xác nhất từ tài liệu nội bộ của công ty bạn, sau đó đưa cho AI để tổng hợp thành một câu trả lời chính xác, có căn cứ và không bịa đặt (hallucination).
            </p>
          </CardContent>
        </Card>
      </section>

      <section className="space-y-4">
        <h2 className="text-lg font-semibold">Kiến trúc Multi-tenant (Đa khách hàng)</h2>
        <p className="text-sm text-muted-foreground mb-4">
          Hệ thống được thiết kế dưới dạng SaaS, cho phép một nền tảng duy nhất phục vụ nhiều tổ chức/công ty khác nhau một cách hoàn toàn biệt lập và bảo mật.
        </p>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Card>
            <CardHeader>
              <ShieldCheckIcon className="w-8 h-8 text-primary mb-2" />
              <CardTitle>Platform Admin</CardTitle>
              <CardDescription>Quản trị viên Hệ thống (Chủ nền tảng)</CardDescription>
            </CardHeader>
            <CardContent>
              <ul className="space-y-2 text-sm">
                <li className="flex items-center gap-2"><div className="w-1.5 h-1.5 rounded-full bg-primary" /> Có toàn quyền kiểm soát toàn bộ hệ thống.</li>
                <li className="flex items-center gap-2"><div className="w-1.5 h-1.5 rounded-full bg-primary" /> Tạo và quản lý các Tenant (Công ty khách hàng).</li>
                <li className="flex items-center gap-2"><div className="w-1.5 h-1.5 rounded-full bg-primary" /> Quản lý hệ thống AI Model, Vector DB (Qdrant).</li>
                <li className="flex items-center gap-2"><div className="w-1.5 h-1.5 rounded-full bg-primary" /> Xem báo cáo tổng thể mọi hoạt động.</li>
              </ul>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <Building2Icon className="w-8 h-8 text-emerald-500 mb-2" />
              <CardTitle>Tenant Admin</CardTitle>
              <CardDescription>Quản trị viên Doanh nghiệp</CardDescription>
            </CardHeader>
            <CardContent>
              <ul className="space-y-2 text-sm">
                <li className="flex items-center gap-2"><div className="w-1.5 h-1.5 rounded-full bg-emerald-500" /> Chỉ thao tác trong giới hạn không gian của công ty mình.</li>
                <li className="flex items-center gap-2"><div className="w-1.5 h-1.5 rounded-full bg-emerald-500" /> Upload và quản lý tài liệu nội bộ riêng biệt.</li>
                <li className="flex items-center gap-2"><div className="w-1.5 h-1.5 rounded-full bg-emerald-500" /> Tạo API Key để kết nối phần mềm của riêng họ.</li>
                <li className="flex items-center gap-2"><div className="w-1.5 h-1.5 rounded-full bg-emerald-500" /> Xem thống kê số lượng chat của nhân viên.</li>
              </ul>
            </CardContent>
          </Card>
        </div>
      </section>

      <section className="space-y-4">
        <h2 className="text-lg font-semibold">Các thành phần cốt lõi</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card className="shadow-sm border-t-4 border-t-blue-500">
            <CardHeader className="pb-3">
              <DatabaseIcon className="w-6 h-6 text-blue-500 mb-1" />
              <CardTitle className="text-lg">Vector Database</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              Hệ thống sử dụng **Qdrant** làm cơ sở dữ liệu Vector. Mọi tài liệu PDF, DOCX tải lên đều được cắt nhỏ và biến thành các chuỗi số (Vector), giúp AI tìm kiếm thần tốc dựa trên ngữ nghĩa thay vì chỉ khớp từ khoá.
            </CardContent>
          </Card>
          
          <Card className="shadow-sm border-t-4 border-t-purple-500">
            <CardHeader className="pb-3">
              <BrainCircuitIcon className="w-6 h-6 text-purple-500 mb-1" />
              <CardTitle className="text-lg">AI Providers</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              Tích hợp linh hoạt với các mô hình LLM mạnh nhất hiện nay thông qua chuẩn OpenAI. Hỗ trợ Reranker siêu cấp để sàng lọc và đưa ra đoạn văn bản liên quan nhất trước khi đưa vào AI.
            </CardContent>
          </Card>

          <Card className="shadow-sm border-t-4 border-t-orange-500">
            <CardHeader className="pb-3">
              <MessageSquareTextIcon className="w-6 h-6 text-orange-500 mb-1" />
              <CardTitle className="text-lg">API First</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              Thay vì bắt người dùng phải vào Web này để Chat, Nền tảng hoạt động như một **API Core Server**. Các lập trình viên có thể dễ dàng nhúng tính năng Chatbot vào phần mềm nội bộ, App di động của công ty.
            </CardContent>
          </Card>
        </div>
      </section>
    </div>
  );
}
