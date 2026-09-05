"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { 
  CopyIcon, 
  CheckCircle2Icon, 
  KeyIcon, 
  InfoIcon, 
  TerminalIcon, 
  CheckIcon, 
  GlobeIcon,
  XIcon,
  LayersIcon,
  ShieldAlertIcon,
} from "lucide-react";

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <Button
      variant="outline"
      size="icon"
      onClick={() => {
        navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      }}
      className="h-7 w-7 rounded-lg"
      title="Sao chép"
    >
      {copied ? <CheckCircle2Icon className="w-3.5 h-3.5 text-emerald-500" /> : <CopyIcon className="w-3.5 h-3.5" />}
    </Button>
  );
}

function CodeBlock({ code }: { code: string }) {
  return (
    <div className="relative group">
      <div className="absolute top-2.5 right-2.5 z-10">
        <CopyButton text={code} />
      </div>
      <pre className="bg-zinc-950 dark:bg-zinc-900 text-zinc-100 p-4 pr-12 rounded-xl text-xs font-mono overflow-x-auto leading-relaxed whitespace-pre border border-border">
        {code}
      </pre>
    </div>
  );
}

export default function ApiReferenceGuidePage() {
  const API_BASE = "https://chatbot-api.sse.net.vn/v1";
  const API_URL = `${API_BASE}/chat/completions`;

  const curlSnippet = `curl -X POST "${API_URL}" \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer trg_YOUR_TENANT_API_KEY" \\
  -d '{
    "model": "chatbot-rag",
    "messages": [
      { "role": "user", "content": "Hướng dẫn quy trình lập hóa đơn bán hàng?" }
    ],
    "stream": false
  }'`;

  const pythonSnippet = `import requests

url = "${API_URL}"
headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer trg_YOUR_TENANT_API_KEY"
}
payload = {
    "model": "chatbot-rag",
    "messages": [
        {"role": "user", "content": "Hướng dẫn quy trình lập hóa đơn bán hàng?"}
    ],
    "stream": False
}

response = requests.post(url, headers=headers, json=payload)
data = response.json()

# Lấy nội dung câu trả lời AI
answer = data['choices'][0]['message']['content']
print("Trả lời:", answer)`;

  const csharpSnippet = `using System;
using System.Net.Http;
using System.Text;
using System.Threading.Tasks;

public class ChatbotService
{
    private static readonly HttpClient client = new HttpClient();

    public async Task<string> CallChatbotAsync(string userQuery)
    {
        string apiUrl = "${API_URL}";
        string apiKey = "YOUR_TENANT_API_KEY";

        var jsonPayload = $@"{{
            ""model"": ""chatbot-rag"",
            ""messages"": [
                {{ ""role"": ""user"", ""content"": ""{userQuery}"" }}
            ],
            ""stream"": false
        }}";

        var request = new HttpRequestMessage(HttpMethod.Post, apiUrl);
        request.Headers.Add("Authorization", $"Bearer {apiKey}");
        request.Content = new StringContent(jsonPayload, Encoding.UTF8, "application/json");

        var response = await client.SendAsync(request);
        return await response.Content.ReadAsStringAsync();
    }
}`;

  return (
    <div className="space-y-8 pb-16 max-w-4xl">
      {/* Header */}
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <h1 className="text-3xl font-bold tracking-tight text-foreground">Đặc tả Kỹ thuật API (API Reference)</h1>
          <Badge variant="default" className="text-xs bg-primary text-primary-foreground">REST API v1</Badge>
        </div>
        <p className="text-sm text-muted-foreground leading-relaxed max-w-3xl">
          Tài liệu đặc tả chuẩn hóa giao tiếp REST API dành cho các đối tác tích hợp hệ thống ERP, CRM, Mobile App và ứng dụng doanh nghiệp.
        </p>
      </div>

      {/* Overview Alert */}
      <Alert className="bg-muted/50 border-border">
        <InfoIcon className="h-5 w-5 text-primary" />
        <AlertTitle className="font-bold text-foreground">Chuẩn giao tiếp OpenAI Compatible Endpoint</AlertTitle>
        <AlertDescription className="text-xs leading-5 mt-1 text-muted-foreground">
          API Chatbot RAG tuân thủ 100% cấu trúc chuẩn <code>/v1/chat/completions</code> của OpenAI, cho phép bạn dễ dàng tích hợp bằng mọi SDK chính thức (OpenAI Python, OpenAI Node.js, cURL...) mà không cần viết lại thư viện kết nối.
        </AlertDescription>
      </Alert>

      {/* ── 1. ĐẶC TẢ API ENDPOINT TABLE ── */}
      <section className="space-y-4">
        <h2 className="text-xl font-bold text-foreground border-b pb-2 flex items-center gap-2">
          <GlobeIcon className="w-5 h-5 text-primary" />
          1. Đặc tả API Endpoint (API Environment Specs)
        </h2>

        <div className="border border-border rounded-xl overflow-hidden bg-card">
          <Table>
            <TableHeader className="bg-muted/40">
              <TableRow>
                <TableHead className="w-[140px] font-bold">Môi trường</TableHead>
                <TableHead className="w-[100px] font-bold">Method</TableHead>
                <TableHead className="font-bold">Endpoint URL</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody className="text-xs font-mono">
              <TableRow>
                <TableCell>
                  <Badge className="bg-emerald-600 hover:bg-emerald-700 text-white font-sans text-[10px]">Production</Badge>
                </TableCell>
                <TableCell>
                  <Badge variant="outline" className="bg-primary/10 text-primary border-primary/20 font-mono font-bold">POST</Badge>
                </TableCell>
                <TableCell className="font-semibold text-foreground">{API_URL}</TableCell>
              </TableRow>
              <TableRow>
                <TableCell>
                  <Badge variant="secondary" className="font-sans text-[10px]">Staging / Local</Badge>
                </TableCell>
                <TableCell>
                  <Badge variant="outline" className="bg-primary/10 text-primary border-primary/20 font-mono font-bold">POST</Badge>
                </TableCell>
                <TableCell className="text-muted-foreground">http://localhost:8000/v1/chat/completions</TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </div>

        {/* HTTP Headers Box */}
        <div className="border border-border rounded-xl p-4 bg-muted/20 space-y-2">
          <h4 className="text-xs font-bold text-foreground flex items-center gap-1.5">
            <KeyIcon className="w-4 h-4 text-primary" /> HTTP Request Headers bắt buộc:
          </h4>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs font-mono">
            <div className="p-2.5 rounded-lg border border-border bg-card">
              <span className="text-muted-foreground block text-[10px] font-sans font-semibold">Content-Type</span>
              <span className="font-semibold text-foreground">application/json</span>
            </div>
            <div className="p-2.5 rounded-lg border border-border bg-card">
              <span className="text-muted-foreground block text-[10px] font-sans font-semibold">Authorization</span>
              <span className="font-semibold text-primary">YOUR_TENANT_API_KEY</span>
            </div>
          </div>
        </div>
      </section>

      {/* ── 2. DỮ LIỆU TRUYỀN VÀO API (REQUEST BODY PAYLOAD) ── */}
      <section className="space-y-4">
        <h2 className="text-xl font-bold text-foreground border-b pb-2 flex items-center gap-2">
          <TerminalIcon className="w-5 h-5 text-primary" />
          2. Dữ liệu truyền vào API (Request Payload Specs)
        </h2>

        <div className="border border-border rounded-xl overflow-hidden bg-card">
          <Table>
            <TableHeader className="bg-muted/40">
              <TableRow>
                <TableHead className="w-[140px] font-bold">Tham số</TableHead>
                <TableHead className="w-[120px] font-bold">Kiểu dữ liệu</TableHead>
                <TableHead className="w-[100px] font-bold text-center">Bắt buộc</TableHead>
                <TableHead className="font-bold">Ý nghĩa &amp; Quy tắc dữ liệu</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody className="text-xs">
              <TableRow>
                <TableCell className="font-mono font-semibold text-foreground">model</TableCell>
                <TableCell className="font-mono text-muted-foreground">String</TableCell>
                <TableCell className="text-center">
                  <CheckIcon className="w-4 h-4 text-emerald-500 mx-auto" />
                </TableCell>
                <TableCell>Tên mô hình RAG xử lý. Mặc định truyền <code className="bg-muted px-1.5 py-0.5 rounded font-mono text-[11px]">chatbot-rag</code>.</TableCell>
              </TableRow>

              <TableRow>
                <TableCell className="font-mono font-semibold text-foreground">messages</TableCell>
                <TableCell className="font-mono text-muted-foreground">Array[Object]</TableCell>
                <TableCell className="text-center">
                  <CheckIcon className="w-4 h-4 text-emerald-500 mx-auto" />
                </TableCell>
                <TableCell>Mảng danh sách các tin nhắn hội thoại theo thứ tự thời gian. Mỗi tin nhắn chứa <code>role</code> và <code>content</code>.</TableCell>
              </TableRow>

              <TableRow>
                <TableCell className="font-mono font-semibold text-foreground pl-6">messages[].role</TableCell>
                <TableCell className="font-mono text-muted-foreground">String</TableCell>
                <TableCell className="text-center">
                  <CheckIcon className="w-4 h-4 text-emerald-500 mx-auto" />
                </TableCell>
                <TableCell>Vai trò người gửi: <code className="bg-muted px-1 rounded font-mono">user</code> (Người dùng) hoặc <code className="bg-muted px-1 rounded font-mono">assistant</code> (Trợ lý AI).</TableCell>
              </TableRow>

              <TableRow>
                <TableCell className="font-mono font-semibold text-foreground pl-6">messages[].content</TableCell>
                <TableCell className="font-mono text-muted-foreground">String</TableCell>
                <TableCell className="text-center">
                  <CheckIcon className="w-4 h-4 text-emerald-500 mx-auto" />
                </TableCell>
                <TableCell>Nội dung câu hỏi hoặc tin nhắn dạng văn bản thô.</TableCell>
              </TableRow>

              <TableRow>
                <TableCell className="font-mono font-semibold text-foreground">stream</TableCell>
                <TableCell className="font-mono text-muted-foreground">Boolean</TableCell>
                <TableCell className="text-center">
                  <XIcon className="w-4 h-4 text-muted-foreground opacity-40 mx-auto" />
                </TableCell>
                <TableCell>Tùy chọn. <code className="bg-muted px-1 rounded font-mono">true</code>: Trả dữ liệu dạng Server-Sent Events (SSE) từng token. <code className="bg-muted px-1 rounded font-mono">false</code>: Trả toàn bộ JSON 1 lần.</TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </div>
      </section>

      {/* ── 3. THAM SỐ API TRẢ VỀ (RESPONSE PAYLOAD SPECS) ── */}
      <section className="space-y-4">
        <h2 className="text-xl font-bold text-foreground border-b pb-2 flex items-center gap-2">
          <LayersIcon className="w-5 h-5 text-primary" />
          3. Tham số API trả về (Response Payload Specs)
        </h2>

        <Tabs defaultValue="non-stream" className="w-full">
          <TabsList className="grid w-full grid-cols-2 max-w-md">
            <TabsTrigger value="non-stream" className="text-xs font-semibold">Chế độ Thường (stream = false)</TabsTrigger>
            <TabsTrigger value="stream" className="text-xs font-semibold">Chế độ Stream (stream = true)</TabsTrigger>
          </TabsList>

          <TabsContent value="non-stream" className="pt-3 space-y-3">
            <div className="border border-border rounded-xl overflow-hidden bg-card">
              <Table>
                <TableHeader className="bg-muted/40">
                  <TableRow>
                    <TableHead className="w-[180px] font-bold">Tham số</TableHead>
                    <TableHead className="w-[120px] font-bold">Kiểu dữ liệu</TableHead>
                    <TableHead className="font-bold">Ý nghĩa dữ liệu</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody className="text-xs">
                  <TableRow>
                    <TableCell className="font-mono font-semibold text-foreground">id</TableCell>
                    <TableCell className="font-mono text-muted-foreground">String</TableCell>
                    <TableCell>Mã định danh phiên trả lời duy nhất dạng UUID.</TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell className="font-mono font-semibold text-foreground">object</TableCell>
                    <TableCell className="font-mono text-muted-foreground">String</TableCell>
                    <TableCell>Loại đối tượng trả về. Cố định là <code className="bg-muted px-1 rounded font-mono">chat.completion</code>.</TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell className="font-mono font-semibold text-foreground">choices[0].message.content</TableCell>
                    <TableCell className="font-mono text-muted-foreground">String</TableCell>
                    <TableCell><strong>Nội dung câu trả lời chuẩn của AI</strong> (Đã được định dạng Markdown chuẩn).</TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell className="font-mono font-semibold text-foreground">usage</TableCell>
                    <TableCell className="font-mono text-muted-foreground">Object</TableCell>
                    <TableCell>Thống kê số token tiêu tốn (<code className="bg-muted px-1 rounded font-mono">prompt_tokens</code>, <code className="bg-muted px-1 rounded font-mono">completion_tokens</code>, <code className="bg-muted px-1 rounded font-mono">total_tokens</code>).</TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell className="font-mono font-semibold text-foreground">citations</TableCell>
                    <TableCell className="font-mono text-muted-foreground">Array[Object]</TableCell>
                    <TableCell>Danh sách tài liệu dẫn chứng trích xuất từ Kho tri thức (<code className="bg-muted px-1 rounded font-mono">title</code>, <code className="bg-muted px-1 rounded font-mono">page_range</code>).</TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </div>
          </TabsContent>

          <TabsContent value="stream" className="pt-3 space-y-3">
            <div className="border border-border rounded-xl p-4 bg-muted/20 space-y-3">
              <p className="text-xs text-muted-foreground leading-relaxed">
                Ở chế độ Stream (<code>stream: true</code>), API sẽ trả về luồng dữ liệu Server-Sent Events (SSE) với từng dòng bắt đầu bằng <code>data: ...</code>:
              </p>
              <CodeBlock
                code={`data: {"id":"conv-123","choices":[{"delta":{"content":"Hướng"}}]}
data: {"id":"conv-123","choices":[{"delta":{"content":" dẫn"}}]}
data: {"id":"conv-123","choices":[{"delta":{"content":" tạo đơn hàng..."}}]}
data: [DONE]`}
              />
            </div>
          </TabsContent>
        </Tabs>
      </section>

      {/* ── 4. BẢNG MÃ LỖI API (ERROR CODES REFERENCE) ── */}
      <section className="space-y-4">
        <h2 className="text-xl font-bold text-foreground border-b pb-2 flex items-center gap-2">
          <ShieldAlertIcon className="w-5 h-5 text-primary" />
          4. Bảng Mã Lỗi API (API Error Codes Reference)
        </h2>

        <div className="border border-border rounded-xl overflow-hidden bg-card">
          <Table>
            <TableHeader className="bg-muted/40">
              <TableRow>
                <TableHead className="w-[100px] font-bold">Mã HTTP</TableHead>
                <TableHead className="w-[160px] font-bold">Tên lỗi (Status Text)</TableHead>
                <TableHead className="font-bold">Nguyên nhân &amp; Hướng xử lý</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody className="text-xs font-mono">
              <TableRow>
                <TableCell><Badge className="bg-emerald-600 text-white font-mono">200 OK</Badge></TableCell>
                <TableCell className="font-semibold text-foreground font-sans">Success</TableCell>
                <TableCell className="font-sans text-muted-foreground">Yêu cầu xử lý thành công hoàn toàn.</TableCell>
              </TableRow>

              <TableRow>
                <TableCell><Badge variant="destructive" className="font-mono">401</Badge></TableCell>
                <TableCell className="font-semibold text-foreground font-sans">Unauthorized</TableCell>
                <TableCell className="font-sans text-muted-foreground">API Key không hợp lệ, sai định dạng hoặc đã bị Admin Thu hồi (Revoked).</TableCell>
              </TableRow>

              <TableRow>
                <TableCell><Badge variant="destructive" className="font-mono">429</Badge></TableCell>
                <TableCell className="font-semibold text-foreground font-sans">Too Many Requests</TableCell>
                <TableCell className="font-sans text-muted-foreground">Vượt quá tốc độ gọi API (Rate Limit RPM) hoặc đã tiêu hết Hạn ngạch Quota tháng của Tenant.</TableCell>
              </TableRow>

              <TableRow>
                <TableCell><Badge variant="destructive" className="font-mono">422</Badge></TableCell>
                <TableCell className="font-semibold text-foreground font-sans">Unprocessable Entity</TableCell>
                <TableCell className="font-sans text-muted-foreground">Dữ liệu JSON truyền lên bị sai cấu trúc hoặc thiếu trường dữ liệu bắt buộc (như `messages`).</TableCell>
              </TableRow>

              <TableRow>
                <TableCell><Badge variant="destructive" className="font-mono">500</Badge></TableCell>
                <TableCell className="font-semibold text-foreground font-sans">Internal Server Error</TableCell>
                <TableCell className="font-sans text-muted-foreground">Lỗi hệ thống Backend API (Vui lòng kiểm tra log hệ thống).</TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </div>
      </section>

      {/* ── 5. CODE MẪU GỌI API TRỰC TIẾP ── */}
      <section className="space-y-4">
        <h2 className="text-xl font-bold text-foreground border-b pb-2 flex items-center gap-2">
          <TerminalIcon className="w-5 h-5 text-primary" />
          5. Mã nguồn mẫu gọi API đa ngôn ngữ (Code Snippets)
        </h2>

        <Tabs defaultValue="curl" className="w-full">
          <TabsList className="grid w-full grid-cols-3 max-w-md">
            <TabsTrigger value="curl" className="text-xs font-semibold">cURL</TabsTrigger>
            <TabsTrigger value="python" className="text-xs font-semibold">Python</TabsTrigger>
            <TabsTrigger value="csharp" className="text-xs font-semibold">C# / ASP.NET</TabsTrigger>
          </TabsList>

          <TabsContent value="curl" className="pt-3">
            <CodeBlock code={curlSnippet} />
          </TabsContent>
          <TabsContent value="python" className="pt-3">
            <CodeBlock code={pythonSnippet} />
          </TabsContent>
          <TabsContent value="csharp" className="pt-3">
            <CodeBlock code={csharpSnippet} />
          </TabsContent>
        </Tabs>
      </section>
    </div>
  );
}
