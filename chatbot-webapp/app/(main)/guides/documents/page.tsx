import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { FileUpIcon, SearchIcon, BotIcon, DatabaseIcon, InfoIcon } from "lucide-react";

export default function DocumentsGuidePage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Quản lý Tài liệu</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Hiểu cách hệ thống "đọc" và "ghi nhớ" tài liệu Word, PDF của bạn.
        </p>
      </div>

      <Alert>
        <InfoIcon className="h-4 w-4" />
        <AlertTitle>Bảo mật dữ liệu tuyệt đối!</AlertTitle>
        <AlertDescription>
          Mọi tài liệu của bạn tải lên chỉ phục vụ duy nhất cho nội bộ công ty (Tenant) của bạn. Hệ thống KHÔNG lấy dữ liệu này để huấn luyện ngược lại cho ChatGPT hay các nhà cung cấp AI.
        </AlertDescription>
      </Alert>

      <section className="space-y-4">
        <h2 className="text-lg font-semibold">Hành trình của một file tài liệu</h2>
        
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mt-6">
          <Card className="border-t-4 border-t-blue-500">
            <CardHeader className="pb-2">
              <FileUpIcon className="w-8 h-8 text-blue-500 mb-2" />
              <CardTitle className="text-lg">1. Upload File</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-slate-600">
              Quản trị viên tải file (PDF, DOCX, TXT...) lên hệ thống qua giao diện hoặc API. File gốc sẽ được lưu trữ an toàn.
            </CardContent>
          </Card>

          <Card className="border-t-4 border-t-amber-500 relative">
            <div className="hidden md:block absolute -left-4 top-1/2 w-8 border-t-2 border-dashed border-slate-300"></div>
            <CardHeader className="pb-2">
              <DatabaseIcon className="w-8 h-8 text-amber-500 mb-2" />
              <CardTitle className="text-lg">2. Băm nhỏ (Chunking)</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-slate-600">
              Một file 100 trang quá dài để AI đọc 1 lúc. Hệ thống sẽ băm file ra thành hàng nghìn đoạn nhỏ (mỗi đoạn vài câu) để dễ tra cứu.
            </CardContent>
          </Card>

          <Card className="border-t-4 border-t-purple-500 relative">
            <div className="hidden md:block absolute -left-4 top-1/2 w-8 border-t-2 border-dashed border-slate-300"></div>
            <CardHeader className="pb-2">
              <SearchIcon className="w-8 h-8 text-purple-500 mb-2" />
              <CardTitle className="text-lg">3. Số hoá (Embedding)</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-slate-600">
              Các đoạn văn bản ngắn này được biến đổi thành dạng "Vector số học". Các đoạn văn có ý nghĩa giống nhau sẽ nằm gần nhau trong không gian Vector.
            </CardContent>
          </Card>

          <Card className="border-t-4 border-t-emerald-500 relative">
            <div className="hidden md:block absolute -left-4 top-1/2 w-8 border-t-2 border-dashed border-slate-300"></div>
            <CardHeader className="pb-2">
              <BotIcon className="w-8 h-8 text-emerald-500 mb-2" />
              <CardTitle className="text-lg">4. Phục vụ AI (RAG)</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-slate-600">
              Khi User hỏi: "Chính sách thai sản", máy tìm kiếm Vector lập tức lôi ra đúng đoạn nói về thai sản và ném cho AI để AI trả lời.
            </CardContent>
          </Card>
        </div>
      </section>

      <section className="space-y-4">
        <h2 className="text-lg font-semibold mt-8">Cách quản lý tốt tài liệu</h2>
        <Card className="bg-slate-50/50">
          <CardContent className="pt-6 space-y-4">
            <ul className="list-disc pl-6 space-y-3 text-slate-700">
              <li>
                <strong>Nội dung rõ ràng:</strong> File PDF nếu là dạng Scan (hình ảnh) sẽ khó phân tích hơn File PDF tạo từ Word có text thật. Nên ưu tiên File gốc (DOCX) hoặc PDF chữ.
              </li>
              <li>
                <strong>Xoá tài liệu cũ:</strong> Nếu công ty bạn thay đổi chính sách nhân sự sang phiên bản 2026, hãy vào xoá file bản 2025. Nếu để cả 2 file, AI có thể bị bối rối vì đọc trúng thông tin bị mâu thuẫn.
              </li>
              <li>
                <strong>Tên file dễ hiểu:</strong> Tên file cũng là một từ khoá hữu ích. Đặt tên <code>Chinh_sach_nhan_su_2026.pdf</code> thay vì <code>Doc123.pdf</code>.
              </li>
            </ul>
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
