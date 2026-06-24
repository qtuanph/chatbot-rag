import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
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
    <div className="space-y-6 pb-12">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Cấu hình AI & Model</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Quản lý sức mạnh trí tuệ nhân tạo đằng sau hệ thống. Chức năng này <strong>chỉ dành cho Platform Admin</strong>.
        </p>
      </div>

      <Alert variant="destructive" className="bg-red-50">
        <ShieldAlertIcon className="h-4 w-4" />
        <AlertTitle className="text-sm font-bold">Khu vực nguy hiểm!</AlertTitle>
        <AlertDescription className="text-xs">
          Việc thay đổi Model Embedding có thể khiến toàn bộ tài liệu đã tải lên trước đó trở nên vô dụng do sai lệch toạ độ Vector. Bạn phải <strong>Re-index (Chạy lại tiến trình băm)</strong> toàn bộ tài liệu nếu thay đổi cấu hình gốc này. Hãy chắc chắn trước khi lưu!
        </AlertDescription>
      </Alert>

      <section className="space-y-4">
        <h2 className="text-xl font-semibold border-b pb-2">1. Hiểu về các Model AI</h2>
        
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <Card className="border-t-4 border-t-yellow-500 shadow-sm">
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-base">
                <ZapIcon className="w-5 h-5 text-yellow-500" />
                LLM (Tạo văn bản)
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm text-slate-700">
              <p>Mô hình AI nhận câu hỏi và đọc tài liệu để viết ra câu trả lời cuối cùng cho User (Ví dụ: GPT-4o, Claude, LLaMA).</p>
              <Badge variant="outline" className="bg-yellow-50 text-yellow-800">Tác dụng: Nói chuyện & Tổng hợp</Badge>
            </CardContent>
          </Card>

          <Card className="border-t-4 border-t-blue-500 shadow-sm">
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-base">
                <LayersIcon className="w-5 h-5 text-blue-500" />
                Embedding (Số hoá)
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm text-slate-700">
              <p>Mô hình &quot;hiểu&quot; ngữ nghĩa văn bản tĩnh, sau đó gán cho nó các toạ độ toán học (Vector) để lưu vào cơ sở dữ liệu.</p>
              <Badge variant="outline" className="bg-blue-50 text-blue-800">Tác dụng: Xếp loại & Tìm kiếm</Badge>
            </CardContent>
          </Card>

          <Card className="border-t-4 border-t-emerald-500 shadow-sm">
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-base">
                <SettingsIcon className="w-5 h-5 text-emerald-500" />
                Reranker (Bộ lọc)
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm text-slate-700">
              <p>Mô hình chấm điểm lại độ liên quan cực kỳ khắt khe. Nó đọc qua 20 kết quả thô, loại bỏ các kết quả rác và chỉ giữ lại 5 kết quả tốt nhất đưa cho LLM.</p>
              <Badge variant="outline" className="bg-emerald-50 text-emerald-800">Tác dụng: Tăng độ chính xác x10</Badge>
            </CardContent>
          </Card>
        </div>
      </section>

      <section className="space-y-4">
        <h2 className="text-xl font-semibold border-b pb-2 flex items-center gap-2">
          <MousePointerClickIcon className="w-5 h-5" />
          Hướng dẫn Thiết lập từng bước (Step-by-step)
        </h2>
        <Card>
          <CardContent className="pt-6 space-y-4 text-sm text-slate-700 leading-6">
            <div className="bg-slate-50 p-4 rounded-lg border border-slate-200 mb-4">
              <h3 className="font-bold mb-2">Các bước thao tác chung trên giao diện:</h3>
              <ol className="list-decimal pl-5 space-y-2">
                <li>Truy cập menu <strong>Quản trị &gt; AI Providers</strong> trên thanh bên trái.</li>
                <li>Chọn Tab (Embedding / Reranker / LLM) mà bạn muốn thiết lập.</li>
                <li>Bấm nút <strong>+ Thêm Provider</strong> (hoặc click vào Card của Provider mặc định có sẵn để sửa).</li>
                <li>Điền đầy đủ <code>URL</code>, <code>API Key</code> (nếu mua từ bên thứ 3), và <code>Model</code>. Bấm Lưu.</li>
                <li>Bấm vào icon <strong>Hình ống nghiệm (Test)</strong> trên Card đó để kiểm tra xem cấu hình đã đúng hay chưa.</li>
                <li>Nếu kết nối thành công, bấm icon <strong>Nguồn (Activate)</strong> để hệ thống chính thức bắt đầu sử dụng model này.</li>
              </ol>
            </div>
          </CardContent>
        </Card>
      </section>

      <section className="space-y-4">
        <h2 className="text-xl font-semibold border-b pb-2 flex items-center gap-2">
          <ServerCrashIcon className="w-5 h-5 text-red-500" />
          Cơ chế Dự phòng lõi (Fallback) - Dành cho Dev / Kỹ sư
        </h2>
        <Card className="bg-red-50/30 border-red-100">
          <CardContent className="pt-6 space-y-4 text-sm text-slate-700 leading-6">
            <p>
              Để đảm bảo hệ thống không bao giờ bị &quot;chết&quot; hoàn toàn khi nhà cung cấp lớn (như NVIDIA hay OpenAI) bị đứt cáp quang hoặc bạn quên đóng tiền API, hệ thống được thiết kế với cơ chế <strong>Auto-Fallback về Local Docker</strong>.
            </p>
            <div className="flex flex-col space-y-3 bg-white p-4 rounded-md border border-slate-200">
              <div className="flex gap-2">
                <Badge className="bg-red-500 hover:bg-red-600">Trường hợp</Badge>
                <span>Bạn cấu hình Reranker dùng <strong>NVIDIA NIM</strong>, nhưng API Key bị lỗi hoặc hết hạn.</span>
              </div>
              <div className="flex gap-2 items-center text-slate-400 pl-4">
                <ArrowRightIcon className="w-4 h-4" />
              </div>
              <div className="flex gap-2">
                <Badge className="bg-emerald-500 hover:bg-emerald-600">Hành động của Code</Badge>
                <span>Backend tự động bắt lỗi (Exception) và chuyển hướng luồng xử lý xuống nhà cung cấp có tên <code>dmr</code> (Docker Model Runner).</span>
              </div>
              <div className="flex gap-2 items-center text-slate-400 pl-4">
                <ArrowRightIcon className="w-4 h-4" />
              </div>
              <div className="flex gap-2">
                <Badge className="bg-blue-500 hover:bg-blue-600">Kết quả</Badge>
                <span>Truy vấn vẫn thành công! Nó lấy cấu hình của card <strong>Docker Model Runner (Fallback)</strong> chạy trên chính server của bạn để xử lý thay thế.</span>
              </div>
            </div>
            <p className="mt-2 text-xs text-muted-foreground italic">
              * Lời khuyên: Hãy luôn cài đặt sẵn model nhẹ (như Qwen 0.5B) cho thằng Docker Model Runner trên giao diện để làm phương án cứu cánh cuối cùng.
            </p>
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
