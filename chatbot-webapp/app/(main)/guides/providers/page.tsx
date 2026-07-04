"use client";

import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { 
  SettingsIcon, 
  ZapIcon, 
  LayersIcon, 
  ArrowRightIcon,
  MousePointerClickIcon,
  ShieldAlertIcon,
  ServerCrashIcon
} from "lucide-react";

export default function ProvidersGuidePage() {
  return (
    <div className="space-y-8 pb-16 max-w-4xl">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-slate-900 dark:text-foreground">Cấu hình AI &amp; Model</h1>
        <p className="text-sm text-muted-foreground mt-2">
          Quản lý sức mạnh trí tuệ nhân tạo đằng sau hệ thống. Chức năng chỉ dành cho <strong>Platform Admin</strong>.
        </p>
      </div>

      {/* Warning alert */}
      <Alert variant="destructive">
        <ShieldAlertIcon className="h-4 w-4" />
        <AlertTitle className="font-bold">Khu vực nhạy cảm!</AlertTitle>
        <AlertDescription className="text-xs mt-1">
          Thay đổi Model Embedding hoặc Model Reranker sẽ làm sai lệch toạ độ không gian vector của các tài liệu cũ. Bạn bắt buộc phải bấm <strong>Re-index (Chạy lại tiến trình băm)</strong> cho toàn bộ tài liệu sau khi đổi cấu hình này.
        </AlertDescription>
      </Alert>

      {/* Model roles grid */}
      <section className="space-y-4">
        <h2 className="text-xl font-bold text-foreground border-b pb-2">1. 3 tầng xử lý AI của hệ thống</h2>
        
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* LLM */}
          <div className="border border-border rounded-xl p-4 bg-card space-y-2">
            <div className="flex items-center gap-2">
              <ZapIcon className="w-5 h-5 text-primary" />
              <h3 className="font-bold text-sm text-foreground">LLM (Tạo câu trả lời)</h3>
            </div>
            <p className="text-xs text-muted-foreground leading-relaxed">
              Mô hình tiếp nhận câu hỏi cùng các tài liệu RAG liên quan để tổng hợp thành câu trả lời tự nhiên (Ví dụ: GPT-4o, Claude, LLaMA).
            </p>
          </div>

          {/* Embedding */}
          <div className="border border-border rounded-xl p-4 bg-card space-y-2">
            <div className="flex items-center gap-2">
              <LayersIcon className="w-5 h-5 text-primary" />
              <h3 className="font-bold text-sm text-foreground">Embedding (Số hóa văn bản)</h3>
            </div>
            <p className="text-xs text-muted-foreground leading-relaxed">
              Chuyển đổi ngôn ngữ viết thành tọa độ số học (Vector) để lưu vào Vector Database phục vụ tìm kiếm ngữ nghĩa.
            </p>
          </div>

          {/* Reranker */}
          <div className="border border-border rounded-xl p-4 bg-card space-y-2">
            <div className="flex items-center gap-2">
              <SettingsIcon className="w-5 h-5 text-primary" />
              <h3 className="font-bold text-sm text-foreground">Reranker (Bộ lọc chuẩn)</h3>
            </div>
            <p className="text-xs text-muted-foreground leading-relaxed">
              Đọc lướt qua hàng chục kết quả thô, chấm điểm và chỉ lọc ra 5 kết quả có độ chính xác cao nhất đưa cho LLM.
            </p>
          </div>
        </div>
      </section>

      {/* Steps */}
      <section className="space-y-4">
        <h2 className="text-xl font-bold text-foreground border-b pb-2 flex items-center gap-2">
          <MousePointerClickIcon className="w-5 h-5 text-primary" />
          Hướng dẫn thiết lập cấu hình AI
        </h2>
        
        <div className="border border-border rounded-xl p-5 bg-card space-y-3 text-xs text-muted-foreground leading-relaxed">
          <ol className="list-decimal pl-4 space-y-2.5">
            <li>Truy cập menu <strong>AI Providers</strong> ở mục hệ thống (Chỉ hiển thị với Platform Admin).</li>
            <li>Chọn tab tương ứng (Embedding / Reranker / LLM).</li>
            <li>Bấm <strong>Thêm mới Provider</strong> hoặc chỉnh sửa cấu hình mặc định.</li>
            <li>Nhập <code>URL</code> kết nối, <code>API Key</code> và tên <code>Model</code> chuẩn.</li>
            <li>Bấm icon <strong>Test (Hình ống nghiệm)</strong> trên card để kiểm tra kết nối.</li>
            <li>Nếu kết nối OK, bấm <strong>Kích hoạt (Icon nguồn)</strong> để đưa model vào sử dụng chính thức.</li>
          </ol>
        </div>
      </section>

      {/* Fallback mechanism */}
      <section className="space-y-4">
        <h2 className="text-xl font-bold text-foreground border-b pb-2 flex items-center gap-2">
          <ServerCrashIcon className="w-5 h-5 text-primary" />
          Cơ chế dự phòng sự cố (Auto-Fallback)
        </h2>
        
        <div className="border border-border rounded-xl p-5 bg-card space-y-4">
          <p className="text-xs text-muted-foreground leading-relaxed">
            Để tránh tình trạng chatbot dừng hoạt động khi các nhà cung cấp bên ngoài (như NVIDIA hay OpenAI) gặp sự cố mạng hoặc hết hạn gói dịch vụ, hệ thống tự động fallback về model local:
          </p>

          <div className="flex flex-col space-y-3 bg-muted/20 p-4 rounded-xl border border-border text-xs text-muted-foreground">
            <div className="flex gap-2">
              <span className="font-semibold text-foreground shrink-0">Sự cố:</span>
              <span>Model Reranker NVIDIA NIM trả về lỗi (hết hạn key hoặc timeout mạng).</span>
            </div>
            <div className="flex justify-center text-muted-foreground">
              <ArrowRightIcon className="w-4 h-4" />
            </div>
            <div className="flex gap-2">
              <span className="font-semibold text-foreground shrink-0 font-sans">Tự động xử lý:</span>
              <span>Backend bắt được exception và lập tức chuyển tiếp request qua <strong>dmr</strong> (Docker Model Runner) local.</span>
            </div>
            <div className="flex justify-center text-muted-foreground">
              <ArrowRightIcon className="w-4 h-4" />
            </div>
            <div className="flex gap-2">
              <span className="font-semibold text-foreground shrink-0 font-sans">Kết quả:</span>
              <span>Chatbot hoạt động bình thường bằng model chạy trực tiếp trên server của bạn, không bị đứt quãng dịch vụ.</span>
            </div>
          </div>
          <p className="text-[10px] text-muted-foreground italic">
            * Lời khuyên: Luôn thiết lập cấu hình Docker Model Runner (dmr) nội bộ làm phương án dự phòng cứu cánh.
          </p>
        </div>
      </section>
    </div>
  );
}
