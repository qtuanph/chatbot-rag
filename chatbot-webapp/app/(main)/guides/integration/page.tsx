"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Code2Icon, TerminalIcon, CpuIcon } from "lucide-react";

export default function IntegrationGuidePage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Tích hợp phần mềm</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Sử dụng Nền tảng RAG như một API (OpenAI Drop-in Replacement).
        </p>
      </div>

      <Alert className="bg-blue-50 border-blue-200">
        <CpuIcon className="h-4 w-4 text-blue-600" />
        <AlertTitle className="text-blue-800 font-bold text-sm">OpenAI Tương thích 100%</AlertTitle>
        <AlertDescription className="text-blue-700 text-xs">
          Bạn không cần học API mới! Nếu phần mềm của bạn đã hỗ trợ ChatGPT/OpenAI, bạn chỉ việc đổi <code>Base URL</code> và <code>API Key</code> là xong.
        </AlertDescription>
      </Alert>

      <section className="space-y-4">
        <h2 className="text-lg font-semibold">Thông tin kết nối cơ bản</h2>
        <Card>
          <CardContent className="pt-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <p className="text-sm font-semibold text-slate-500 mb-1">Base URL</p>
                <code className="bg-slate-100 text-pink-600 px-2 py-1 rounded">https://api.qtuanph.dev/v1</code>
              </div>
              <div>
                <p className="text-sm font-semibold text-slate-500 mb-1">Model Name</p>
                <code className="bg-slate-100 text-pink-600 px-2 py-1 rounded">chatbot-rag</code> 
                <span className="text-sm text-muted-foreground ml-2">(Có thể truyền bất kỳ text nào)</span>
              </div>
              <div className="md:col-span-2">
                <p className="text-sm font-semibold text-slate-500 mb-1">API Key</p>
                <div className="bg-slate-100 p-2 rounded text-sm text-slate-700 border border-slate-200 break-all">
                  <code>trg_... (Lấy trong phần Cài đặt Tenant)</code>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </section>

      <section className="space-y-4">
        <h2 className="text-lg font-semibold flex items-center gap-2">
          <Code2Icon className="w-5 h-5" />
          Code Mẫu Tích Hợp
        </h2>
        
        <Tabs defaultValue="python" className="w-full">
          <TabsList className="grid w-full grid-cols-3 mb-6">
            <TabsTrigger value="python">Python (OpenAI SDK)</TabsTrigger>
            <TabsTrigger value="node">Node.js (OpenAI SDK)</TabsTrigger>
            <TabsTrigger value="fetch">Raw Fetch API (JS)</TabsTrigger>
          </TabsList>
          
          <TabsContent value="python">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Dùng thư viện OpenAI của Python</CardTitle>
                <CardDescription className="text-xs">Cài đặt: <code>pip install openai</code></CardDescription>
              </CardHeader>
              <CardContent>
                <pre className="bg-slate-950 text-slate-50 p-4 rounded-lg overflow-x-auto text-sm">
{`from openai import OpenAI

client = OpenAI(
    base_url="https://api.qtuanph.dev/v1",
    api_key="YOUR_TENANT_API_KEY", # Ví dụ: trg_fkbZ...
)

completion = client.chat.completions.create(
    model="chatbot-rag",
    messages=[
        {"role": "user", "content": "Muốn backup số liệu thì vào mục nào?"}
    ],
    stream=True # Bật tính năng gõ từng chữ
)

# Nhận phản hồi real-time
for chunk in completion:
    if chunk.choices and chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")
`}
                </pre>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="node">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Dùng thư viện OpenAI của Node.js / React</CardTitle>
                <CardDescription className="text-xs">Cài đặt: <code>npm install openai</code></CardDescription>
              </CardHeader>
              <CardContent>
                <pre className="bg-slate-950 text-slate-50 p-4 rounded-lg overflow-x-auto text-sm">
{`import OpenAI from "openai";

const openai = new OpenAI({
  baseURL: "https://api.qtuanph.dev/v1",
  apiKey: "YOUR_TENANT_API_KEY", // Thay bằng Key của bạn
});

async function main() {
  const stream = await openai.chat.completions.create({
    model: "chatbot-rag",
    messages: [{ role: "user", content: "Chính sách nhân sự mới nhất?" }],
    stream: true,
  });

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
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Gốc (Không dùng SDK)</CardTitle>
                <CardDescription className="text-xs">Gọi REST API thuần cho các ngôn ngữ không có SDK (Java, PHP, C#...)</CardDescription>
              </CardHeader>
              <CardContent>
                <pre className="bg-slate-950 text-slate-50 p-4 rounded-lg overflow-x-auto text-sm">
{`fetch("https://api.qtuanph.dev/v1/chat/completions", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "Authorization": "Bearer YOUR_TENANT_API_KEY"
  },
  body: JSON.stringify({
    model: "chatbot-rag",
    messages: [
      { role: "user", content: "Xin chào" }
    ],
    stream: false, // Để false để lấy kết quả 1 cục JSON cho dễ parse
    temperature: 0.7
  })
})
.then(response => response.json())
.then(data => console.log(data.choices[0].message.content));`}
                </pre>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </section>

      <section className="space-y-4">
        <h2 className="text-lg font-semibold flex items-center gap-2">
          <TerminalIcon className="w-5 h-5" />
          Hiệu ứng gõ phím mượt mà (SSE - Server Sent Events)
        </h2>
        <Card className="bg-slate-50/50">
          <CardContent className="pt-6 space-y-4 leading-6 text-sm text-slate-700">
            <p>
              Nếu AI mất 10 giây để đọc tài liệu và suy nghĩ câu trả lời, người dùng sẽ phải đợi mòn mỏi. 
              Đó là lý do bạn nên dùng thuộc tính <code>stream: true</code>.
            </p>
            <p>
              Khi truyền <code>stream: true</code>, server sẽ gửi trả dữ liệu từng mảnh một (chunks) ngay khi AI vừa suy nghĩ ra chữ đó. Nhờ vậy, chữ sẽ chạy rẹt rẹt trên màn hình giống hệt ChatGPT mà không có độ trễ. 
              Các bộ SDK chính thức như `openai-python` đã tự động đóng gói việc giải mã stream này, bạn chỉ việc dùng vòng lặp `for` như code mẫu phía trên là xong!
            </p>
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
