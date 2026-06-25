"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Code2Icon, TerminalIcon, CpuIcon, WebhookIcon, NetworkIcon } from "lucide-react";

export default function IntegrationGuidePage() {
  return (
    <div className="space-y-6 pb-12">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Tích hợp phần mềm (Dev Guide)</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Sử dụng Nền tảng RAG như một API Backend độc lập (Drop-in Replacement cho OpenAI).
        </p>
      </div>

      <Alert className="bg-blue-50 border-blue-200">
        <CpuIcon className="h-4 w-4 text-blue-600" />
        <AlertTitle className="text-blue-800 font-bold">OpenAI Tương thích 100%</AlertTitle>
        <AlertDescription className="text-blue-700 text-sm leading-6">
          Bạn không cần học cú pháp API mới! Nếu phần mềm của bạn đã hỗ trợ ChatGPT/OpenAI, bạn chỉ việc đổi <code>Base URL</code> và truyền <code>API Key</code> do hệ thống này cấp là chạy được ngay lập tức.
        </AlertDescription>
      </Alert>

      <section className="space-y-4">
        <h2 className="text-xl font-semibold border-b pb-2 flex items-center gap-2">
          <NetworkIcon className="w-5 h-5" />
          Thông số Kết nối (Connection Config)
        </h2>
        <Card className="shadow-sm">
          <CardContent className="pt-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <p className="text-sm font-semibold text-slate-500 mb-1">Base URL</p>
                <code className="bg-slate-100 text-pink-600 px-2 py-1 rounded text-sm block overflow-hidden text-ellipsis whitespace-nowrap">
                  https://api.qtuanph.dev/v1
                </code>
                <p className="text-xs text-muted-foreground mt-1">Thay bằng Domain thật nếu chạy trên server.</p>
              </div>
              <div>
                <p className="text-sm font-semibold text-slate-500 mb-1">Model Name</p>
                <code className="bg-slate-100 text-pink-600 px-2 py-1 rounded text-sm block">chatbot-rag</code> 
                <p className="text-xs text-muted-foreground mt-1">Luôn để <code>chatbot-rag</code>. Hệ thống sẽ tự map sang LLM thực tế ở cấu hình Admin.</p>
              </div>
              <div className="md:col-span-2">
                <p className="text-sm font-semibold text-slate-500 mb-1">API Key (Header: Authorization)</p>
                <div className="bg-slate-100 p-3 rounded text-sm text-slate-700 border border-slate-200 break-all font-mono">
                  Bearer trg_xxxxxxxxxxxxxxxxxxxxxx
                </div>
                <p className="text-xs text-muted-foreground mt-1">Bắt buộc phải có chữ <code>Bearer</code>. Lấy Key này trong phần <strong>Quản trị &gt; Tenants &gt; API Keys</strong>.</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </section>

      <section className="space-y-4 mt-8">
        <h2 className="text-xl font-semibold border-b pb-2 flex items-center gap-2">
          <WebhookIcon className="w-5 h-5 text-indigo-500" />
          Cơ chế Chat phi trạng thái (Stateless Chat)
        </h2>
        <Card className="bg-indigo-50/30 border-indigo-100 shadow-sm">
          <CardContent className="pt-6 space-y-4 text-sm text-slate-700 leading-6">
            <p>
              Giống như OpenAI, hệ thống của chúng tôi <strong>KHÔNG LƯU LẠI</strong> lịch sử hội thoại trên Server để đảm bảo tốc độ cực cao và tránh phình to database.
            </p>
            <p>
              Khi Dev gọi API, Dev <strong>phải gửi kèm toàn bộ lịch sử chat cũ</strong> trong mảng <code>messages</code>. Nền tảng sẽ tự động rút trích câu hỏi cuối cùng của User, tìm kiếm tài liệu (RAG), tự động nhồi ngữ cảnh vào câu prompt (Instruction injection) và ném cho AI đọc.
            </p>
          </CardContent>
        </Card>
      </section>

      <section className="space-y-4 mt-8">
        <h2 className="text-xl font-semibold border-b pb-2 flex items-center gap-2">
          <Code2Icon className="w-5 h-5" />
          Code Mẫu Tích Hợp (SDK Examples)
        </h2>
        
        <Tabs defaultValue="python" className="w-full">
          <TabsList className="grid w-full grid-cols-3 mb-6 bg-slate-100">
            <TabsTrigger value="python" className="data-[state=active]:bg-white">Python (OpenAI SDK)</TabsTrigger>
            <TabsTrigger value="node" className="data-[state=active]:bg-white">Node.js (OpenAI SDK)</TabsTrigger>
            <TabsTrigger value="fetch" className="data-[state=active]:bg-white">Raw Fetch API (cURL)</TabsTrigger>
          </TabsList>
          
          <TabsContent value="python">
            <Card className="border-slate-200">
              <CardHeader className="bg-slate-50 border-b pb-4">
                <CardTitle className="text-base font-semibold">Tích hợp bằng Python</CardTitle>
                <CardDescription className="text-xs">Cài đặt SDK bằng lệnh: <code>pip install openai</code></CardDescription>
              </CardHeader>
              <CardContent className="p-0">
                <pre className="bg-slate-950 text-emerald-400 p-6 overflow-x-auto text-sm leading-relaxed rounded-b-lg">
{`from openai import OpenAI

# Khởi tạo Client, trỏ Base URL về server của chúng ta
client = OpenAI(
    base_url="https://api.qtuanph.dev/v1",
    api_key="YOUR_TENANT_API_KEY", # Lấy mã trg_... từ màn hình API Keys
)

# Gửi request Chat
completion = client.chat.completions.create(
    model="chatbot-rag",
    messages=[
        {"role": "user", "content": "Muốn backup số liệu thì vào mục nào?"}
    ],
    stream=True # Khuyên dùng: Bật stream để lấy kết quả tức thời
)

# Nhận phản hồi real-time in ra terminal
print("AI: ", end="")
for chunk in completion:
    if chunk.choices and chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")
`}
                </pre>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="node">
            <Card className="border-slate-200">
              <CardHeader className="bg-slate-50 border-b pb-4">
                <CardTitle className="text-base font-semibold">Tích hợp bằng Node.js / React / Next.js</CardTitle>
                <CardDescription className="text-xs">Cài đặt SDK bằng lệnh: <code>npm install openai</code></CardDescription>
              </CardHeader>
              <CardContent className="p-0">
                <pre className="bg-slate-950 text-emerald-400 p-6 overflow-x-auto text-sm leading-relaxed rounded-b-lg">
{`import OpenAI from "openai";

const openai = new OpenAI({
  baseURL: "https://api.qtuanph.dev/v1",
  apiKey: "YOUR_TENANT_API_KEY", 
});

async function main() {
  const stream = await openai.chat.completions.create({
    model: "chatbot-rag",
    messages: [
      { role: "user", content: "Xin chào!" },
      { role: "assistant", content: "Chào bạn, tôi có thể giúp gì?" },
      { role: "user", content: "Quy định nghỉ phép năm nay?" } // Câu hỏi mới
    ],
    stream: true,
  });

  process.stdout.write("AI: ");
  for await (const chunk of stream) {
    process.stdout.write(chunk.choices[0]?.delta?.content || "");
  }
}

main();`}
                </pre>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="fetch">
            <Card className="border-slate-200">
              <CardHeader className="bg-slate-50 border-b pb-4">
                <CardTitle className="text-base font-semibold">Gọi API gốc (Không dùng thư viện SDK)</CardTitle>
                <CardDescription className="text-xs">Dành cho Java, C#, PHP hoặc khi bạn muốn test nhanh qua Postman / cURL.</CardDescription>
              </CardHeader>
              <CardContent className="p-0">
                <pre className="bg-slate-950 text-emerald-400 p-6 overflow-x-auto text-sm leading-relaxed rounded-b-lg">
{`fetch("https://api.qtuanph.dev/v1/chat/completions", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "Authorization": "Bearer YOUR_TENANT_API_KEY" // <== Cực kỳ quan trọng
  },
  body: JSON.stringify({
    model: "chatbot-rag",
    messages: [
      { role: "user", content: "Xin chào" }
    ],
    stream: false, // Để false sẽ trả về 1 cục JSON thay vì stream từng chữ
    temperature: 0.7
  })
})
.then(response => response.json())
.then(data => {
  console.log("Câu trả lời của AI:", data.choices[0].message.content);
})
.catch(err => console.error("Lỗi:", err));`}
                </pre>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </section>

      <section className="space-y-4 mt-8">
        <h2 className="text-xl font-semibold border-b pb-2 flex items-center gap-2">
          <TerminalIcon className="w-5 h-5 text-emerald-500" />
          Hiệu ứng gõ phím mượt mà (SSE - Server Sent Events)
        </h2>
        <Card className="shadow-sm">
          <CardContent className="pt-6 space-y-4 leading-6 text-sm text-slate-700">
            <p>
              <strong>Vấn đề:</strong> Nếu AI mất 10 giây để đọc tài liệu và suy nghĩ câu trả lời dài 1000 chữ, người dùng sẽ phải nhìn màn hình loading trống không rất ức chế.
            </p>
            <p>
              <strong>Giải pháp:</strong> Bạn PHẢI truyền tham số <code>stream: true</code> trong code. Khi đó, Server backend sẽ trả dữ liệu về dạng luồng (SSE). AI nghĩ ra được chữ nào, Backend sẽ ngay lập tức đẩy chữ đó về Frontend của bạn.
            </p>
            <p>
              Kết quả là chữ sẽ <strong>chạy rẹt rẹt trên màn hình giống hệt ChatGPT</strong> mà không có độ trễ. Các bộ SDK chính thức như <code>openai-python</code> hoặc thư viện <code>ai</code> của Vercel (Next.js) đã tự động giải mã luồng Stream này giùm bạn.
            </p>
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
