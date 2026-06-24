import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
    <div className="space-y-6 pb-12">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Quản lý Tài liệu (Knowledge Base)</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Hiểu cách hệ thống &quot;đọc&quot;, &quot;băm nhỏ&quot; và &quot;ghi nhớ&quot; tài liệu PDF, DOCX của công ty bạn.
        </p>
      </div>

      <Alert className="bg-emerald-50 border-emerald-200">
        <InfoIcon className="h-4 w-4 text-emerald-600" />
        <AlertTitle className="text-emerald-800 font-bold">Bảo mật dữ liệu tuyệt đối!</AlertTitle>
        <AlertDescription className="text-emerald-700">
          Mọi tài liệu của bạn tải lên chỉ phục vụ duy nhất cho nội bộ công ty (Tenant) của bạn. Hệ thống <strong>KHÔNG</strong> lấy dữ liệu này để huấn luyện ngược lại cho ChatGPT hay bán cho bên thứ ba. Dữ liệu số hoá được cô lập hoàn toàn.
        </AlertDescription>
      </Alert>

      <section className="space-y-4">
        <h2 className="text-xl font-semibold border-b pb-2 flex items-center gap-2">
          <MousePointerClickIcon className="w-5 h-5" />
          Hướng dẫn Tải lên (Upload) & Quản lý
        </h2>
        <Card>
          <CardContent className="pt-6 space-y-4 text-sm text-slate-700 leading-6">
            <div className="bg-slate-50 p-4 rounded-lg border border-slate-200 mb-4">
              <h3 className="font-bold mb-2">Các bước thao tác trên giao diện:</h3>
              <ol className="list-decimal pl-5 space-y-2">
                <li>Truy cập menu <strong>Dữ liệu &gt; Documents</strong> trên thanh bên trái. (Chỉ Tenant Admin mới thấy).</li>
                <li>Bấm nút <strong>+ Tải file lên</strong>.</li>
                <li>Chọn các tệp tin từ máy tính. Hỗ trợ tốt nhất là <strong>PDF (dạng chữ)</strong>, <strong>DOCX</strong>, <strong>TXT</strong>, và <strong>Markdown</strong>.</li>
                <li>Hệ thống sẽ chạy ngầm. Vui lòng theo dõi <strong>Cột Trạng thái (Status)</strong> của file trong bảng:
                  <ul className="list-none pl-0 mt-2 space-y-1">
                    <li className="flex gap-2 items-center"><ClockIcon className="w-4 h-4 text-yellow-500" /> <code>Pending/Processing</code>: Đang xếp hàng chờ máy chủ băm nhỏ và Vector hoá.</li>
                    <li className="flex gap-2 items-center"><CheckCircle2Icon className="w-4 h-4 text-emerald-500" /> <code>Ready / Completed</code>: Đã học xong! AI giờ đây đã biết các thông tin trong file này.</li>
                    <li className="flex gap-2 items-center"><AlertTriangleIcon className="w-4 h-4 text-red-500" /> <code>Failed</code>: Lỗi định dạng file (ví dụ PDF trỗng hoặc mã hoá mật khẩu).</li>
                  </ul>
                </li>
              </ol>
            </div>
            
            <h3 className="font-bold mt-4">Kinh nghiệm chuẩn bị tài liệu (Best Practices):</h3>
            <ul className="list-disc pl-5 space-y-2">
              <li><strong>Chữ thay vì Ảnh:</strong> File PDF nếu là dạng Scan (chụp ảnh) sẽ cực kỳ khó phân tích và dễ bị sai chữ. Nếu có thể, hãy tải lên File gốc (DOCX) hoặc PDF xuất trực tiếp từ Word.</li>
              <li><strong>Đừng để AI &quot;Học tài liệu rác&quot;:</strong> Xoá các mục lục quá dài, các trang giới thiệu công ty vô thưởng vô phạt. Hãy đưa cho hệ thống các phần trọng tâm (Chính sách, Báo cáo, Quy trình).</li>
              <li><strong>Dọn dẹp file cũ:</strong> Nếu công ty bạn thay đổi chính sách nhân sự sang bản năm 2026, hãy vào <strong>xoá file bản 2025</strong> đi. Nếu để cả 2 file, AI sẽ đọc trúng thông tin mâu thuẫn và trả lời sai.</li>
              <li><strong>Đặt tên file dễ hiểu:</strong> Tên file cũng là một dạng siêu dữ liệu (Metadata) giúp AI tìm kiếm. Đặt tên <code>Chinh_sach_nhan_su_2026.pdf</code> thay vì <code>Doc123_final_v2.pdf</code>.</li>
            </ul>
          </CardContent>
        </Card>
      </section>

      <section className="space-y-4">
        <h2 className="text-xl font-semibold border-b pb-2 mt-8">Hành trình của một file tài liệu (Under the hood)</h2>
        <p className="text-sm text-muted-foreground mb-4">
          Dành cho những ai muốn tò mò: Chuyện gì xảy ra sau khi bạn bấm nút Upload?
        </p>
        
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mt-6">
          <Card className="border-t-4 border-t-blue-500 bg-blue-50/30">
            <CardHeader className="pb-2">
              <FileUpIcon className="w-8 h-8 text-blue-500 mb-2" />
              <CardTitle className="text-base">1. Parsing (Đọc thô)</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-slate-600">
              Hệ thống gỡ bỏ các định dạng màu mè, hình ảnh thừa, bảng biểu lộn xộn trong file PDF/Word để trích xuất ra toàn bộ <strong>Văn bản thô (Raw Text)</strong>.
            </CardContent>
          </Card>

          <Card className="border-t-4 border-t-amber-500 relative bg-amber-50/30">
            <div className="hidden md:block absolute -left-4 top-1/2 w-8 border-t-2 border-dashed border-slate-300"></div>
            <CardHeader className="pb-2">
              <DatabaseIcon className="w-8 h-8 text-amber-500 mb-2" />
              <CardTitle className="text-base">2. Chunking (Băm nhỏ)</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-slate-600">
              Một file 100 trang quá dài để AI đọc cùng 1 lúc (vượt quá Token limit). Hệ thống sẽ băm file ra thành hàng nghìn đoạn nhỏ (mỗi đoạn khoảng 500-1000 chữ) để dễ tra cứu.
            </CardContent>
          </Card>

          <Card className="border-t-4 border-t-purple-500 relative bg-purple-50/30">
            <div className="hidden md:block absolute -left-4 top-1/2 w-8 border-t-2 border-dashed border-slate-300"></div>
            <CardHeader className="pb-2">
              <SearchIcon className="w-8 h-8 text-purple-500 mb-2" />
              <CardTitle className="text-base">3. Embedding (Số hoá)</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-slate-600">
              Sử dụng Embedding Model (như BGE-M3), các đoạn văn bản này được chuyển đổi thành toạ độ <strong>Vector đa chiều</strong> (ví dụ 1024 chiều) và lưu vào Qdrant DB. Các câu có &quot;ý nghĩa&quot; giống nhau sẽ nằm gần nhau.
            </CardContent>
          </Card>

          <Card className="border-t-4 border-t-emerald-500 relative bg-emerald-50/30">
            <div className="hidden md:block absolute -left-4 top-1/2 w-8 border-t-2 border-dashed border-slate-300"></div>
            <CardHeader className="pb-2">
              <BotIcon className="w-8 h-8 text-emerald-500 mb-2" />
              <CardTitle className="text-base">4. Retrieval (Truy xuất)</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-slate-600">
              Khi User hỏi: <em>&quot;Chính sách thai sản 2026&quot;</em>. Cỗ máy tính toán nhanh chóng quét qua hàng triệu Vector để lôi ra đúng 5 đoạn chunk nói về thai sản, rồi ném cho AI để viết câu trả lời cuối cùng.
            </CardContent>
          </Card>
        </div>
      </section>
    </div>
  );
}
