"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { TerminalIcon, CpuIcon, WebhookIcon, NetworkIcon, ShieldAlertIcon, PaintbrushIcon, FileTextIcon, CopyIcon, CheckCircle2Icon, KeyIcon, DatabaseIcon, RocketIcon } from "lucide-react";
import { useState } from "react";

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = () => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <button onClick={handleCopy} className="absolute top-4 right-4 p-2 bg-slate-800 text-slate-300 rounded hover:bg-slate-700 transition-colors z-10">
      {copied ? <CheckCircle2Icon className="w-4 h-4 text-emerald-400" /> : <CopyIcon className="w-4 h-4" />}
    </button>
  );
}

export default function IntegrationGuidePage() {
  return (
    <div className="space-y-8 pb-16">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-slate-900">Hướng Dẫn Tích Hợp Toàn Diện (End-to-End)</h1>
        <p className="text-base text-slate-600 mt-2 leading-relaxed max-w-4xl">
          Tài liệu này sẽ hướng dẫn bạn chi tiết từng bước một: từ lúc khởi tạo không gian làm việc (Tenant), huấn luyện dữ liệu, cho đến việc copy mã nguồn dán thẳng vào phần mềm của bạn để chạy thực tế.
        </p>
      </div>

      {/* BƯỚC 1: KHỞI TẠO TENANT VÀ DATA */}
      <section className="relative">
        <div className="absolute left-4 top-0 bottom-0 w-0.5 bg-slate-200"></div>
        <div className="relative pl-12">
          <div className="absolute left-0 top-1 w-8 h-8 bg-blue-600 text-white rounded-full flex items-center justify-center font-bold shadow-md z-10">1</div>
          <h2 className="text-2xl font-bold text-slate-800 mb-4 flex items-center gap-2">
            <DatabaseIcon className="w-6 h-6 text-blue-600" />
            Khởi tạo Không gian (Tenant) & Huấn luyện AI
          </h2>
          <Card className="border-slate-200 shadow-sm">
            <CardContent className="pt-6 space-y-4 text-slate-700">
              <p>Trước khi tích hợp code, Chatbot cần phải biết nó đang phục vụ cho tổ chức nào và kiến thức của nó là gì. Vui lòng thực hiện trên trang Quản trị (Admin Panel) này:</p>
              <ul className="list-decimal pl-5 space-y-3 font-medium text-slate-800">
                <li>
                  <strong className="text-blue-700">Tạo Tenant:</strong> Vào mục <span className="bg-slate-100 px-2 py-1 rounded border">Quản lý Tenant</span>, bấm tạo mới một Tenant đại diện cho Phần mềm/Công ty của bạn.
                </li>
                <li>
                  <strong className="text-blue-700">Tải tài liệu (Huấn luyện AI):</strong> Vào mục <span className="bg-slate-100 px-2 py-1 rounded border">Quản lý Tài liệu</span>, upload các file PDF, Word, Excel chứa nghiệp vụ và hướng dẫn sử dụng của công ty bạn. Hệ thống sẽ tự động vector hóa để AI học.
                </li>
                <li>
                  <strong className="text-blue-700">Lấy chìa khóa (API Key):</strong> Quay lại mục <span className="bg-slate-100 px-2 py-1 rounded border">Cấu hình Tenant</span>, tạo một <strong>API Key</strong> mới. Hãy sao chép chuỗi mã (bắt đầu bằng <code>trg_...</code>) và cất giữ cẩn thận. Bạn sẽ cần nó ở Bước 4.
                </li>
              </ul>
            </CardContent>
          </Card>
        </div>
      </section>

      {/* BƯỚC 2: NHÚNG MARKDOWN */}
      <section className="relative">
        <div className="absolute left-4 top-0 bottom-0 w-0.5 bg-slate-200"></div>
        <div className="relative pl-12">
          <div className="absolute left-0 top-1 w-8 h-8 bg-indigo-600 text-white rounded-full flex items-center justify-center font-bold shadow-md z-10">2</div>
          <h2 className="text-2xl font-bold text-slate-800 mb-4 flex items-center gap-2">
            <FileTextIcon className="w-6 h-6 text-indigo-600" />
            Nhúng thư viện biên dịch Markdown
          </h2>
          <p className="text-slate-600 mb-4">
            AI trả lời dưới định dạng Markdown (có bảng biểu, in đậm). Mở file giao diện gốc của phần mềm bạn (VD: <code>index.html</code> hoặc <code>Main.master</code>), dán đoạn mã này vào trong thẻ <code>&lt;head&gt;</code>:
          </p>
          <div className="relative">
            <CopyButton text={'<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>\n<script>\n    marked.setOptions({ breaks: true, gfm: true });\n</script>'} />
            <pre className="bg-slate-950 text-indigo-300 p-5 rounded-lg text-sm overflow-x-auto">
{`<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<script>
    // Cấu hình xuống dòng tự nhiên và hỗ trợ Github Flavored Markdown
    marked.setOptions({ breaks: true, gfm: true });
</script>`}
            </pre>
          </div>
        </div>
      </section>

      {/* BƯỚC 3: GIAO DIỆN CHATBOT */}
      <section className="relative">
        <div className="absolute left-4 top-0 bottom-0 w-0.5 bg-slate-200"></div>
        <div className="relative pl-12">
          <div className="absolute left-0 top-1 w-8 h-8 bg-pink-600 text-white rounded-full flex items-center justify-center font-bold shadow-md z-10">3</div>
          <h2 className="text-2xl font-bold text-slate-800 mb-4 flex items-center gap-2">
            <PaintbrushIcon className="w-6 h-6 text-pink-600" />
            Thêm CSS Giao diện chuẩn (Vanilla CSS)
          </h2>
          <p className="text-slate-600 mb-4">
            Dán khối CSS này vào thẻ <code>&lt;style&gt;</code>. Bộ CSS này được code thuần 100%, độc lập hoàn toàn, cam kết <strong>không làm vỡ giao diện</strong> (không conflict Tailwind/Bootstrap) của phần mềm hiện tại.
          </p>
          <div className="relative">
            <CopyButton text={`#chatbot-container { position: fixed; bottom: 20px; right: 20px; z-index: 1000; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
#chatbot-icon { width: 60px; height: 60px; background: linear-gradient(135deg, #E3ECFE, #C7D6FD); border-radius: 50%; cursor: pointer; display: flex; align-items: center; justify-content: center; box-shadow: 0 4px 20px rgba(227, 236, 254, 0.3); transition: all 0.3s; }
#chatbot-icon:hover { transform: translateY(-2px); box-shadow: 0 8px 25px rgba(227, 236, 254, 0.4); }
#chatbot-icon img { width: 32px; height: 32px; filter: brightness(0) invert(0.2); }
#chatbot-box { display: none; width: 380px; height: 500px; background: #ffffff; border-radius: 20px; box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15); margin-top: 15px; margin-left: -320px; overflow: hidden; border: 1px solid rgba(0, 0, 0, 0.05); }
#chatbot-header { background: linear-gradient(135deg, #E3ECFE, #C7D6FD); color: #2d3748; padding: 20px; text-align: center; }
#chatbot-header h3 { font-size: 18px; font-weight: 600; margin: 0; }
#chatbot-header p { font-size: 12px; opacity: 0.9; margin: 5px 0 0 0; }
#chatbot-messages { height: 340px; overflow-y: auto; padding: 20px; background: #f8fafc; }
.message { margin: 15px 0; max-width: 85%; word-wrap: break-word; font-size: 14px; line-height: 1.5; }
.message.user { background: linear-gradient(135deg, #E3ECFE, #C7D6FD); color: #2d3748; margin-left: auto; text-align: right; padding: 12px 16px; border-radius: 18px 18px 6px 18px; }
.message.bot { background: white; color: #2d3748; margin-right: auto; padding: 12px 16px; border-radius: 18px 18px 18px 6px; border: 1px solid #e2e8f0; border-left: 3px solid #E3ECFE; }
.timestamp { font-size: 10px; opacity: 0.7; margin-top: 5px; }
#chatbot-input { padding: 20px; background: white; border-top: 1px solid #e2e8f0; display: flex; gap: 10px; }
#user-input { flex: 1; padding: 12px 16px; border: 2px solid #e2e8f0; border-radius: 20px; font-size: 14px; outline: none; background: #f8fafc; }
#user-input:focus { border-color: #E3ECFE; background: white; }
.send-btn { background: linear-gradient(135deg, #E3ECFE, #C7D6FD); color: #2d3748; border: none; border-radius: 12px; padding: 8px; cursor: pointer; width: 40px; height: 40px; }`} />
            <pre className="bg-slate-950 text-pink-300 p-5 rounded-lg text-sm overflow-x-auto h-64">
{`#chatbot-container { position: fixed; bottom: 20px; right: 20px; z-index: 1000; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
#chatbot-icon { width: 60px; height: 60px; background: linear-gradient(135deg, #E3ECFE, #C7D6FD); border-radius: 50%; cursor: pointer; display: flex; align-items: center; justify-content: center; box-shadow: 0 4px 20px rgba(227, 236, 254, 0.3); transition: all 0.3s; }
#chatbot-icon:hover { transform: translateY(-2px); box-shadow: 0 8px 25px rgba(227, 236, 254, 0.4); }
#chatbot-icon img { width: 32px; height: 32px; filter: brightness(0) invert(0.2); }
#chatbot-box { display: none; width: 380px; height: 500px; background: #ffffff; border-radius: 20px; box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15); margin-top: 15px; margin-left: -320px; overflow: hidden; border: 1px solid rgba(0, 0, 0, 0.05); }
#chatbot-header { background: linear-gradient(135deg, #E3ECFE, #C7D6FD); color: #2d3748; padding: 20px; text-align: center; }
#chatbot-header h3 { font-size: 18px; font-weight: 600; margin: 0; }
#chatbot-header p { font-size: 12px; opacity: 0.9; margin: 5px 0 0 0; }
#chatbot-messages { height: 340px; overflow-y: auto; padding: 20px; background: #f8fafc; }
.message { margin: 15px 0; max-width: 85%; word-wrap: break-word; font-size: 14px; line-height: 1.5; }
.message.user { background: linear-gradient(135deg, #E3ECFE, #C7D6FD); color: #2d3748; margin-left: auto; text-align: right; padding: 12px 16px; border-radius: 18px 18px 6px 18px; }
.message.bot { background: white; color: #2d3748; margin-right: auto; padding: 12px 16px; border-radius: 18px 18px 18px 6px; border: 1px solid #e2e8f0; border-left: 3px solid #E3ECFE; }
.timestamp { font-size: 10px; opacity: 0.7; margin-top: 5px; }
#chatbot-input { padding: 20px; background: white; border-top: 1px solid #e2e8f0; display: flex; gap: 10px; }
#user-input { flex: 1; padding: 12px 16px; border: 2px solid #e2e8f0; border-radius: 20px; font-size: 14px; outline: none; background: #f8fafc; }
#user-input:focus { border-color: #E3ECFE; background: white; }
.send-btn { background: linear-gradient(135deg, #E3ECFE, #C7D6FD); color: #2d3748; border: none; border-radius: 12px; padding: 8px; cursor: pointer; width: 40px; height: 40px; }`}
            </pre>
          </div>
        </div>
      </section>

      {/* BƯỚC 4: JAVASCRIPT & API */}
      <section className="relative">
        <div className="absolute left-4 top-0 bottom-0 w-0.5 bg-slate-200"></div>
        <div className="relative pl-12">
          <div className="absolute left-0 top-1 w-8 h-8 bg-amber-500 text-white rounded-full flex items-center justify-center font-bold shadow-md z-10">4</div>
          <h2 className="text-2xl font-bold text-slate-800 mb-4 flex items-center gap-2">
            <TerminalIcon className="w-6 h-6 text-amber-500" />
            Mã Javascript Core (Gọi API & Trí nhớ)
          </h2>
          <p className="text-slate-600 mb-4">
            Dán đoạn JS sau vào ngay trước thẻ đóng <code>&lt;/body&gt;</code>. Bộ mã này sẽ tự động sinh HTML, gán sự kiện thu nhỏ/phóng to, và đặc biệt là <strong>tự động nhớ 6 câu chat gần nhất</strong> để AI hiểu mạch hội thoại.<br/>
            <strong className="text-red-500">Quan trọng:</strong> Thay <code>YOUR_API_KEY_HERE</code> bằng chìa khóa bạn đã lấy ở Bước 1.
          </p>
          <div className="relative">
            <CopyButton text={`// Tự động sinh giao diện HTML
document.body.insertAdjacentHTML('beforeend', \`
    <div id="chatbot-container">
        <div id="chatbot-icon">
            <img src="https://storage-ic.icenter.ai/smartbot-v2/chatbot_images/12282023/dc64a85b-9c28-4f73-ad3f-81025ab81833.png" alt="Chatbot">
        </div>
        <div id="chatbot-box">
            <div id="chatbot-header">
                <h3>Trợ Lý AI Doanh Nghiệp</h3>
                <p>Hỗ trợ thông minh 24/7</p>
            </div>
            <div id="chatbot-messages">
                <div class="message bot">Xin chào! Tôi có thể giúp gì cho bạn?</div>
            </div>
            <div id="chatbot-input">
                <input type="text" id="user-input" placeholder="Nhập câu hỏi..." onkeypress="if(event.key === 'Enter') sendMessage()">
                <button class="send-btn" onclick="sendMessage()">Gửi</button>
            </div>
        </div>
    </div>
\`);

// Bật/Tắt Chatbox
document.getElementById('chatbot-icon').addEventListener('click', () => {
    const box = document.getElementById('chatbot-box');
    box.style.display = box.style.display === 'none' ? 'block' : 'none';
    if(box.style.display === 'block') document.getElementById('user-input').focus();
});

// === CẤU HÌNH KẾT NỐI API ===
const LLM_API_URL = "https://api.qtuanph.dev/v1/chat/completions";
const API_KEY = "Bearer YOUR_API_KEY_HERE"; // THAY KEY CỦA BẠN VÀO ĐÂY

// === BỘ NHỚ NGỮ CẢNH (Nhớ 6 tin nhắn) ===
let chatContext = { history: [], isTyping: false };
const MAX_CONTEXT = 6;

async function sendMessage() {
    if (chatContext.isTyping) return;
    const input = document.getElementById('user-input');
    const question = input.value.trim();
    if (!question) return;

    chatContext.isTyping = true;
    input.value = '';
    
    const chatBox = document.getElementById('chatbot-messages');
    
    // Hiển thị câu hỏi của User
    chatBox.insertAdjacentHTML('beforeend', \`<div class="message user">\${question}</div>\`);
    chatBox.scrollTop = chatBox.scrollHeight;

    // LƯU CÂU HỎI VÀO BỘ NHỚ
    chatContext.history.push({ role: "user", content: question });
    const recentMessages = chatContext.history.slice(-MAX_CONTEXT);

    try {
        const payload = {
            model: "default", // Backend tự map sang LLM thực tế
            messages: [
                { role: "system", content: "Ngữ cảnh: Người dùng đang thao tác trên phần mềm." },
                ...recentMessages // Truyền toàn bộ lịch sử
            ],
            stream: false
        };

        const res = await fetch(LLM_API_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': API_KEY },
            body: JSON.stringify(payload)
        });

        const data = await res.json();
        let answer = "Không lấy được dữ liệu.";
        if (data.choices && data.choices[0]?.message) {
            answer = data.choices[0].message.content;
            // LƯU CÂU TRẢ LỜI CỦA AI VÀO BỘ NHỚ
            chatContext.history.push({ role: "assistant", content: answer });
        }

        // Render Markdown ra HTML bằng marked.js
        const botHtml = marked.parse(answer);
        chatBox.insertAdjacentHTML('beforeend', \`<div class="message bot">\${botHtml}</div>\`);
        
    } catch (err) {
        chatBox.insertAdjacentHTML('beforeend', \`<div class="message bot" style="color: red;">Lỗi kết nối API.</div>\`);
    } finally {
        chatContext.isTyping = false;
        chatBox.scrollTop = chatBox.scrollHeight;
    }
}
`} />
            <pre className="bg-slate-950 text-amber-300 p-5 rounded-lg text-sm overflow-x-auto h-96">
{`// Tự động sinh giao diện HTML
document.body.insertAdjacentHTML('beforeend', \`
    <div id="chatbot-container">
        <div id="chatbot-icon">
            <img src="https://storage-ic.icenter.ai/smartbot-v2/chatbot_images/12282023/dc64a85b-9c28-4f73-ad3f-81025ab81833.png" alt="Chatbot">
        </div>
        <div id="chatbot-box">
            <div id="chatbot-header">
                <h3>Trợ Lý AI Doanh Nghiệp</h3>
                <p>Hỗ trợ thông minh 24/7</p>
            </div>
            <div id="chatbot-messages">
                <div class="message bot">Xin chào! Tôi có thể giúp gì cho bạn?</div>
            </div>
            <div id="chatbot-input">
                <input type="text" id="user-input" placeholder="Nhập câu hỏi..." onkeypress="if(event.key === 'Enter') sendMessage()">
                <button class="send-btn" onclick="sendMessage()">Gửi</button>
            </div>
        </div>
    </div>
\`);

// Bật/Tắt Chatbox
document.getElementById('chatbot-icon').addEventListener('click', () => {
    const box = document.getElementById('chatbot-box');
    box.style.display = box.style.display === 'none' ? 'block' : 'none';
    if(box.style.display === 'block') document.getElementById('user-input').focus();
});

// === CẤU HÌNH KẾT NỐI API ===
const LLM_API_URL = "https://api.qtuanph.dev/v1/chat/completions";
const API_KEY = "Bearer YOUR_API_KEY_HERE"; // THAY KEY CỦA BẠN VÀO ĐÂY

// === BỘ NHỚ NGỮ CẢNH (Nhớ 6 tin nhắn) ===
let chatContext = { history: [], isTyping: false };
const MAX_CONTEXT = 6;

async function sendMessage() {
    if (chatContext.isTyping) return;
    const input = document.getElementById('user-input');
    const question = input.value.trim();
    if (!question) return;

    chatContext.isTyping = true;
    input.value = '';
    
    const chatBox = document.getElementById('chatbot-messages');
    
    // Hiển thị câu hỏi của User
    chatBox.insertAdjacentHTML('beforeend', \`<div class="message user">\${question}</div>\`);
    chatBox.scrollTop = chatBox.scrollHeight;

    // LƯU CÂU HỎI VÀO BỘ NHỚ
    chatContext.history.push({ role: "user", content: question });
    const recentMessages = chatContext.history.slice(-MAX_CONTEXT);

    try {
        const payload = {
            model: "default", // Backend tự map sang LLM thực tế
            messages: [
                { role: "system", content: "Ngữ cảnh: Người dùng đang thao tác trên phần mềm." },
                ...recentMessages // Truyền toàn bộ lịch sử
            ],
            stream: false
        };

        const res = await fetch(LLM_API_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': API_KEY },
            body: JSON.stringify(payload)
        });

        const data = await res.json();
        let answer = "Không lấy được dữ liệu.";
        if (data.choices && data.choices[0]?.message) {
            answer = data.choices[0].message.content;
            // LƯU CÂU TRẢ LỜI CỦA AI VÀO BỘ NHỚ
            chatContext.history.push({ role: "assistant", content: answer });
        }

        // Render Markdown ra HTML bằng marked.js
        const botHtml = marked.parse(answer);
        chatBox.insertAdjacentHTML('beforeend', \`<div class="message bot">\${botHtml}</div>\`);
        
    } catch (err) {
        chatBox.insertAdjacentHTML('beforeend', \`<div class="message bot" style="color: red;">Lỗi kết nối API.</div>\`);
    } finally {
        chatContext.isTyping = false;
        chatBox.scrollTop = chatBox.scrollHeight;
    }
}
`}
            </pre>
          </div>
        </div>
      </section>

      {/* BƯỚC 5: ĐƯA LÊN PRODUCTION */}
      <section className="relative">
        <div className="absolute left-4 top-0 bottom-0 w-0 bg-transparent"></div>
        <div className="relative pl-12">
          <div className="absolute left-0 top-1 w-8 h-8 bg-emerald-600 text-white rounded-full flex items-center justify-center font-bold shadow-md z-10"><RocketIcon className="w-4 h-4"/></div>
          <h2 className="text-2xl font-bold text-slate-800 mb-4 flex items-center gap-2">
            Đưa Lên Môi Trường Thực Tế (Go Live)
          </h2>
          <Alert className="bg-amber-50 border-amber-200">
            <ShieldAlertIcon className="h-5 w-5 text-amber-600" />
            <AlertTitle className="text-amber-800 font-bold text-base">Cảnh Báo Về Bảo Mật & Lỗi CORS</AlertTitle>
            <AlertDescription className="text-amber-700 text-sm leading-6 mt-2">
              <p className="mb-2">Khi bạn dùng trình duyệt (Chrome, Safari) của phần mềm cũ gọi thẳng đến tên miền <code>api.qtuanph.dev</code>, sẽ có 2 vấn đề lớn xảy ra:</p>
              <ul className="list-decimal pl-5 space-y-1 font-medium mb-3">
                <li>Bị trình duyệt chặn lại vì lỗi <strong>Cross-Origin (CORS)</strong>.</li>
                <li>Ai ấn F12 cũng xem được mã <strong>API Key</strong> của bạn ở trên (Vô cùng nguy hiểm).</li>
              </ul>
              <p><strong>Cách giải quyết đúng chuẩn doanh nghiệp:</strong> Không nhúng <code>API_KEY</code> vào Javascript Frontend. Hãy tạo một file Proxy ẩn ở Backend của bạn (Ví dụ: <code>ChatbotProxy.ashx</code> với .NET, hoặc 1 route API bằng PHP/NodeJS). Trình duyệt gọi Proxy nội bộ, Proxy nội bộ gắn Header Authorization rồi gọi tới RAG API. Khi đó sẽ tránh được mọi lỗi CORS và bảo mật tuyệt đối API Key.</p>
            </AlertDescription>
          </Alert>
        </div>
      </section>
    </div>
  );
}
