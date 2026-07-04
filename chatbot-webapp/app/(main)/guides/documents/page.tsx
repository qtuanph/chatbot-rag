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
  AlertTriangleIcon
} from "lucide-react";

export default function DocumentsGuidePage() {
  return (
    <div className="space-y-8 pb-16 max-w-4xl">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-foreground">Quản lý Tài liệu (Knowledge Base)</h1>
        <p className="text-sm text-muted-foreground mt-2">
          Cách hệ thống đọc, băm nhỏ và vector hóa các tài liệu nghiệp vụ nội bộ.
        </p>
      </div>

      {/* Security alert */}
      <Alert>
        <InfoIcon className="h-4 w-4" />
        <AlertTitle className="font-bold">Bảo mật dữ liệu nội bộ</AlertTitle>
        <AlertDescription className="text-sm leading-6 mt-1 text-muted-foreground">
          Dữ liệu của từng Tenant được cô lập hoàn toàn ở tầng vật lý (Database Filter). Hệ thống <strong>tuyệt đối không</strong> sử dụng tài liệu của bạn để train lại cho các model công cộng của OpenAI hay NVIDIA.
        </AlertDescription>
      </Alert>

      {/* Guide & Rules */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        
        {/* Upload guide */}
        <div className="border border-border rounded-xl p-5 bg-card space-y-3">
          <h2 className="text-base font-bold text-foreground flex items-center gap-2">
            <MousePointerClickIcon className="w-4 h-4 text-primary" />
            Các bước Upload Tài liệu
          </h2>
          <ol className="list-decimal pl-4 text-xs text-muted-foreground space-y-2.5">
            <li>Truy cập menu <strong>Dữ liệu &gt; Tài liệu</strong> (Chỉ hiển thị với Tenant Admin).</li>
            <li>Bấm nút <strong>Tải file lên</strong> ở góc trên.</li>
            <li>Chọn file từ máy tính. Định dạng hỗ trợ tốt nhất là <strong>PDF (dạng text)</strong>, <strong>DOCX</strong>, <strong>TXT</strong> và <strong>Markdown</strong>.</li>
            <li>Theo dõi trạng thái xử lý tài liệu trong bảng:
              <ul className="mt-2 space-y-1.5 list-none pl-0 font-medium">
                <li className="flex items-center gap-1.5"><ClockIcon className="w-3.5 h-3.5 text-amber-500" /> <code>Processing</code>: Đang băm và trích xuất.</li>
                <li className="flex items-center gap-1.5"><CheckCircle2Icon className="w-3.5 h-3.5 text-emerald-500" /> <code>Ready</code>: AI đã học xong và có thể trả lời.</li>
                <li className="flex items-center gap-1.5"><AlertTriangleIcon className="w-3.5 h-3.5 text-destructive" /> <code>Failed</code>: Lỗi đọc file (file scan ảnh không có text hoặc bị khóa mật khẩu).</li>
              </ul>
            </li>
          </ol>
        </div>

        {/* Best practices */}
        <div className="border border-border rounded-xl p-5 bg-card space-y-3">
          <h2 className="text-base font-bold text-foreground flex items-center gap-2">
            <InfoIcon className="w-4 h-4 text-primary" />
            Kinh nghiệm soạn tài liệu (Best Practices)
          </h2>
          <ul className="list-disc pl-4 text-xs text-muted-foreground space-y-2.5">
            <li>
              <strong>Tránh PDF dạng ảnh chụp (Scanned):</strong> OCR tự động có độ sai lệch cao. Hãy ưu tiên file Word (.docx) hoặc PDF xuất trực tiếp từ máy tính.
            </li>
            <li>
              <strong>Dọn dẹp thông tin rác:</strong> Loại bỏ các trang bìa lớn, mục lục dài hoặc các lời mở đầu thừa thãi để tránh gây nhiễu cho AI khi tìm kiếm ngữ nghĩa.
            </li>
            <li>
              <strong>Đặt tên file mô tả đúng nội dung:</strong> Tên file là một siêu dữ liệu (Metadata) quan trọng. Ví dụ đặt tên: <code className="bg-muted px-1 rounded text-foreground text-[11px]">Chinh_sach_nhan_su_2026.pdf</code> thay vì <code className="bg-muted px-1 rounded text-[11px]">Doc_final_v2.pdf</code>.
            </li>
            <li>
              <strong>Xóa bỏ tài liệu hết hạn:</strong> Khi có chính sách mới thay thế bản cũ, hãy xóa bản cũ khỏi hệ thống để tránh AI đọc phải thông tin mâu thuẫn.
            </li>
          </ul>
        </div>

      </div>

      {/* Under the hood workflow */}
      <section className="space-y-4">
        <h2 className="text-xl font-bold text-foreground border-b pb-2">Hành trình của một file tài liệu (Under the hood)</h2>
        
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="border border-border rounded-xl p-4 bg-muted/20 space-y-2">
            <FileUpIcon className="w-6 h-6 text-primary" />
            <h3 className="font-bold text-sm text-foreground">1. Đọc thô (Parsing)</h3>
            <p className="text-xs text-muted-foreground leading-relaxed">
              Trích xuất toàn bộ văn bản thô từ file, loại bỏ hình ảnh trang trí, font chữ màu mè.
            </p>
          </div>

          <div className="border border-border rounded-xl p-4 bg-muted/20 space-y-2">
            <DatabaseIcon className="w-6 h-6 text-primary" />
            <h3 className="font-bold text-sm text-foreground">2. Băm nhỏ (Chunking)</h3>
            <p className="text-xs text-muted-foreground leading-relaxed">
              Băm văn bản thành các đoạn nhỏ (khoảng 500-1000 từ) để AI dễ đọc và định vị chính xác thông tin.
            </p>
          </div>

          <div className="border border-border rounded-xl p-4 bg-muted/20 space-y-2">
            <SearchIcon className="w-6 h-6 text-primary" />
            <h3 className="font-bold text-sm text-foreground">3. Số hóa (Embedding)</h3>
            <p className="text-xs text-muted-foreground leading-relaxed">
              Chuyển các đoạn văn bản thành Vector đa chiều lưu vào Vector DB (Qdrant).
            </p>
          </div>

          <div className="border border-border rounded-xl p-4 bg-muted/20 space-y-2">
            <BotIcon className="w-6 h-6 text-primary" />
            <h3 className="font-bold text-sm text-foreground">4. Truy xuất (Retrieval)</h3>
            <p className="text-xs text-muted-foreground leading-relaxed">
              Quét nhanh hàng triệu vector, lọc ra 5 đoạn văn bản khớp ý nghĩa nhất đưa vào Prompt cho LLM.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}
