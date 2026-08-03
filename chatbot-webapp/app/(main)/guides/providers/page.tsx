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
  ServerCrashIcon,
  CpuIcon,
  BotIcon,
  ShieldCheckIcon,
} from "lucide-react";

export default function ProvidersGuidePage() {
  return (
    <div className="space-y-8 pb-16 max-w-4xl">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-foreground">Cấu hình AI Models &amp; Engine Dự phòng</h1>
        <p className="text-sm text-muted-foreground mt-2">
          Quản lý 3 tầng xử lý AI của hệ thống: LLM Provider, Local Embedding Engine và Reranker Model.
        </p>
      </div>

      {/* Warning alert */}
      <Alert variant="destructive">
        <ShieldAlertIcon className="h-4 w-4" />
        <AlertTitle className="font-bold">Khu vực quản trị nhạy cảm!</AlertTitle>
        <AlertDescription className="text-xs mt-1">
          Thay đổi Model Embedding hoặc Model Reranker sẽ làm thay đổi tọa độ không gian Vector của các tài liệu cũ. Bạn bắt buộc phải cho tiến trình băm lại toàn bộ tài liệu cũ sau khi thay đổi cấu hình này.
        </AlertDescription>
      </Alert>

      {/* 3 AI Layers */}
      <section className="space-y-4">
        <h2 className="text-xl font-bold text-foreground border-b pb-2 flex items-center gap-2">
          <CpuIcon className="w-5 h-5 text-primary" />
          1. 3 tầng xử lý AI chuyên biệt của Nền tảng
        </h2>
        
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* LLM */}
          <div className="border border-border rounded-xl p-4 bg-card space-y-2">
            <div className="flex items-center gap-2">
              <ZapIcon className="w-5 h-5 text-primary" />
              <h3 className="font-bold text-sm text-foreground">LLM Provider (9Router)</h3>
            </div>
            <p className="text-xs text-muted-foreground leading-relaxed">
              Mô hình ngôn ngữ lớn tiếp nhận Prompt tiêm Context từ RAG để tổng hợp thành câu trả lời tự nhiên (Đi qua 9Router Proxy).
            </p>
          </div>

          {/* Embedding */}
          <div className="border border-border rounded-xl p-4 bg-card space-y-2">
            <div className="flex items-center gap-2">
              <LayersIcon className="w-5 h-5 text-primary" />
              <h3 className="font-bold text-sm text-foreground">Embedding (DMR Local)</h3>
            </div>
            <p className="text-xs text-muted-foreground leading-relaxed">
              Chuyển đổi văn bản thành Tọa độ Vector số học đa chiều. Mặc định đi qua Docker Model Runner (DMR) nội bộ trên server.
            </p>
          </div>

          {/* Reranker */}
          <div className="border border-border rounded-xl p-4 bg-card space-y-2">
            <div className="flex items-center gap-2">
              <SettingsIcon className="w-5 h-5 text-primary" />
              <h3 className="font-bold text-sm text-foreground">Reranker (NVIDIA NIM)</h3>
            </div>
            <p className="text-xs text-muted-foreground leading-relaxed">
              Bộ lọc cross-encoder đọc lướt các đoạn tài liệu tìm được từ Qdrant, chấm điểm khắt khe và chỉ chọn ra 5 kết quả tốt nhất.
            </p>
          </div>
        </div>
      </section>

      {/* Auto-fallback section */}
      <section className="space-y-4">
        <h2 className="text-xl font-bold text-foreground border-b pb-2 flex items-center gap-2">
          <ServerCrashIcon className="w-5 h-5 text-primary" />
          2. Cơ chế Tự động Dự phòng Sự cố (Auto-Fallback)
        </h2>
        
        <div className="border border-border rounded-xl p-5 bg-card space-y-4">
          <p className="text-xs text-muted-foreground leading-relaxed">
            Để bảo đảm dịch vụ Chatbot hoạt động liên tục 24/7 khi các dịch vụ AI Cloud bên ngoài (như NVIDIA NIM hay OpenAI) gặp sự cố mạng hoặc hết hạn cước, hệ thống sẽ tự động kích hoạt luồng dự phòng local:
          </p>

          <div className="flex flex-col space-y-3 bg-muted/20 p-4 rounded-xl border border-border text-xs text-muted-foreground">
            <div className="flex gap-2">
              <span className="font-semibold text-foreground shrink-0">1. Sự cố Cloud:</span>
              <span>Model Cloud AI trả về lỗi Connection Timeout / Rate Limit / Auth Error.</span>
            </div>
            <div className="flex justify-center text-muted-foreground">
              <ArrowRightIcon className="w-4 h-4" />
            </div>
            <div className="flex gap-2">
              <span className="font-semibold text-foreground shrink-0">2. Tự động dự phòng:</span>
              <span>Backend RAG Service tự động bắt Exception và chuyển hướng sang <strong>Docker Model Runner (DMR)</strong> chạy local trên Server nội bộ.</span>
            </div>
            <div className="flex justify-center text-muted-foreground">
              <ArrowRightIcon className="w-4 h-4" />
            </div>
            <div className="flex gap-2">
              <span className="font-semibold text-foreground shrink-0">3. Duy trì hoạt động:</span>
              <span>Hệ thống Chatbot duy trì câu trả lời liên tục, không bị sập dịch vụ hay gián đoạn trải nghiệm người dùng.</span>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
