"use client";

import { Card, CardContent } from "@/components/ui/card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { 
  FileUpIcon, 
  SearchIcon, 
  BotIcon, 
  DatabaseIcon, 
  InfoIcon,
  MousePointerClickIcon,
  CheckCircle2Icon,
  ClockIcon,
  AlertTriangleIcon,
  ShieldCheckIcon,
  Trash2Icon,
  WorkflowIcon,
} from "lucide-react";

export default function DocumentsGuidePage() {
  return (
    <div className="space-y-8 pb-16 max-w-4xl">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-foreground">Quản lý Kho Tài liệu &amp; Tri thức RAG</h1>
        <p className="text-sm text-muted-foreground mt-2">
          Hướng dẫn tải file, xử lý băm nhỏ (Semantic Chunking) và phân quyền tri thức tài liệu cho từng Công ty.
        </p>
      </div>

      {/* Security alert */}
      <Alert className="border-border bg-card">
        <ShieldCheckIcon className="h-5 w-5 text-primary" />
        <AlertTitle className="font-bold text-foreground">Bảo mật dữ liệu &amp; Cô lập tài liệu</AlertTitle>
        <AlertDescription className="text-xs leading-5 mt-1 text-muted-foreground">
          Dữ liệu tài liệu của từng Tenant được bảo vệ bằng cơ chế phân quyền <code>tenant_document_access</code>. Hệ thống <strong>tuyệt đối không</strong> gửi tài liệu của bạn để huấn luyện cho bất kỳ mô hình công cộng nào ngoài internet.
        </AlertDescription>
      </Alert>

      {/* Upload guide & Best practices */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        
        {/* Upload guide */}
        <div className="border border-border rounded-xl p-5 bg-card space-y-3">
          <h2 className="text-base font-bold text-foreground flex items-center gap-2">
            <MousePointerClickIcon className="w-4 h-4 text-primary" />
            Các bước Tải &amp; Quản lý Tài liệu
          </h2>
          <ol className="list-decimal pl-4 text-xs text-muted-foreground space-y-2.5">
            <li>Truy cập menu <strong>Tri thức &gt; Kho Tài liệu</strong>.</li>
            <li>Bấm nút <strong>Tải file lên</strong> ở góc trên bên phải.</li>
            <li>Chọn file từ máy tính. Các định dạng được hỗ trợ: <strong>PDF (dạng text)</strong>, <strong>DOCX</strong>, <strong>TXT</strong> và <strong>Markdown (.md)</strong>.</li>
            <li>Theo dõi trạng thái băm file trong bảng dữ liệu:
              <ul className="mt-2 space-y-1.5 list-none pl-0 font-medium">
                <li className="flex items-center gap-1.5"><ClockIcon className="w-3.5 h-3.5 text-amber-500" /> <code>Processing</code>: Đang trích xuất văn bản &amp; băm chunk.</li>
                <li className="flex items-center gap-1.5"><CheckCircle2Icon className="w-3.5 h-3.5 text-emerald-500" /> <code>Ready</code>: AI đã học xong tri thức và sẵn sàng trả lời.</li>
                <li className="flex items-center gap-1.5"><AlertTriangleIcon className="w-3.5 h-3.5 text-destructive" /> <code>Failed</code>: File bị khóa mật khẩu hoặc là PDF scan ảnh.</li>
              </ul>
            </li>
          </ol>
        </div>

        {/* Best practices */}
        <div className="border border-border rounded-xl p-5 bg-card space-y-3">
          <h2 className="text-base font-bold text-foreground flex items-center gap-2">
            <InfoIcon className="w-4 h-4 text-primary" />
            Kinh nghiệm chuẩn hóa tài liệu (Best Practices)
          </h2>
          <ul className="list-disc pl-4 text-xs text-muted-foreground space-y-2.5">
            <li>
              <strong>Khuyên dùng PDF xuất từ Word / Markdown:</strong> Tránh file scan ảnh không có text. Văn bản thô càng sạch thì AI đọc trả lời càng chính xác.
            </li>
            <li>
              <strong>Cấu trúc tiêu đề rõ ràng:</strong> Đặt tiêu đề mục (Heading 1, Heading 2...) rõ ràng để bộ băm <code>Section Chunking</code> giữ nguyên cấu trúc văn bản.
            </li>
            <li>
              <strong>Đặt tên file chuẩn hóa:</strong> Đặt tên file thể hiện đúng chủ đề. Ví dụ: <code className="bg-muted px-1 rounded text-foreground text-[11px]">Huong_dan_Ke_toan_Tong_hop_2026.pdf</code> thay vì <code className="bg-muted px-1 rounded text-[11px]">File_v1.pdf</code>.
            </li>
            <li>
              <strong>Phân quyền cho Tenant:</strong> Sau khi nạp file, nhớ gán quyền tài liệu cho Tenant tương ứng để AI truy xuất dữ liệu.
            </li>
          </ul>
        </div>

      </div>

      {/* Hard Delete Rules */}
      <section className="border border-border rounded-xl p-5 bg-card space-y-3">
        <h2 className="text-base font-bold text-foreground flex items-center gap-2">
          <Trash2Icon className="w-4 h-4 text-destructive" />
          Quy trình Xóa tài liệu triệt để (Hard-Delete Standard)
        </h2>
        <p className="text-xs text-muted-foreground leading-relaxed">
          Khi xóa một tài liệu khỏi Kho tri thức, hệ thống thực thi xóa triệt để theo thứ tự bắt buộc: 
          <strong> 1. Vector Qdrant ➔ 2. Section Chunks trong DB ➔ 3. File nguồn trên Storage ➔ 4. Dòng dữ liệu DB</strong>.
          Quy trình này bảo đảm tài liệu xóa sẽ biến mất hoàn toàn khỏi bộ nhớ AI và không để lại vector rác.
        </p>
      </section>
    </div>
  );
}
