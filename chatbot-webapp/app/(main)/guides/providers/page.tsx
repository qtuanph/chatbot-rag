import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { SettingsIcon, ZapIcon, LayersIcon, ArrowRightIcon } from "lucide-react";

export default function ProvidersGuidePage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Cấu hình AI & Model</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Quản lý sức mạnh trí tuệ nhân tạo đằng sau hệ thống. Chức năng này chỉ dành cho Platform Admin.
        </p>
      </div>

      <Alert variant="destructive">
        <SettingsIcon className="h-4 w-4" />
        <AlertTitle className="text-sm">Khu vực nguy hiểm!</AlertTitle>
        <AlertDescription className="text-xs">
          Việc thay đổi Model Embedding có thể khiến toàn bộ tài liệu đã tải lên không thể tìm kiếm được nữa. Bạn phải Re-index lại toàn bộ tài liệu nếu thay đổi cấu hình gốc này.
        </AlertDescription>
      </Alert>

      <section className="space-y-4">
        <h2 className="text-lg font-semibold">1. Large Language Model (LLM)</h2>
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <ZapIcon className="w-5 h-5 text-yellow-500" />
              Bộ não tạo văn bản
            </CardTitle>
            <CardDescription className="text-xs">Mô hình AI nhận câu hỏi và đọc tài liệu để viết câu trả lời cho User.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-slate-700 leading-6">
              Bạn có thể dễ dàng chuyển đổi qua lại giữa GPT-4o, Claude 3.5 Sonnet, Gemini 1.5 Pro, hoặc các mô hình mã nguồn mở như LLaMA 3. 
              Hệ thống dùng chuẩn kết nối OpenAI tương thích ngược, nên bất kỳ Provider nào có chuẩn API giống OpenAI đều cắm vào chạy được ngay lập tức (Ví dụ: Groq, TogetherAI, DeepSeek).
            </p>
            <div className="bg-slate-50 p-4 rounded-lg border border-slate-200">
              <p className="font-semibold mb-2">Thông số cấu hình:</p>
              <ul className="list-disc pl-5 space-y-1 text-sm text-slate-600">
                <li><code>Provider URL</code>: Đường dẫn API của nhà cung cấp (VD: https://api.openai.com/v1)</li>
                <li><code>API Key</code>: Chìa khoá bí mật mua từ nhà cung cấp</li>
                <li><code>Model ID</code>: Mã mô hình chính xác (VD: gpt-4o-mini)</li>
              </ul>
            </div>
          </CardContent>
        </Card>
      </section>

      <section className="space-y-4">
        <h2 className="text-lg font-semibold">2. Embedding Model</h2>
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <LayersIcon className="w-5 h-5 text-blue-500" />
              Bộ nhúng số học
            </CardTitle>
            <CardDescription className="text-xs">Mô hình chuyên dụng để biến văn bản thành Vector đa chiều.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-slate-700 leading-6">
              Khác với LLM dùng để "nói", Embedding Model dùng để "hiểu" ngữ nghĩa văn bản và gán cho nó các toạ độ toán học. Model này thường chạy Local trên máy chủ Docker để tiết kiệm chi phí và cực kỳ bảo mật (tài liệu nội bộ không bao giờ rời khỏi server của bạn).
            </p>
            <div className="flex items-center gap-2 p-3 bg-amber-50 text-amber-900 rounded-md border border-amber-200 text-sm">
              <ArrowRightIcon className="w-4 h-4" />
              <strong>Lưu ý:</strong> Khi bạn thay đổi từ model A sang model B (Ví dụ BGE-M3 sang Nomic), tất cả vector cũ trong Qdrant sẽ vô dụng vì số chiều toạ độ khác nhau. Bạn phải chạy tiến trình Re-chunk / Re-index toàn bộ kho tài liệu.
            </div>
          </CardContent>
        </Card>
      </section>

      <section className="space-y-4">
        <h2 className="text-lg font-semibold">3. Reranker Model</h2>
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <SettingsIcon className="w-5 h-5 text-emerald-500" />
              Bộ lọc nâng cao
            </CardTitle>
            <CardDescription className="text-xs">Mô hình chấm điểm lại độ liên quan.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 text-sm text-slate-700 leading-6">
            <p>
              Khi User hỏi một câu, Vector DB sẽ móc ra 20 đoạn văn bản có khả năng liên quan cao nhất. Nhưng 20 đoạn này chưa chắc đoạn số 1 đã là câu trả lời tốt nhất.
            </p>
            <p>
              <strong>Reranker</strong> sẽ xuất hiện, đọc lướt qua cả 20 đoạn đó, đối chiếu kỹ lưỡng với câu hỏi của người dùng, và chấm điểm lại. Nó vứt đi 15 đoạn rác, và chỉ xếp hạng 5 đoạn chính xác nhất để ném cho LLM đọc. Việc này giúp AI trả lời cực kỳ thông minh và đỡ bị "nhiễu" thông tin.
            </p>
            <Badge className="bg-emerald-100 text-emerald-800 hover:bg-emerald-100 border-none">Được khuyên dùng: NVIDIA NIM Reranker hoặc BGE-Reranker-v2</Badge>
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
