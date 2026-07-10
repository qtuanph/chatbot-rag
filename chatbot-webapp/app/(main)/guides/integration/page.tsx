"use client";

import { useState, useRef, useEffect } from "react";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  ShieldAlertIcon,
  CopyIcon,
  CheckCircle2Icon,
  KeyIcon,
  DatabaseIcon,
  RocketIcon,
  CodeIcon,
  ZapIcon,
  InfoIcon,
  SendIcon,
  EyeIcon,
  EyeOffIcon,
  RefreshCwIcon,
  TerminalIcon,
  ThumbsUpIcon,
  ThumbsDownIcon,
  DownloadIcon,
} from "lucide-react";
import ReactMarkdown from "react-markdown";

/* ─── Copy Button ─────────────────────────────────────────────── */
function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={() => {
        navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      }}
      className="absolute top-3 right-3 p-1.5 bg-muted text-muted-foreground hover:bg-accent rounded border transition-colors z-10"
      title="Sao chép"
    >
      {copied ? <CheckCircle2Icon className="w-4 h-4 text-emerald-500" /> : <CopyIcon className="w-4 h-4" />}
    </button>
  );
}

function CodeBlock({ code, lang = "" }: { code: string; lang?: string }) {
  return (
    <div className="relative">
      <CopyButton text={code} />
      <pre className="bg-zinc-950 dark:bg-zinc-900 text-zinc-100 p-5 pr-12 rounded-lg text-xs overflow-x-auto leading-relaxed whitespace-pre font-mono">
        {code}
      </pre>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════ */
const API_BASE = "https://api.qtuanph.dev/v1";
const API_URL = `${API_BASE}/chat/completions`;
const PLACEHOLDER_KEY = "trg_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx";

/* ─── Code strings ────────────────────────────────────────────── */

const webConfigCode = `<!-- Web.config -->
<configuration>
  <appSettings>
    <add key="Chatbot_ApiUrl"  value="${API_URL}" />
    <add key="Chatbot_ApiKey"  value="${PLACEHOLDER_KEY}" />
  </appSettings>
</configuration>`;

const curlCode = `curl -X POST "${API_URL}" \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer ${PLACEHOLDER_KEY}" \\
  -d '{
    "model": "chatbot-rag",
    "messages": [
      { "role": "user", "content": "Hướng dẫn tạo đơn hàng mới?" }
    ],
    "stream": false
  }'`;

const pythonCode = `from openai import OpenAI

client = OpenAI(
    base_url="${API_BASE}",
    api_key="${PLACEHOLDER_KEY}",
)

# Không stream (nhận toàn bộ 1 lần)
response = client.chat.completions.create(
    model="chatbot-rag",
    messages=[
        {"role": "user", "content": "Hướng dẫn tạo đơn hàng mới?"}
    ]
)
print(response.choices[0].message.content)

# Streaming (nhận từng token)
stream = client.chat.completions.create(
    model="chatbot-rag",
    messages=[{"role": "user", "content": "Hướng dẫn tạo đơn hàng mới?"}],
    stream=True,
)
for chunk in stream:
    print(chunk.choices[0].delta.content or "", end="", flush=True)`;

const nodejsCode = `import OpenAI from "openai";

const client = new OpenAI({
  baseURL: "${API_BASE}",
  apiKey: "${PLACEHOLDER_KEY}",
});

// Không stream
const response = await client.chat.completions.create({
  model: "chatbot-rag",
  messages: [{ role: "user", content: "Hướng dẫn tạo đơn hàng mới?" }],
});
console.log(response.choices[0].message.content);

// Streaming
const stream = client.chat.completions.stream({
  model: "chatbot-rag",
  messages: [{ role: "user", content: "Hướng dẫn tạo đơn hàng mới?" }],
});
for await (const chunk of stream) {
  process.stdout.write(chunk.choices[0]?.delta?.content ?? "");
}`;

const cssCode = `/* ===== Chatbot Container ===== */
#chatbot-container, #chatbot-container * { box-sizing: border-box; }

/* Nút mở chatbot - cố định góc dưới phải */
#chatbot-icon {
    position: fixed; bottom: 24px; right: 24px; z-index: 9999;
    width: 60px; height: 60px;
    background: linear-gradient(135deg, #667eea, #764ba2);
    border-radius: 50%; cursor: pointer;
    display: flex; align-items: center; justify-content: center;
    box-shadow: 0 4px 20px rgba(102,126,234,0.5);
    transition: transform 0.3s cubic-bezier(0.34,1.56,0.64,1), box-shadow 0.3s ease;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}
#chatbot-icon:hover { transform: scale(1.1) translateY(-2px); box-shadow: 0 8px 30px rgba(102,126,234,0.6); }
#chatbot-icon:active { transform: scale(0.95); }
#chatbot-icon img { width: 32px; height: 32px; filter: brightness(0) invert(1); }

/* Badge xanh đang hoạt động */
#chatbot-icon::after {
    content: ''; position: absolute; top: 4px; right: 4px;
    width: 10px; height: 10px; background: #22c55e;
    border-radius: 50%; border: 2px solid white;
    animation: pulse-badge 2s infinite;
}
@keyframes pulse-badge {
    0%, 100% { transform: scale(1); opacity: 1; }
    50% { transform: scale(1.3); opacity: 0.7; }
}

/* Hộp chat - cố định ngay trên nút */
#chatbot-box {
    position: fixed; bottom: 96px; right: 24px; z-index: 9998;
    width: 380px; height: 520px;
    background: #ffffff; border-radius: 20px;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15), 0 4px 20px rgba(102, 126, 234, 0.1);
    overflow: hidden; border: 1px solid rgba(102, 126, 234, 0.15);
    display: none; transform-origin: bottom right;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}
#chatbot-box.is-open {
    display: flex; flex-direction: column;
    animation: chatbox-open 0.35s cubic-bezier(0.34, 1.56, 0.64, 1) forwards;
}
#chatbot-box.is-closing {
    display: flex; flex-direction: column;
    animation: chatbox-close 0.25s ease-in forwards;
}
@keyframes chatbox-open  { from { opacity:0; transform:scale(0.85) translateY(20px); } to { opacity:1; transform:scale(1) translateY(0); } }
@keyframes chatbox-close { from { opacity:1; transform:scale(1) translateY(0); } to { opacity:0; transform:scale(0.85) translateY(20px); } }

/* Header */
#chatbot-header {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white; padding: 18px 20px; text-align: center;
    position: relative; overflow: hidden; flex-shrink: 0;
}
#chatbot-header::before {
    content: ''; position: absolute; top: -50%; left: -50%;
    width: 200%; height: 200%;
    background: radial-gradient(circle at 30% 50%, rgba(255,255,255,0.08) 0%, transparent 60%);
    pointer-events: none;
}
/* Nút đóng (X) - góc phải */
#chatbot-close {
    position: absolute; top: 10px; right: 10px;
    background: rgba(255,255,255,0.2); border: none; color: white;
    width: 36px; height: 36px; border-radius: 50%; cursor: pointer;
    display: flex; align-items: center; justify-content: center;
    font-size: 20px; transition: background 0.2s; line-height: 1;
}
#chatbot-close:hover { background: rgba(255,255,255,0.35); }

/* Nút reset - góc trái */
#chatbot-reset {
    position: absolute; top: 10px; left: 10px;
    background: rgba(255,255,255,0.2); border: none; color: white;
    width: 36px; height: 36px; border-radius: 50%; cursor: pointer;
    display: flex; align-items: center; justify-content: center;
    transition: background 0.2s, transform 0.3s ease;
}
#chatbot-reset:hover { background: rgba(255,255,255,0.35); transform: rotate(-180deg); }

/* QUAN TRỌNG: tắt pointer-events trên nội dung trong nút
   để click vào dấu X hoặc SVG vẫn kích hoạt đúng nút */
#chatbot-close *, #chatbot-reset * { pointer-events: none; }

#chatbot-header h3 { font-size: 18px; font-weight: 600; margin: 0; position: relative; z-index: 1; }
#chatbot-header p  { font-size: 12px; opacity: 0.9; margin: 5px 0 0; position: relative; z-index: 1; }

/* Khu vực tin nhắn */
#chatbot-messages {
    flex: 1; overflow-y: auto; padding: 20px; background: #f8fafc;
    scrollbar-width: thin; scrollbar-color: #cbd5e0 transparent;
}
#chatbot-messages::-webkit-scrollbar { width: 4px; }
#chatbot-messages::-webkit-scrollbar-thumb { background: #cbd5e0; border-radius: 2px; }

.message {
    margin: 15px 0; max-width: 85%; word-wrap: break-word;
    font-size: 14px; line-height: 1.5;
    animation: messageSlide 0.3s ease-out;
}
@keyframes messageSlide { from { opacity:0; transform:translateY(10px); } to { opacity:1; transform:translateY(0); } }

.message.user {
    background: linear-gradient(135deg, #E3ECFE, #C7D6FD);
    color: #2d3748; margin-left: auto; text-align: right;
    padding: 12px 16px; border-radius: 18px 18px 6px 18px;
}
.message.bot {
    background: white; color: #2d3748; margin-right: auto;
    padding: 12px 16px 12px 14px;
    border-radius: 18px 18px 18px 6px;
    border: 1px solid #e2e8f0; border-left: 3px solid #E3ECFE;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
}
.timestamp { font-size: 10px; opacity: 0.7; margin-top: 5px; }

/* Markdown trong bot */
.message.bot p { margin: 0 0 8px; line-height: 1.6; }
.message.bot p:last-child { margin-bottom: 0; }
.message.bot h1,.message.bot h2,.message.bot h3 { font-weight:700; margin:12px 0 6px; color:#1a202c; }
.message.bot h1 { font-size:16px; } .message.bot h2 { font-size:15px; } .message.bot h3 { font-size:14px; }
.message.bot ul,.message.bot ol { margin:6px 0 8px; padding-left:20px; }
.message.bot ul { list-style-type:disc; } .message.bot ol { list-style-type:decimal; }
.message.bot li { margin-bottom:4px; line-height:1.6; display:list-item; }
.message.bot strong,.message.bot b { font-weight:700; color:#1a202c; }
.message.bot code { background:#f1f5f9; color:#c53030; padding:1px 5px; border-radius:4px; font-size:12px; }
.message.bot pre { background:#1e293b; color:#e2e8f0; padding:12px; border-radius:8px; overflow-x:auto; margin:8px 0; font-size:12px; }
.message.bot table { border-collapse:collapse; width:100%; margin:8px 0; font-size:13px; }
.message.bot th,.message.bot td { border:1px solid #e2e8f0; padding:6px 10px; text-align:left; }
.message.bot th { background:#f1f5f9; font-weight:600; }

/* Typing indicator */
.typing-indicator {
    display:flex; align-items:center; padding:12px 16px; background:white;
    border-radius:18px 18px 18px 6px; margin:15px 0; max-width:85%;
    box-shadow:0 2px 8px rgba(0,0,0,0.05); border:1px solid #e2e8f0;
}
.typing-dots { display:flex; gap:3px; }
.typing-dots span {
    width:6px; height:6px; background:#94a3b8; border-radius:50%;
    animation: typing 1.4s infinite ease-in-out;
}
.typing-dots span:nth-child(1) { animation-delay:-0.32s; }
.typing-dots span:nth-child(2) { animation-delay:-0.16s; }
@keyframes typing {
    0%,80%,100% { transform:scale(0.8); opacity:0.5; }
    40%          { transform:scale(1);   opacity:1; }
}

/* Feedback Actions */
.feedback-actions { display: flex; gap: 8px; margin-top: 8px; justify-content: flex-end; }
.feedback-btn { background: transparent; border: 1px solid #e2e8f0; color: #64748b; border-radius: 6px; padding: 4px 8px; cursor: pointer; font-size: 12px; display: flex; align-items: center; gap: 4px; transition: all 0.2s; }
.feedback-btn:hover { background: #f8fafc; color: #334155; border-color: #cbd5e0; }
.feedback-btn.active-like { background: #dcfce7; color: #166534; border-color: #bbf7d0; }
.feedback-btn.active-dislike { background: #fee2e2; color: #991b1b; border-color: #fecaca; }

/* Input */
#chatbot-input { padding: 20px; background: white; border-top: 1px solid #e2e8f0; flex-shrink: 0; }
.input-group { display:flex; gap:10px; align-items:flex-end; }
#user-input {
    flex:1; padding:12px 16px; border:2px solid #e2e8f0;
    border-radius:20px; font-size:14px; outline:none;
    background:#f8fafc; transition:all 0.2s ease;
}
#user-input:focus { border-color:#E3ECFE; background:white; box-shadow:0 0 0 3px rgba(227,236,254,0.3); }
.send-btn {
    background: linear-gradient(135deg, #667eea, #764ba2);
    color:white; border:none; border-radius:12px; padding:8px;
    cursor:pointer; width:40px; height:40px;
    display:flex; align-items:center; justify-content:center;
    box-shadow:0 2px 8px rgba(102, 126, 234, 0.3); transition:all 0.2s ease;
}
.send-btn:hover { transform:translateY(-1px); }
.send-btn:active { transform:translateY(0); }`;

const htmlCode = `<!-- Dán vào cuối <body>, trước thẻ đóng </body> -->

<!-- 1. Thư viện render Markdown (dán vào <head>) -->
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<script>marked.setOptions({ breaks: true, gfm: true });</script>

<!-- 2. Chatbot HTML -->
<div id="chatbot-icon">
    <img src="https://storage-ic.icenter.ai/smartbot-v2/chatbot_images/12282023/dc64a85b-9c28-4f73-ad3f-81025ab81833.png" alt="Chatbot">
</div>
<div id="chatbot-box">
    <div id="chatbot-header">
        <button type="button" id="chatbot-reset" onclick="resetChat()" title="Cuộc hội thoại mới">
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24"
                 fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="1 4 1 10 7 10"></polyline>
                <path d="M3.51 15a9 9 0 1 0 .49-3.51"></path>
            </svg>
        </button>
        <button type="button" id="chatbot-close" onclick="closeChatbox()" title="Đóng">×</button>
        <h3>🤖 Trợ Lý AI</h3>
        <p>Hỏi bất cứ điều gì về nghiệp vụ</p>
    </div>
    <div id="chatbot-messages">
        <div class="message bot">
            Xin chào! Bạn cần hỏi gì?
            <div class="timestamp"></div>
        </div>
    </div>
    <div id="chatbot-input">
        <div class="input-group">
            <input type="text" id="user-input" placeholder="Nhập câu hỏi..."
                   onkeypress="if(event.key==='Enter') sendMessage()">
            <button type="button" class="send-btn" onclick="sendMessage()" title="Gửi">
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24"
                     fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <line x1="22" y1="2" x2="11" y2="13"></line>
                    <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
                </svg>
            </button>
        </div>
    </div>
</div>`;

const jsVbnet = `<script>
    // === CẤU HÌNH API GỌI TRỰC TIẾP ===
    // API_KEY và LLM_API_URL được ASP.NET tự động đọc từ Web.config khi render trang (.master/.aspx)
    const LLM_API_URL = '<%= ConfigurationManager.AppSettings("Chatbot_ApiUrl") %>';
    const API_KEY     = '<%= ConfigurationManager.AppSettings("Chatbot_ApiKey") %>';

    let chatContext = { isTyping: false, history: [] };
    const MAX_CONTEXT = 6;

    // Mở / đóng chatbox với animation
    function openChatbox() {
        const box = document.getElementById('chatbot-box');
        box.classList.remove('is-closing');
        box.classList.add('is-open');
        setTimeout(() => document.getElementById('user-input').focus(), 350);
    }
    function closeChatbox() {
        const box = document.getElementById('chatbot-box');
        box.classList.remove('is-open');
        box.classList.add('is-closing');
        box.addEventListener('animationend', () => box.classList.remove('is-closing'), { once: true });
    }

    document.getElementById('chatbot-icon').addEventListener('click', () => {
        const box = document.getElementById('chatbot-box');
        box.classList.contains('is-open') ? closeChatbox() : openChatbox();
    });

    // Click bên ngoài để đóng (giống modal)
    document.addEventListener('click', function(e) {
        const box  = document.getElementById('chatbot-box');
        const icon = document.getElementById('chatbot-icon');
        if (box.classList.contains('is-open') && !box.contains(e.target) && !icon.contains(e.target))
            closeChatbox();
    });

    // Reset toàn bộ lịch sử
    function resetChat() {
        chatContext.history = [];
        const chatBox = document.getElementById('chatbot-messages');
        chatBox.innerHTML = '';
        const msg = document.createElement('div');
        msg.className = 'message bot';
        msg.textContent = 'Cuộc hội thoại mới đã bắt đầu!';
        chatBox.appendChild(msg);
        document.getElementById('user-input').focus();
    }

    // Typing indicator (3 chấm nảy)
    function showTypingIndicator() {
        const chatBox = document.getElementById('chatbot-messages');
        const div = document.createElement('div');
        div.className = 'typing-indicator'; div.id = 'typing-indicator';
        div.innerHTML = '<div class="typing-dots"><span></span><span></span><span></span></div>';
        chatBox.appendChild(div);
        chatBox.scrollTop = chatBox.scrollHeight;
    }
    function removeTypingIndicator() {
        const el = document.getElementById('typing-indicator');
        if (el) el.remove();
    }

    async function sendMessage() {
        if (chatContext.isTyping) return;
        const input   = document.getElementById('user-input');
        const sendBtn = document.querySelector('.send-btn');
        const question = input.value.trim();
        if (!question) return;

        chatContext.isTyping = true;
        sendBtn.disabled = true; input.disabled = true; input.value = '';

        // Hiển thị tin nhắn user
        const chatBox = document.getElementById('chatbot-messages');
        const userMsg = document.createElement('div');
        userMsg.className = 'message user';
        userMsg.innerHTML = question
            + '<div class="timestamp">' + new Date().toLocaleTimeString('vi-VN', {hour:'2-digit', minute:'2-digit'}) + '</div>';
        chatBox.appendChild(userMsg);
        chatBox.scrollTop = chatBox.scrollHeight;

        showTypingIndicator();

        chatContext.history.push({ role: 'user', content: question });
        const contextMessages = chatContext.history.slice(-MAX_CONTEXT);

        let answer = '';
        try {
            const llmRes = await fetch(LLM_API_URL, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + API_KEY },
                body: JSON.stringify({
                    model: 'chatbot-rag',
                    messages: contextMessages,
                    stream: true
                })
            });

            if (!llmRes.ok) throw new Error('Lỗi API: ' + llmRes.status);

            removeTypingIndicator();

            const botMsg = document.createElement('div');
            botMsg.className = 'message bot';
            const botContent = document.createElement('div');
            botMsg.appendChild(botContent);
            const ts = document.createElement('div');
            ts.className = 'timestamp';
            ts.textContent = new Date().toLocaleTimeString('vi-VN', {hour:'2-digit', minute:'2-digit'});
            botMsg.appendChild(ts);
            chatBox.appendChild(botMsg);

            // Đọc stream theo từng chunk (chuẩn OpenAI SSE)
            const reader  = llmRes.body.getReader();
            const decoder = new TextDecoder('utf-8');
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                buffer += decoder.decode(value, { stream: true });

                let newlineIndex;
                while ((newlineIndex = buffer.indexOf('\\n')) >= 0) {
                    const line = buffer.slice(0, newlineIndex).trim();
                    buffer = buffer.slice(newlineIndex + 1);
                    if (!line.startsWith('data: ')) continue;
                    const payload = line.slice(6).trim();
                    if (payload === '[DONE]') continue;
                    try {
                        const chunk = JSON.parse(payload)?.choices?.[0]?.delta?.content;
                        if (chunk) {
                            answer += chunk;
                            botContent.innerHTML = marked.parse(answer);
                            chatBox.scrollTop = chatBox.scrollHeight;
                        }
                    } catch (e) { /* bỏ qua JSON lỗi */ }
                }
            }

            chatContext.history.push({ role: 'assistant', content: answer });

            // Thêm nút Like / Dislike
            const feedbackActions = document.createElement('div');
            feedbackActions.className = 'feedback-actions';
            
            const likeBtn = document.createElement('button');
            likeBtn.className = 'feedback-btn';
            likeBtn.innerHTML = '👍';
            
            const dislikeBtn = document.createElement('button');
            dislikeBtn.className = 'feedback-btn';
            dislikeBtn.innerHTML = '👎';

            const currentQuestion = question;
            const currentAnswer = answer;

            likeBtn.onclick = (e) => {
                e.stopPropagation();
                sendFeedback(currentQuestion, currentAnswer, 'like');
                feedbackActions.innerHTML = '<span style="font-size: 11px; color: #10b981; font-style: italic;">✓ Đã gửi đánh giá</span>';
            };

            dislikeBtn.onclick = (e) => {
                e.stopPropagation();
                sendFeedback(currentQuestion, currentAnswer, 'dislike');
                feedbackActions.innerHTML = '<span style="font-size: 11px; color: #10b981; font-style: italic;">✓ Đã gửi đánh giá</span>';
            };

            feedbackActions.appendChild(likeBtn);
            feedbackActions.appendChild(dislikeBtn);
            botMsg.appendChild(feedbackActions);
            chatBox.scrollTop = chatBox.scrollHeight;

        } catch (err) {
            removeTypingIndicator();
            chatContext.history.pop();
            const errMsg = document.createElement('div');
            errMsg.className = 'message bot';
            errMsg.innerHTML = marked.parse('⚠️ Lỗi kết nối: ' + err.message);
            chatBox.appendChild(errMsg);
        } finally {
            chatContext.isTyping = false;
            sendBtn.disabled = false; input.disabled = false; input.focus();
        }
    }

    function sendFeedback(queryText, answerText, feedbackType) {
        const feedbackUrl = LLM_API_URL.replace('/chat/completions', '/chat/feedback');
        fetch(feedbackUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + API_KEY
            },
            body: JSON.stringify({
                feedback_type: feedbackType,
                query_text: queryText,
                assistant_answer: answerText
            })
        }).catch(err => console.error("Feedback error:", err));
    }
<\/script>`;

const reactPlaygroundCode = `// React Playground Component Example
import { useState, useRef } from "react";
import ReactMarkdown from "react-markdown";

export function LiveChatPlayground() {
  const [apiKey, setApiKey] = useState("");
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  const sendMessage = async () => {
    if (!input.trim() || !apiKey.trim() || loading) return;
    
    setLoading(true);
    const userMsg = { role: "user", content: input };
    const updatedMessages = [...messages, userMsg];
    setMessages(updatedMessages);
    setInput("");

    // Khởi tạo tin nhắn trống cho bot
    const botMsgIndex = updatedMessages.length;
    const nextMessages = [...updatedMessages, { role: "assistant", content: "" }];
    setMessages(nextMessages);

    try {
      const response = await fetch("https://api.qtuanph.dev/v1/chat/completions", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": \`Bearer \${apiKey}\`
        },
        body: JSON.stringify({
          model: "chatbot-rag",
          messages: updatedMessages.slice(-6),
          stream: true
        })
      });

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let streamText = "";
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        let lineEnd;
        while ((lineEnd = buffer.indexOf("\\n")) >= 0) {
          const line = buffer.slice(0, lineEnd).trim();
          buffer = buffer.slice(lineEnd + 1);

          if (!line.startsWith("data: ")) continue;
          const payload = line.slice(6).trim();
          if (payload === "[DONE]") continue;

          try {
            const data = JSON.parse(payload);
            const chunk = data.choices[0]?.delta?.content || "";
            streamText += chunk;

            // Cập nhật câu trả lời bot real-time
            setMessages(prev => {
              const copy = [...prev];
              copy[botMsgIndex] = { role: "assistant", content: streamText };
              return copy;
            });
          } catch {}
        }
      }
    } catch {
      setMessages(prev => {
        const copy = [...prev];
        copy[botMsgIndex] = { role: "assistant", content: "Lỗi kết nối API." };
        return copy;
      });
    } finally {
      setLoading(false);
    }
  };

  return ( ... );
}`;

/* ─── Interactive Playground Component ────────────────────────── */
interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
  feedback?: "like" | "dislike";
}

function LivePlayground() {
  const [apiKey, setApiKey] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputMessage, setInputMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  
  const chatEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleFeedback = async (index: number, feedbackType: "like" | "dislike") => {
    if (!apiKey.trim()) return;
    const assistantMsg = messages[index];
    // Find the user message right before it
    const userMsg = messages[index - 1];
    if (!assistantMsg || !userMsg || userMsg.role !== "user") return;

    setMessages(prev => {
      const copy = [...prev];
      copy[index] = { ...copy[index], feedback: feedbackType };
      return copy;
    });

    try {
      await fetch(API_URL.replace("/chat/completions", "/chat/feedback"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${apiKey.trim()}`,
        },
        body: JSON.stringify({
          feedback_type: feedbackType,
          query_text: userMsg.content,
          assistant_answer: assistantMsg.content
        })
      });
    } catch (e) {
      console.error("Feedback error", e);
    }
  };

  const handleSend = async () => {
    if (!inputMessage.trim() || isLoading) return;
    if (!apiKey.trim()) {
      alert("Vui lòng nhập API Key để tiến hành thử nghiệm chat!");
      return;
    }

    const currentInput = inputMessage;
    setInputMessage("");
    setIsLoading(true);

    const userMsg: ChatMessage = { role: "user", content: currentInput };
    const updatedMessages = [...messages, userMsg];
    setMessages(updatedMessages);

    // Prepare placeholder assistant message
    const assistantIndex = updatedMessages.length;
    setMessages([...updatedMessages, { role: "assistant", content: "" }]);

    try {
      const response = await fetch(API_URL, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${apiKey.trim()}`,
        },
        body: JSON.stringify({
          model: "chatbot-rag",
          messages: updatedMessages.slice(-6),
          stream: true,
        }),
      });

      if (!response.ok) {
        throw new Error(`Mã lỗi HTTP: ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error("Không thể khởi tạo reader stream.");

      const decoder = new TextDecoder("utf-8");
      let buffer = "";
      let fullText = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        
        let newlineIndex;
        while ((newlineIndex = buffer.indexOf("\n")) >= 0) {
          const line = buffer.slice(0, newlineIndex).trim();
          buffer = buffer.slice(newlineIndex + 1);

          if (!line.startsWith("data: ")) continue;
          const dataPayload = line.slice(6).trim();
          if (dataPayload === "[DONE]") continue;

          try {
            const parsed = JSON.parse(dataPayload);
            const chunk = parsed?.choices?.[0]?.delta?.content || "";
            if (chunk) {
              fullText += chunk;
              setMessages((prev) => {
                const list = [...prev];
                list[assistantIndex] = { role: "assistant", content: fullText };
                return list;
              });
            }
          } catch (e) {
            // ignore bad chunks
          }
        }
      }
    } catch (error: any) {
      setMessages((prev) => {
        const list = [...prev];
        list[assistantIndex] = { role: "assistant", content: `❌ Lỗi: ${error?.message || "Không thể kết nối đến API RAG."}` };
        return list;
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="border border-border rounded-xl overflow-hidden bg-card text-foreground">
      {/* Settings Header */}
      <div className="p-4 bg-muted/30 border-b border-border space-y-3">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
          <div className="space-y-1">
            <span className="font-semibold block">RAG Target Endpoint URL:</span>
            <Input type="text" readOnly value={API_URL} className="font-mono text-[10px] h-8 bg-muted cursor-default" />
          </div>
          <div className="space-y-1">
            <span className="font-semibold block text-primary">Nhập API Key (trg_...) để test:</span>
            <div className="relative">
              <Input
                type={showKey ? "text" : "password"}
                placeholder="Dán API Key của Tenant của bạn vào đây..."
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                className="font-mono text-[10px] h-8 pr-8"
              />
              <button
                type="button"
                onClick={() => setShowKey(!showKey)}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              >
                {showKey ? <EyeOffIcon className="w-3.5 h-3.5" /> : <EyeIcon className="w-3.5 h-3.5" />}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Chat Display Box */}
      <div className="h-64 overflow-y-auto p-4 bg-muted/10 flex flex-col gap-3">
        {messages.length === 0 ? (
          <div className="text-center text-xs text-muted-foreground my-auto space-y-2">
            <InfoIcon className="w-8 h-8 mx-auto opacity-40 text-primary" />
            <p>Điền API Key của Tenant phía trên rồi nhập câu hỏi để thử nghiệm chat stream trực tiếp.</p>
          </div>
        ) : (
          messages.map((m, idx) => (
            <div
              key={idx}
              className={`max-w-[85%] rounded-lg p-2.5 text-xs ${
                m.role === "user"
                  ? "bg-primary text-primary-foreground ml-auto"
                  : "bg-card border border-border text-foreground mr-auto leading-relaxed"
              }`}
            >
              {m.role === "user" ? (
                <div className="whitespace-pre-wrap">{m.content}</div>
              ) : (
                <div className="flex flex-col gap-2">
                  <div className="prose prose-sm dark:prose-invert break-words max-w-none text-xs">
                    {m.content === "" ? (
                      <span className="inline-flex gap-1 items-center italic text-muted-foreground">
                        <RefreshCwIcon className="w-3 h-3 animate-spin" /> Đang nhận phản hồi...
                      </span>
                    ) : (
                      <ReactMarkdown>{m.content}</ReactMarkdown>
                    )}
                  </div>
                  {(!isLoading || idx !== messages.length - 1) && m.content !== "" && !m.feedback && (
                    <div className="flex items-center gap-1.5 mt-1 border-t border-border/50 pt-2">
                      <button
                        onClick={() => handleFeedback(idx, "like")}
                        className="p-1 rounded transition-colors hover:bg-muted text-muted-foreground"
                        title="Thích câu trả lời này"
                      >
                        <ThumbsUpIcon className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={() => handleFeedback(idx, "dislike")}
                        className="p-1 rounded transition-colors hover:bg-muted text-muted-foreground"
                        title="Không thích câu trả lời này"
                      >
                        <ThumbsDownIcon className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  )}
                  {m.feedback && (
                    <div className="flex items-center gap-1.5 mt-1 border-t border-border/50 pt-2 text-muted-foreground text-[10px] italic">
                      <CheckCircle2Icon className="w-3 h-3 text-green-500" /> Đã gửi đánh giá
                    </div>
                  )}
                </div>
              )}
            </div>
          ))
        )}
        <div ref={chatEndRef} />
      </div>

      {/* Chat Control Input */}
      <div className="p-3 border-t border-border bg-card flex gap-2">
        <Input
          type="text"
          placeholder={apiKey.trim() ? "Nhập câu hỏi test nghiệp vụ (ví dụ: Quy trình tạo đơn hàng)..." : "Nhập API Key ở phần trên trước..."}
          disabled={!apiKey.trim() || isLoading}
          value={inputMessage}
          onChange={(e) => setInputMessage(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleSend();
          }}
          className="text-xs h-9 flex-1"
        />
        <Button
          size="sm"
          disabled={!apiKey.trim() || !inputMessage.trim() || isLoading}
          onClick={handleSend}
          className="h-9 flex gap-1.5 items-center text-xs"
        >
          {isLoading ? <RefreshCwIcon className="w-3.5 h-3.5 animate-spin" /> : <SendIcon className="w-3.5 h-3.5" />}
          Gửi
        </Button>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════ */

export default function IntegrationGuidePage() {
  return (
    <div className="space-y-6 pb-16 max-w-4xl">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-foreground">Hướng Dẫn Tích Hợp</h1>
        <p className="text-sm text-muted-foreground mt-1.5 leading-relaxed">
          Tài liệu tích hợp nhúng AI Chatbot trực tiếp vào phần mềm doanh nghiệp của bạn thông qua Direct API Connection.
        </p>
      </div>

      {/* API Info card */}
      <Card className="border border-border bg-card">
        <CardContent className="pt-4 pb-4">
          <div className="flex items-center gap-2 mb-3">
            <InfoIcon className="w-4 h-4 text-primary" />
            <span className="text-sm font-semibold text-foreground">Thông tin kết nối API</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-1.5 text-xs font-mono text-muted-foreground">
            <div><span className="text-foreground font-sans font-semibold">Base URL: </span>{API_BASE}</div>
            <div><span className="text-foreground font-sans font-semibold">Endpoint: </span>POST /chat/completions</div>
            <div><span className="text-foreground font-sans font-semibold">Auth: </span>Bearer trg_...</div>
            <div><span className="text-foreground font-sans font-semibold">Model: </span>chatbot-rag</div>
          </div>
        </CardContent>
      </Card>

      {/* Guide Steps - Flat separate Accordion components */}
      <div className="space-y-3">

        {/* ── BƯỚC 1 ── */}
        <Accordion multiple className="border border-border rounded-xl shadow-sm bg-card">
          <AccordionItem value="step-1">
            <AccordionTrigger className="px-5 hover:no-underline font-semibold text-foreground text-sm">
              <div className="flex items-center gap-3">
                <span className="w-6 h-6 rounded-full bg-primary text-primary-foreground text-xs font-bold flex items-center justify-center shrink-0">1</span>
                <DatabaseIcon className="w-4 h-4 text-primary shrink-0" />
                Chuẩn bị trên Admin Panel
              </div>
            </AccordionTrigger>
            <AccordionContent className="px-5 pb-5 text-muted-foreground text-xs leading-relaxed space-y-2">
              <ol className="space-y-3 list-decimal pl-5">
                <li>
                  <strong className="text-foreground">Tạo Tenant:</strong>{" "}
                  Vào <code className="bg-muted px-1.5 py-0.5 rounded text-xs">Quản lý Tenant → Tạo mới</code>.
                  Mỗi phần mềm/công ty là một Tenant riêng với dữ liệu độc lập.
                </li>
                <li>
                  <strong className="text-foreground">Upload tài liệu (Train AI):</strong>{" "}
                  Vào <code className="bg-muted px-1.5 py-0.5 rounded text-xs">Quản lý Tài liệu</code>.
                  Upload PDF, Word, Excel chứa quy trình nghiệp vụ, FAQ, hướng dẫn sử dụng...
                  Hệ thống tự động vector hóa và index để AI tìm kiếm ngữ nghĩa.
                </li>
                <li>
                  <strong className="text-foreground">Lấy API Key:</strong>{" "}
                  Vào <code className="bg-muted px-1.5 py-0.5 rounded text-xs">Cấu hình Tenant → API Keys → Tạo mới</code>.
                  Sao chép chuỗi bắt đầu bằng <code className="bg-muted px-1 rounded text-xs">trg_...</code>.{" "}
                  <strong className="text-destructive font-semibold">Chỉ hiển thị 1 lần, không thể xem lại!</strong>
                </li>
              </ol>
            </AccordionContent>
          </AccordionItem>
        </Accordion>

        {/* ── BƯỚC 2 ── */}
        <Accordion multiple className="border border-border rounded-xl shadow-sm bg-card">
          <AccordionItem value="step-2">
            <AccordionTrigger className="px-5 hover:no-underline font-semibold text-foreground text-sm">
              <div className="flex items-center gap-3">
                <span className="w-6 h-6 rounded-full bg-primary text-primary-foreground text-xs font-bold flex items-center justify-center shrink-0">2</span>
                <KeyIcon className="w-4 h-4 text-primary shrink-0" />
                Lưu API Key an toàn trong Web.config
              </div>
            </AccordionTrigger>
            <AccordionContent className="px-5 pb-5 space-y-3 text-muted-foreground text-xs">
              <Alert variant="destructive" className="bg-destructive/10 border-destructive/25 text-destructive">
                <ShieldAlertIcon className="h-4 w-4" />
                <AlertTitle className="text-sm font-bold text-destructive">KHÔNG hardcode API Key vào JavaScript static</AlertTitle>
                <AlertDescription className="text-xs mt-1 text-destructive/90">
                  Hãy giữ key phía Backend. Đối với ASP.NET WebForms, cách tốt nhất là đặt cấu hình URL và API Key bên trong file <code>Web.config</code> của ứng dụng:
                </AlertDescription>
              </Alert>
              <CodeBlock code={webConfigCode} lang="xml" />
            </AccordionContent>
          </AccordionItem>
        </Accordion>

        {/* ── BƯỚC 3 ── */}
        <Accordion multiple className="border border-border rounded-xl shadow-sm bg-card">
          <AccordionItem value="step-3">
            <AccordionTrigger className="px-5 hover:no-underline font-semibold text-foreground text-sm">
              <div className="flex items-center gap-3">
                <span className="w-6 h-6 rounded-full bg-primary text-primary-foreground text-xs font-bold flex items-center justify-center shrink-0">3</span>
                <CodeIcon className="w-4 h-4 text-primary shrink-0" />
                Demo gọi API phía Backend (Python/Node.js/cURL)
              </div>
            </AccordionTrigger>
            <AccordionContent className="px-5 pb-5 space-y-4 text-muted-foreground text-xs">
              <p>
                Để test nhanh kết nối từ các tool backend hoặc terminal:
              </p>
              <Tabs defaultValue="python">
                <TabsList>
                  <TabsTrigger value="python">Python</TabsTrigger>
                  <TabsTrigger value="nodejs">Node.js</TabsTrigger>
                  <TabsTrigger value="curl">cURL</TabsTrigger>
                </TabsList>
                <TabsContent value="python" className="mt-2"><CodeBlock code={pythonCode} lang="python" /></TabsContent>
                <TabsContent value="nodejs" className="mt-2"><CodeBlock code={nodejsCode} lang="js" /></TabsContent>
                <TabsContent value="curl" className="mt-2"><CodeBlock code={curlCode} lang="shell" /></TabsContent>
              </Tabs>
            </AccordionContent>
          </AccordionItem>
        </Accordion>

        {/* ── BƯỚC 4 ── */}
        <Accordion multiple className="border border-border rounded-xl shadow-sm bg-card">
          <AccordionItem value="step-4">
            <AccordionTrigger className="px-5 hover:no-underline font-semibold text-foreground text-sm">
              <div className="flex items-center gap-3">
                <span className="w-6 h-6 rounded-full bg-primary text-primary-foreground text-xs font-bold flex items-center justify-center shrink-0">4</span>
                <ZapIcon className="w-4 h-4 text-primary shrink-0" />
                Nhúng Chatbot Widget vào file giao diện (Main.master)
              </div>
            </AccordionTrigger>
            <AccordionContent className="px-5 pb-5 space-y-4 text-muted-foreground text-xs">
              <Alert className="bg-primary/5 border-primary/20 text-foreground">
                <InfoIcon className="h-4 w-4 text-primary" />
                <AlertTitle className="text-sm font-semibold">Cơ chế inject API Key trực tiếp từ Server</AlertTitle>
                <AlertDescription className="text-xs mt-1 text-muted-foreground">
                  Vì file <code>Main.master</code> chạy trên server ASP.NET, bạn có thể gọi mã biểu thức 
                  <code>{"<%= ConfigurationManager.AppSettings(\"Chatbot_ApiKey\") %>"}</code> để render động key vào trong script trước khi trả về browser.
                  Điều này giúp client kết nối trực tiếp đến API Server của RAG, đồng thời không bao giờ lộ API Key tĩnh trong source code git.
                </AlertDescription>
              </Alert>

              <div className="flex items-center gap-3 p-4 bg-muted/30 border border-border rounded-lg">
                <div className="flex-1">
                  <h4 className="text-sm font-semibold text-foreground">File Mẫu Tích Hợp (Main.master)</h4>
                  <p className="text-xs text-muted-foreground mt-1">Tải xuống file Main.master đã được nhúng sẵn Chatbot UI và logic gọi API. Lập trình viên có thể dùng file này để đối chiếu hoặc thay thế trực tiếp vào dự án ERP cũ.</p>
                </div>
                <Button size="sm" className="shrink-0 gap-2" onClick={() => window.open("/downloads/Main.master", "_blank")}>
                  <DownloadIcon className="w-4 h-4" />
                  Tải xuống file mẫu
                </Button>
              </div>

              <Tabs defaultValue="css">
                <TabsList>
                  <TabsTrigger value="css">CSS Giao diện</TabsTrigger>
                  <TabsTrigger value="html">HTML Khung</TabsTrigger>
                  <TabsTrigger value="js">JavaScript Logic (Direct Call)</TabsTrigger>
                </TabsList>
                <TabsContent value="css" className="mt-2">
                  <CodeBlock code={cssCode} lang="css" />
                </TabsContent>
                <TabsContent value="html" className="mt-2">
                  <CodeBlock code={htmlCode} lang="xml" />
                </TabsContent>
                <TabsContent value="js" className="mt-2">
                  <CodeBlock code={jsVbnet} lang="js" />
                </TabsContent>
              </Tabs>
            </AccordionContent>
          </AccordionItem>
        </Accordion>

        {/* ── BƯỚC 5: HỘP THỬ NGHIỆM TRỰC TIẾP (API PLAYGROUND) ── */}
        <Accordion multiple className="border border-border rounded-xl shadow-sm bg-card">
          <AccordionItem value="step-5">
            <AccordionTrigger className="px-5 hover:no-underline font-semibold text-foreground text-sm">
              <div className="flex items-center gap-3">
                <span className="w-6 h-6 rounded-full bg-primary text-primary-foreground text-xs font-bold flex items-center justify-center shrink-0">5</span>
                <TerminalIcon className="w-4 h-4 text-primary shrink-0" />
                Thử nghiệm API trực tuyến (Interactive Playground)
              </div>
            </AccordionTrigger>
            <AccordionContent className="px-5 pb-5 space-y-4 text-muted-foreground text-xs">
              <p>
                Dưới đây là một giao diện Chat Sandbox kết nối trực tiếp đến RAG API. Hãy nhập API Key của Tenant bạn và bắt đầu trò chuyện để kiểm chứng khả năng stream thực tế:
              </p>
              
              <LivePlayground />

              <Accordion multiple className="border border-border rounded-xl mt-4 bg-muted/10">
                <AccordionItem value="playground-source">
                  <AccordionTrigger className="px-4 hover:no-underline font-semibold text-foreground text-xs">
                    📁 Xem mã nguồn React/TypeScript của Sandbox này
                  </AccordionTrigger>
                  <AccordionContent className="px-4 pb-4">
                    <p className="mb-2 text-[11px]">Dành cho dự án frontend phát triển bằng React/Next.js có hỗ trợ stream: </p>
                    <CodeBlock code={reactPlaygroundCode} lang="js" />
                  </AccordionContent>
                </AccordionItem>
              </Accordion>
            </AccordionContent>
          </AccordionItem>
        </Accordion>

        {/* ── BƯỚC 6 ── */}
        <Accordion multiple className="border border-border rounded-xl shadow-sm bg-card">
          <AccordionItem value="step-6">
            <AccordionTrigger className="px-5 hover:no-underline font-semibold text-foreground text-sm">
              <div className="flex items-center gap-3">
                <span className="w-6 h-6 rounded-full bg-primary text-primary-foreground text-xs font-bold flex items-center justify-center shrink-0">6</span>
                <RocketIcon className="w-4 h-4 text-primary shrink-0" />
                Checklist Go-Live
              </div>
            </AccordionTrigger>
            <AccordionContent className="px-5 pb-5">
              <ul className="space-y-2 text-xs text-muted-foreground">
                {[
                  "Cấu hình Chatbot_ApiUrl và Chatbot_ApiKey đã được định nghĩa trong file Web.config của ứng dụng",
                  "Các thẻ button trong widget HTML đã có thuộc tính type=\"button\" để tránh xung đột submit form WebForms",
                  "Đã upload và vector hóa đầy đủ các tài liệu quy trình nghiệp vụ trên Admin Panel",
                  "F12 → Network kiểm tra request /chat/completions gọi trực tiếp đến API RAG thành công và stream mượt mà",
                  "Nút Đóng (✕) và Xoay reset (🔄) trên widget hoạt động trơn tru không lỗi",
                ].map((item, i) => (
                  <li key={i} className="flex items-start gap-2">
                    <CheckCircle2Icon className="w-4 h-4 text-emerald-500 mt-0.5 shrink-0" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </AccordionContent>
          </AccordionItem>
        </Accordion>

      </div>
    </div>
  );
}
