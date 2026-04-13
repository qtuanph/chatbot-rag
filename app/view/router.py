from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
import html
import json

from app.api.routes.health import _build_snapshot
from app.db.session import SessionLocal
from app.models.core import Document
from app.core.config import settings

router = APIRouter(tags=["view"])

def get_stats() -> dict:
    snapshot = _build_snapshot()
    with SessionLocal() as session:
        docs = session.query(Document).order_by(Document.created_at.desc()).limit(50).all()
        
    documents_list = []
    ready_count = 0
    processing_count = 0
    failed_count = 0
    
    for doc in docs:
        if doc.status == "ready": ready_count += 1
        elif doc.status == "failed": failed_count += 1
        else: processing_count += 1
        
        documents_list.append({
            "id": str(doc.id),
            "file_name": doc.file_name,
            "status": doc.status,
            "progress_percent": doc.progress_percent,
            "file_size": doc.file_size
        })

    return {
        "status": snapshot.get("status", "unknown"),
        "total": len(docs),
        "ready": ready_count,
        "processing": processing_count,
        "failed": failed_count,
        "services": snapshot.get("checks", {}),
        "documents": documents_list
    }

@router.get("/view/stats")
async def api_stats():
    return get_stats()

@router.get("/")
async def admin_ui(request: Request):
    prefix = settings.api_v1_prefix.rstrip("/")
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>RAG System Demo</title>
        <style>
            :root {{
                --bg-color: #f8fafc;
                --text-color: #334155;
                --card-bg: #ffffff;
                --border-color: #e2e8f0;
                --primary: #3b82f6;
                --success: #22c55e;
                --warning: #f59e0b;
                --danger: #ef4444;
            }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                background-color: var(--bg-color);
                color: var(--text-color);
                margin: 0;
                padding: 0;
                line-height: 1.5;
            }}
            .container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}
            .card {{ background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 8px; padding: 20px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
            h1, h2, h3 {{ margin-top: 0; color: #0f172a; }}
            input[type="text"], input[type="password"] {{ padding: 10px; border: 1px solid var(--border-color); border-radius: 4px; width: 100%; box-sizing: border-box; margin-bottom: 10px; }}
            button {{ background: var(--primary); color: white; border: none; padding: 10px 16px; border-radius: 4px; cursor: pointer; font-weight: bold; }}
            button:hover {{ opacity: 0.9; }}
            button.danger-btn {{ background: var(--danger); }}
            button.outline-btn {{ background: transparent; color: var(--primary); border: 1px solid var(--primary); }}
            
            /* Navbar */
            .navbar {{ display: flex; justify-content: space-between; align-items: center; background: white; padding: 15px 20px; border-bottom: 1px solid var(--border-color); }}
            
            /* Login View */
            #login-view {{ max-width: 400px; margin: 100px auto; }}
            
            /* Admin Tabs */
            .tabs {{ display: flex; border-bottom: 1px solid var(--border-color); margin-bottom: 20px; }}
            .tab-btn {{ padding: 10px 20px; cursor: pointer; border: none; background: none; font-size: 16px; color: var(--text-color); border-bottom: 2px solid transparent; }}
            .tab-btn.active {{ color: var(--primary); border-bottom-color: var(--primary); font-weight: bold; }}
            .tab-content {{ display: none; }}
            .tab-content.active {{ display: block; }}
            
            /* Tables & Grids */
            table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
            th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid var(--border-color); }}
            th {{ background-color: #f1f5f9; font-weight: 600; }}
            .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px; }}
            .stat-box {{ background: var(--card-bg); border: 1px solid var(--border-color); padding: 15px; border-radius: 8px; text-align: center; }}
            .stat-value {{ font-size: 24px; font-weight: bold; margin: 10px 0; }}
            .badge {{ padding: 4px 8px; border-radius: 12px; font-size: 12px; font-weight: bold; color: white; }}
            .badge.ready, .badge.ok, .badge.up {{ background: var(--success); }}
            .badge.processing {{ background: var(--warning); }}
            .badge.failed, .badge.down {{ background: var(--danger); }}
            
            /* Chat View */
            #chat-window {{ height: 500px; border: 1px solid var(--border-color); border-radius: 8px; padding: 20px; overflow-y: auto; background: white; margin-bottom: 10px; }}
            .chat-msg {{ margin-bottom: 15px; padding: 10px 15px; border-radius: 8px; max-width: 80%; line-height: 1.4; }}
            .chat-msg.user {{ background: var(--primary); color: white; margin-left: auto; }}
            .chat-msg.bot {{ background: #f1f5f9; color: var(--text-color); margin-right: auto; }}
            .citation-box {{ font-size: 12px; background: #e2e8f0; padding: 8px; margin-top: 8px; border-radius: 4px; color: #475569; }}
            
            /* Upload */
            .upload-area {{ border: 2px dashed var(--border-color); padding: 40px; text-align: center; border-radius: 8px; background: #f8fafc; cursor: pointer; }}
            .upload-area:hover {{ background: #f1f5f9; border-color: var(--primary); }}
        </style>
    </head>
    <body>
        <div class="navbar" id="navbar" style="display:none;">
            <h2>🤖 RAG Enterprise</h2>
            <div>
                <span id="user-role-badge" class="badge ready" style="margin-right: 15px;"></span>
                <button class="outline-btn" onclick="logout()">Đăng xuất</button>
            </div>
        </div>

        <!-- 1. LOGIN VIEW -->
        <div id="login-view" class="card">
            <h2 style="text-align:center; color: var(--primary);">Đăng nhập Hệ thống</h2>
            <div id="login-error" style="color: var(--danger); font-size: 14px; margin-bottom: 10px; text-align:center;"></div>
            <input type="text" id="login-username" placeholder="Email / Username">
            <input type="password" id="login-password" placeholder="Mật khẩu">
            <button style="width: 100%;" onclick="performLogin()">Đăng nhập</button>
        </div>

        <!-- 2. ADMIN VIEW -->
        <div id="admin-view" class="container" style="display:none;">
            <div class="tabs">
                <button class="tab-btn active" onclick="switchAdminTab('dashboard')">🏠 Dashboard</button>
                <button class="tab-btn" onclick="switchAdminTab('files')">📂 Quản lý File</button>
                <button class="tab-btn" onclick="switchAdminTab('nodes')">🔍 Node Viewer</button>
                <button class="tab-btn" onclick="switchAdminTab('users')">👥 Quản lý User</button>
                <button class="tab-btn" onclick="switchAdminTab('health')">🩺 Service Health</button>
                <button class="tab-btn" onclick="switchAdminTab('about')">ℹ️ Giới thiệu</button>
            </div>
            
            <div id="tab-dashboard" class="tab-content active">
                <div class="grid">
                    <div class="stat-box"><div>Hệ thống</div><div class="stat-value" id="dash-sys-status">⏳</div></div>
                    <div class="stat-box"><div>Tổng Document</div><div class="stat-value" id="dash-total">0</div></div>
                    <div class="stat-box"><div>Đã xử lý (Ready)</div><div class="stat-value" id="dash-ready" style="color: var(--success)">0</div></div>
                    <div class="stat-box"><div>Đang chạy/Lỗi</div><div class="stat-value" id="dash-processing" style="color: var(--warning)">0</div></div>
                </div>
                <div class="card">
                    <h2>Tài liệu gần đây</h2>
                    <table>
                        <thead><tr><th>ID</th><th>Tên File</th><th>Trạng thái</th><th>Tiến độ</th></tr></thead>
                        <tbody id="dash-recent-docs"><tr><td colspan="4">Đang tải...</td></tr></tbody>
                    </table>
                </div>
            </div>
            
            <div id="tab-files" class="tab-content">
                <div class="card">
                    <h2>Upload Tài liệu mới</h2>
                    <div class="upload-area" id="drop-zone" onclick="document.getElementById('file-input').click()">
                        <p>Kéo thả file vào đây hoặc <b>Nhấn để chọn file</b></p>
                        <p style="color: #64748b; font-size: 14px;">Hỗ trợ: PDF, DOCX, XLSX, TXT, MD</p>
                        <input type="file" id="file-input" style="display: none;" onchange="handleFileUpload(event)">
                    </div>
                    <div id="upload-status" style="margin-top: 10px; font-weight: bold;"></div>
                </div>
                <div class="card">
                    <h2>Danh sách Tài liệu <button onclick="fetchStats()" style="float: right; padding: 4px 8px; font-size: 12px;">🔄 Làm mới</button></h2>
                    <table>
                        <thead><tr><th>Tên File</th><th>Trạng thái</th><th>Tiến độ</th><th>Kích thước</th><th>Hành động</th></tr></thead>
                        <tbody id="files-table-body"><tr><td colspan="5">Đang tải...</td></tr></tbody>
                    </table>
                </div>
            </div>
            
            <div id="tab-nodes" class="tab-content">
                <div class="card">
                    <h2>🔍 Xem chi tiết Vector Node của Tài liệu</h2>
                    <div style="display: flex; gap: 10px; margin-bottom: 20px;">
                        <input type="text" id="node-doc-id" placeholder="Dán Document ID vào đây..." style="flex: 1; margin:0; font-family: monospace;">
                        <button onclick="viewNodes()">Tra cứu</button>
                    </div>
                    <div id="nodes-result"></div>
                </div>
            </div>
            
            <div id="tab-health" class="tab-content">
                <div class="card">
                    <h2>Trạng thái Service <button onclick="fetchStats()" style="float: right; padding: 4px 8px; font-size: 12px;">🔄 Làm mới</button></h2>
                    <div class="grid" id="health-grid"><div class="stat-box">Đang tải...</div></div>
                </div>
            </div>
            
            <div id="tab-users" class="tab-content">
                <div class="card">
                    <h2>Tạo Tài khoản Mới</h2>
                    <p style="color:#64748b;font-size:14px;">Tạo tài khoản <b>member</b> cho nhân viên sử dụng chức năng Chat, hoặc <b>admin</b> để quản lý hệ thống.</p>
                    <div style="max-width: 400px;">
                        <label style="font-size:14px;font-weight:600;display:block;margin-bottom:4px">Username (email)</label>
                        <input type="text" id="new-username" placeholder="VD: nhanvien@company.com" style="margin-bottom:15px">
                        <label style="font-size:14px;font-weight:600;display:block;margin-bottom:4px">Mật khẩu</label>
                        <input type="password" id="new-password" placeholder="Ít nhất 8 ký tự" style="margin-bottom:15px">
                        <label style="font-size:14px;font-weight:600;display:block;margin-bottom:8px">Vai trò</label>
                        <select id="new-role" style="padding:10px;border:1px solid var(--border-color);border-radius:4px;width:100%;margin-bottom:15px;font-size:14px">
                            <option value="member">member — Chỉ dùng Chat</option>
                            <option value="admin">admin — Quản trị toàn hệ thống</option>
                        </select>
                        <button style="width:100%" onclick="createUser()">✚ Tạo tài khoản</button>
                    </div>
                    <div id="user-create-status" style="margin-top:15px;font-weight:bold;"></div>

                    <h2 style="margin-top: 30px; border-top: 1px solid var(--border-color); padding-top: 20px;">Danh sách User Hiện tại <button class="outline-btn" onclick="fetchUsers()" style="font-size: 12px; float: right; padding: 4px 8px;">🔄 Làm mới</button></h2>
                    <table style="width: 100%; text-align: left; border-collapse: collapse; margin-top: 10px;">
                        <thead>
                            <tr style="background: #f1f5f9; border-bottom: 2px solid #cbd5e1;">
                                <th style="padding: 10px;">User ID</th>
                                <th style="padding: 10px;">Username</th>
                                <th style="padding: 10px;">Vai trò (Role)</th>
                            </tr>
                        </thead>
                        <tbody id="users-tbody">
                            <tr><td colspan="3" style="text-align: center; padding: 15px; color: #64748b;">Đang tải dữ liệu...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <div id="tab-about" class="tab-content">
                <div class="card" style="padding: 30px; line-height: 1.6; color: #334155;">
                    <h1 style="color: var(--primary); margin-bottom: 5px; font-size: 28px;">🚀 Phân tích Hệ thống: Enterprise RAG Chatbot</h1>
                    <p style="color: #64748b; font-size: 16px; margin-bottom: 30px; font-weight: 500;">Báo cáo Thiết kế Kiến trúc và Luồng dữ liệu (Data Flow) - Chatbot AI Nội bộ (On-Premises) chuyên dụng cho Doanh nghiệp.</p>

                    <h2 style="border-bottom: 2px solid var(--primary); padding-bottom: 8px; color: #0f172a; margin-top: 30px;">1. Tổng quan Dự án (Project Overview)</h2>
                    <div style="background: #f8fafc; border-left: 4px solid var(--primary); padding: 15px 20px; border-radius: 0 8px 8px 0; margin-bottom: 20px;">
                        <p style="margin: 0;"><b>Enterprise RAG Chatbot</b> là một hệ thống Trợ lý ảo AI được xây dựng theo kiến trúc <strong>Retrieval-Augmented Generation (RAG)</strong>. Mục đích cốt lõi là khắc phục nhược điểm "ảo giác" (hallucination) thường gặp của các mô hình AI ngôn ngữ lớn (LLM) bằng cách ép AI phải <b>đọc và trích xuất thông tin nghiêm ngặt từ kho tài liệu mật của doanh nghiệp</b> trước khi trả lời người dùng. Hệ thống hỗ trợ triển khai hoàn toàn Offline (Air-gapped) để bảo vệ 100% tài sản trí tuệ (Data Privacy).</p>
                    </div>

                    <h2 style="border-bottom: 2px solid var(--primary); padding-bottom: 8px; color: #0f172a; margin-top: 30px;">2. Luồng Xử lý Dữ liệu (System Workflow)</h2>
                    
                    <h3 style="color: #1d4ed8; margin-top: 20px;">A. Luồng Nhập liệu (Ingestion Pipeline)</h3>
                    <p>Khi Admin tải lên một tài liệu mới (PDF, DOCX...), quá trình xử lý diễn ra như sau để tối ưu hóa hiệu năng và không làm treo hệ thống:</p>
                    <ol style="margin-left: 20px; margin-bottom: 20px; padding-left: 10px;">
                        <li style="margin-bottom: 8px;"><b>1. Nhận File & Lưu trữ:</b> API nhận file, ngay lập tức lưu vào ổ cứng (RustFS/S3) và cập nhật trạng thái "Đang Cài đặt" vào <b>PostgreSQL</b>. API trả về <code>task_id</code> cho người dùng và kết thúc kết nối ngay (Asynchronous).</li>
                        <li style="margin-bottom: 8px;"><b>2. Background Queue:</b> <code>task_id</code> được đẩy vào hàng đợi <b>Redis</b>.</li>
                        <li style="margin-bottom: 8px;"><b>3. Worker Xử lý:</b> <b>Celery Worker</b> (một tiến trình ngầm có quyền truy cập GPU) cấu trúc nhận task. Nó bắt đầu dùng <b>Docling & EasyOCR</b> để bóc tách chữ, bảng biểu, và nhận dạng cấu trúc (Header 1, Header 2) của file gốc.</li>
                        <li style="margin-bottom: 8px;"><b>4. Hierarchical Chunking (Cắt phân cấp):</b> File không bị chặt khúc 500 từ mù quáng, mà được bảo toàn theo cấu trúc: <i>Chương -> Mục -> Trang -> Đoạn văn</i> (Bảo toàn ngữ cảnh). Nhờ đó, AI đọc văn bản không bị đứt đoạn tư duy.</li>
                        <li style="margin-bottom: 8px;"><b>5. Embedding & Vector hóa:</b> Đoạn chữ sau khi nén được truyền qua mô hình AI <code>BAAI/bge-m3</code> (chuyên Tiếng Việt) trên GPU để biến thành các ma trận số <b>đa chiều (Vector)</b>.</li>
                        <li style="margin-bottom: 8px;"><b>6. Persist Qdrant:</b> Hàng ngàn Vector vừa tạo được nạp vào mạng lưới Vector Database <b>Qdrant (Rust)</b> siêu tốc. Document được đánh dấu "Ready" trong PostgreSQL.</li>
                    </ol>

                    <h3 style="color: #047857; margin-top: 20px;">B. Luồng Trả lời Hỏi Đáp (Retrieval & Chat Pipeline)</h3>
                    <p>Đây là quá trình diễn ra trong vài giây khi Nhân viên (Member) nhắn tin cho AI:</p>
                    <ul style="margin-left: 20px; margin-bottom: 20px; padding-left: 10px;">
                        <li style="margin-bottom: 8px;"><b>1. Embedding Câu hỏi:</b> Dòng tin nhắn <i>"Chính sách nghỉ phép tự kỷ là gì?"</i> lập tức được mô hình AI dịch sang chung "ngôn ngữ Vector" cùng với kho dữ liệu.</li>
                        <li style="margin-bottom: 8px;"><b>2. Vector Search (Qdrant Tìm kiếm):</b> Thuật toán <b>Cosine Similarity</b> đo khoảng cách giữa vector "câu hỏi" với hàng triệu vector "tài liệu" trong kho để móc ra Top 5 đoạn văn giống nghĩa nhất (kể cả khi rập khuôn từ khóa không trùng khớp).</li>
                        <li style="margin-bottom: 8px;"><b>3. Prompt Engineering:</b> Top 5 đoạn văn này được bọc lại trong 1 cái khung Context (Bối cảnh). Hệ thống ra lệnh cho LLM: <i>"Đây là bối cảnh công ty. Hãy dựa DUY NHẤT vào đây để trả lời câu hỏi sau. Nếu không có dữ liệu, hãy nói KHÔNG BIẾT, cấm bịa đặt."</i></li>
                        <li style="margin-bottom: 8px;"><b>4. Sinh Text (Generation) & Trích Dẫn:</b> LLM đẻ ra đoạn văn trả lời, kèm theo chính xác <b>Citations (Trích dẫn)</b>: Lấy từ đoạn văn nào, File tên gì, Trang bao nhiêu. Dữ liệu vội vàng trả về Client UI cho user đọc.</li>
                    </ul>

                    <h2 style="border-bottom: 2px solid var(--primary); padding-bottom: 8px; color: #0f172a; margin-top: 30px;">3. Danh mục API Cốt lõi (API Reference)</h2>
                    <p>Hệ thống Backend (FastAPI) hoạt động qua chuẩn REST API. Dưới đây là chức năng của các "nút mạng" chính thức:</p>
                    
                    <div style="display: grid; grid-template-columns: 1fr; gap: 10px; margin-top: 15px;">
                        <div style="background: #fff; border: 1px solid #e2e8f0; padding: 15px; border-radius: 6px;">
                            <h4 style="margin: 0 0 5px 0; color: #b91c1c;">🔐 Phân hệ Xác thực (Auth API)</h4>
                            <p style="margin: 0; font-size: 14px;"><code>POST /api/v1/auth/login</code>: Bắt user khai báo Tên/Pass để cấp thẻ bài <b>JWT (JSON Web Token)</b>.<br><code>POST /api/v1/auth/users</code>: Admin dùng để tạo tài khoản mới ngay trên mạch ngầm.</p>
                        </div>
                        <div style="background: #fff; border: 1px solid #e2e8f0; padding: 15px; border-radius: 6px;">
                            <h4 style="margin: 0 0 5px 0; color: #ea580c;">📥 Phân hệ Upload & Pipeline (Ingestion API)</h4>
                            <p style="margin: 0; font-size: 14px;"><code>POST /api/v1/upload</code>: Cổng nhập liệu chính, chặn file dung lượng quá khổ.<br><code>GET /api/v1/status/{{task_id}}</code>: Cổng giám sát tiến độ (Download -> Read -> Encode -> Finish) realtime.<br><code>DELETE /api/v1/documents/{{id}}</code>: Lệnh tử hình - rà soát và xóa vĩnh viễn tàn tích File trên cả Database, Qdrant và Ổ cứng.</p>
                        </div>
                        <div style="background: #fff; border: 1px solid #e2e8f0; padding: 15px; border-radius: 6px;">
                            <h4 style="margin: 0 0 5px 0; color: #0d9488;">💬 Phân hệ Tương tác AI (Chat API)</h4>
                            <p style="margin: 0; font-size: 14px;"><code>POST /api/v1/chat</code>: Đầu não tiếp nhận câu hỏi nhạy cảm và trả về Streaming hoặc JSON chứa Answer & Citation. Chỉ những tài khoản có thẻ bài JWT mới lọt qua được cửa này.</p>
                        </div>
                        <div style="background: #fff; border: 1px solid #e2e8f0; padding: 15px; border-radius: 6px;">
                            <h4 style="margin: 0 0 5px 0; color: #4338ca;">🩺 Phân hệ Giám sát Rủi ro (Health API)</h4>
                            <p style="margin: 0; font-size: 14px;"><code>GET /api/v1/health</code> & <code>/view/nodes</code>: "Máy chụp X-Quang" của hệ thống. Kiểm tra sinh hiệu của Database, Redis, Worker và đặc biệt soi rõ tường tận nội thất từng Vector Node ở bên trong não bộ AI.</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- 3. MEMBER CHAT VIEW -->
        <div id="member-view" class="container" style="display:none; max-width: 800px;">
            <div class="card">
                <h2>💬 Chat với Trợ lý AI (Chế độ Member)</h2>
                <p style="color:#64748b; font-size:14px; margin-bottom: 20px;">AI sẽ trả lời dựa trên các dữ liệu doanh nghiệp đã được Admin upload và xử lý thành công.</p>
                
                <div id="chat-window">
                    <div class="chat-msg bot">Xin chào! Tôi có thể giúp gì cho bạn dựa trên tài liệu hiện có?</div>
                </div>
                
                <div style="display: flex; gap: 10px;">
                    <input type="text" id="chat-input" placeholder="Nhập câu hỏi của bạn..." style="flex: 1; margin:0;" onkeypress="if(event.key === 'Enter') sendChat()">
                    <button id="chat-btn" onclick="sendChat()">Gửi</button>
                </div>
            </div>
        </div>

        <script>
            let currentToken = localStorage.getItem('access_token');
            let currentRole = localStorage.getItem('role');

            function showView(viewId) {{
                document.getElementById('login-view').style.display = 'none';
                document.getElementById('admin-view').style.display = 'none';
                document.getElementById('member-view').style.display = 'none';
                document.getElementById('navbar').style.display = 'flex';
                document.getElementById(viewId).style.display = 'block';
            }}

            function checkAuth() {{
                if (!currentToken) {{
                    document.getElementById('navbar').style.display = 'none';
                    document.getElementById('login-view').style.display = 'block';
                }} else {{
                    document.getElementById('user-role-badge').textContent = 'Vai trò: ' + currentRole.toUpperCase();
                    if (currentRole === 'admin') {{
                        showView('admin-view');
                        fetchStats();
                    }} else {{
                        showView('member-view');
                    }}
                }}
            }}

            // ─── AUTH LOGIC ──────────────────────────────────────────────────────────
            async function performLogin() {{
                const user = document.getElementById('login-username').value;
                const pass = document.getElementById('login-password').value;
                const errDiv = document.getElementById('login-error');
                errDiv.textContent = 'Đang xử lý...';

                try {{
                    const res = await fetch('{prefix}/auth/login', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{ username: user, password: pass }})
                    }});
                    const data = await res.json();
                    
                    if (res.ok) {{
                        currentToken = data.access_token;
                        currentRole = data.role;
                        localStorage.setItem('access_token', currentToken);
                        localStorage.setItem('role', currentRole);
                        errDiv.textContent = '';
                        checkAuth();
                    }} else {{
                        errDiv.textContent = data.detail || 'Sai tài khoản hoặc mật khẩu!';
                    }}
                }} catch (e) {{
                    errDiv.textContent = 'Lỗi kết nối máy chủ.';
                }}
            }}

            function logout() {{
                localStorage.removeItem('access_token');
                localStorage.removeItem('role');
                location.reload();
            }}

            // ─── ADMIN LOGIC ─────────────────────────────────────────────────────────
            function switchAdminTab(tabId) {{
                document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
                document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
                event.target.classList.add('active');
                document.getElementById('tab-' + tabId).classList.add('active');
                if(tabId === 'dashboard' || tabId === 'files' || tabId === 'health') fetchStats();
                if(tabId === 'users') fetchUsers();
            }}

            function formatBytes(bytes) {{
                if(bytes === 0) return '0 Bytes';
                const k = 1024, dm = 2, sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
                const i = Math.floor(Math.log(bytes) / Math.log(k));
                return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
            }}

            async function fetchStats() {{
                if(currentRole !== 'admin') return;
                try {{
                    const res = await fetch('/view/stats');
                    const data = await res.json();
                    
                    document.getElementById('dash-sys-status').innerHTML = `<span class="badge ${{data.status === 'healthy' ? 'up' : 'down'}}">${{data.status.toUpperCase()}}</span>`;
                    document.getElementById('dash-total').textContent = data.total;
                    document.getElementById('dash-ready').textContent = data.ready;
                    document.getElementById('dash-processing').textContent = data.processing + data.failed;
                    
                    let rowsHtml = '';
                    let recentHtml = '';
                    
                    data.documents.forEach((doc, idx) => {{
                        let badgeClass = doc.status === 'ready' ? 'ready' : (doc.status === 'failed' ? 'failed' : 'processing');
                        const row = `<tr>
                            <td>${{doc.file_name}}</td>
                            <td><span class="badge ${{badgeClass}}">${{doc.status}}</span></td>
                            <td>${{doc.progress_percent}}%</td>
                            <td>${{formatBytes(doc.file_size)}}</td>
                            <td>
                                <button onclick="document.getElementById('node-doc-id').value='${{doc.id}}'; switchAdminTab('nodes');" style="font-size: 12px; padding: 4px 8px;">🔍</button>
                                <button class="danger-btn" onclick="deleteDocument('${{doc.id}}')" style="font-size: 12px; padding: 4px 8px;">🗑️</button>
                            </td>
                        </tr>`;
                        rowsHtml += row;
                        if(idx < 5) recentHtml += `<tr><td style="font-family: monospace; font-size: 12px;">${{doc.id.substring(0,8)}}</td><td>${{doc.file_name}}</td><td><span class="badge ${{badgeClass}}">${{doc.status}}</span></td><td>${{doc.progress_percent}}%</td></tr>`;
                    }});
                    
                    document.getElementById('files-table-body').innerHTML = rowsHtml || '<tr><td colspan="5">Chưa có tài liệu</td></tr>';
                    document.getElementById('dash-recent-docs').innerHTML = recentHtml || '<tr><td colspan="4">Chưa có tài liệu</td></tr>';
                    
                    let healthHtml = '';
                    for (const [service, info] of Object.entries(data.services)) {{
                        healthHtml += `<div class="stat-box"><h3>${{service.toUpperCase()}}</h3><div style="margin-top: 10px;"><span class="badge ${{info.status === 'up' ? 'up' : 'down'}}">${{info.status.toUpperCase()}}</span></div></div>`;
                    }}
                    document.getElementById('health-grid').innerHTML = healthHtml;
                }} catch (e) {{ console.error(e); }}
            }}

            async function handleFileUpload(event) {{
                const file = event.target.files[0];
                if (!file) return;
                
                const statusDiv = document.getElementById('upload-status');
                statusDiv.textContent = `Đang tải lên: ${{file.name}}...`;
                statusDiv.style.color = 'var(--warning)';
                
                const formData = new FormData();
                formData.append('file', file);
                
                try {{
                    const res = await fetch('{prefix}/upload', {{
                        method: 'POST',
                        headers: {{ 'Authorization': `Bearer ${{currentToken}}` }}, // GẮN TOKEN Ở ĐÂY LÀ HẾT LỖI 405/401
                        body: formData
                    }});
                    
                    if(res.ok) {{
                        statusDiv.textContent = `✅ Tải lên thành công!`;
                        statusDiv.style.color = 'var(--success)';
                        fetchStats();
                    }} else {{
                        const err = await res.json();
                        statusDiv.textContent = `❌ Lỗi: ${{err.detail || res.statusText}}`;
                        statusDiv.style.color = 'var(--danger)';
                    }}
                }} catch(err) {{
                    statusDiv.textContent = `❌ Lỗi mạng: ${{err.message}}`;
                    statusDiv.style.color = 'var(--danger)';
                }}
            }}

            async function deleteDocument(id) {{
                if(!confirm('Xác nhận xóa tài liệu này? Hệ thống sẽ dọn dẹp sạch sẽ File, Database và Qdrant Vector.')) return;
                try {{
                    const res = await fetch(`{prefix}/documents/${{id}}`, {{
                        method: 'DELETE',
                        headers: {{ 'Authorization': `Bearer ${{currentToken}}` }}
                    }});
                    if(res.ok) {{ alert('Đã gửi lệnh xóa. Worker đang dọn dẹp ngầm...'); fetchStats(); }}
                    else {{ const err = await res.json(); alert('Xóa thất bại: ' + (err.detail || res.status)); }}
                }} catch(err) {{ alert('Lỗi mạng'); }}
            }}

            async function viewNodes() {{
                const docId = document.getElementById('node-doc-id').value.trim();
                const resultDiv = document.getElementById('nodes-result');
                if(!docId) {{ resultDiv.innerHTML = '<p style="color:var(--danger)">Vui lòng nhập Document ID.</p>'; return; }}

                resultDiv.innerHTML = '<p style="color:var(--warning)">⏳ Đang tải danh sách node từ Qdrant...</p>';

                try {{
                    const res = await fetch(`/view/nodes?document_id=${{encodeURIComponent(docId)}}`);
                    const html_text = await res.text();
                    // Parse the HTML response and extract the table part for inline display
                    const parser = new DOMParser();
                    const doc_html = parser.parseFromString(html_text, 'text/html');
                    const card = doc_html.querySelector('.card');
                    if(card) {{
                        // Fix links to open in new tab
                        card.querySelectorAll('a').forEach(a => a.setAttribute('target', '_blank'));
                        resultDiv.innerHTML = card.innerHTML;
                    }} else {{
                        resultDiv.innerHTML = html_text;
                    }}
                }} catch(e) {{
                    resultDiv.innerHTML = `<p style="color:var(--danger)">❌ Lỗi tải nodes: ${{e.message}}</p>`;
                }}
            }}

            async function createUser() {{
                const username = document.getElementById('new-username').value.trim();
                const password = document.getElementById('new-password').value;
                const role = document.getElementById('new-role').value;
                const statusDiv = document.getElementById('user-create-status');

                if(!username || !password) {{
                    statusDiv.textContent = '❌ Vui lòng nhập đầy đủ Username và Mật khẩu.';
                    statusDiv.style.color = 'var(--danger)';
                    return;
                }}
                statusDiv.textContent = 'Đang tạo...';
                statusDiv.style.color = 'var(--warning)';

                try {{
                    const res = await fetch('{prefix}/auth/users', {{
                        method: 'POST',
                        headers: {{
                            'Content-Type': 'application/json',
                            'Authorization': `Bearer ${{currentToken}}`
                        }},
                        body: JSON.stringify({{ username, password, role }})
                    }});
                    const data = await res.json();
                    if(res.ok) {{
                        statusDiv.innerHTML = `✅ Tạo thành công! <br>Username: <b>${{data.username}}</b> | Vai trò: <b>${{data.role}}</b> | ID: <code style="font-size:12px">${{data.id}}</code>`;
                        statusDiv.style.color = 'var(--success)';
                        document.getElementById('new-username').value = '';
                        document.getElementById('new-password').value = '';
                        fetchUsers();
                    }} else {{
                        statusDiv.textContent = `❌ Lỗi: ${{data.detail || res.statusText}}`;
                        statusDiv.style.color = 'var(--danger)';
                    }}
                }} catch(e) {{
                    statusDiv.textContent = `❌ Lỗi mạng: ${{e.message}}`;
                    statusDiv.style.color = 'var(--danger)';
                }}
            }}

            async function fetchUsers() {{
                if(currentRole !== 'admin') return;
                const tbody = document.getElementById('users-tbody');
                try {{
                    const res = await fetch('{prefix}/auth/users', {{
                        headers: {{ 'Authorization': `Bearer ${{currentToken}}` }}
                    }});
                    const data = await res.json();
                    if(res.ok) {{
                        if (data.length === 0) {{
                            tbody.innerHTML = '<tr><td colspan="3" style="text-align: center; padding: 15px;">Chưa có tài khoản nào</td></tr>';
                        }} else {{
                            tbody.innerHTML = data.map(u => `
                                <tr>
                                    <td style="font-family: monospace; font-size: 12px; color: #64748b;">${{u.id.substring(0,8)}}...</td>
                                    <td style="font-weight: 600;">${{u.username}}</td>
                                    <td><span class="badge ${{u.role === 'admin' ? 'ready' : 'processing'}}">${{u.role.toUpperCase()}}</span></td>
                                </tr>
                            `).join('');
                        }}
                    }} else {{
                        tbody.innerHTML = `<tr><td colspan="3" style="text-align: center; padding: 15px; color: red;">Lỗi tải dữ liệu: ${{data.detail}}</td></tr>`;
                    }}
                }} catch(e) {{
                    tbody.innerHTML = `<tr><td colspan="3" style="text-align: center; padding: 15px; color: red;">Lỗi kết nối máy chủ</td></tr>`;
                }}
            }}

            // ─── MEMBER CHAT LOGIC ───────────────────────────────────────────────────
            async function sendChat() {{
                const input = document.getElementById('chat-input');
                const btn = document.getElementById('chat-btn');
                const windowDiv = document.getElementById('chat-window');
                const query = input.value.trim();
                if(!query) return;

                // Thêm tin nhắn User
                windowDiv.innerHTML += `<div class="chat-msg user">${{htmlEscape(query)}}</div>`;
                input.value = '';
                btn.disabled = true;
                windowDiv.scrollTop = windowDiv.scrollHeight;

                try {{
                    const res = await fetch('{prefix}/chat', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json', 'Authorization': `Bearer ${{currentToken}}` }},
                        body: JSON.stringify({{ query: query }})
                    }});
                    const data = await res.json();
                    
                    if(res.ok) {{
                        let botHtml = `<div class="chat-msg bot"><div>${{data.answer}}</div>`;
                        // Hiển thị citations nếu có
                        if(data.citations && data.citations.length > 0) {{
                            const cites = data.citations.map(c => c.filename + ' (Page ' + (c.page || 1) + ')').join(' | ');
                            botHtml += `<div class="citation-box">Nguồn: ${{cites}}</div>`;
                        }}
                        botHtml += `</div>`;
                        windowDiv.innerHTML += botHtml;
                    }} else {{
                        windowDiv.innerHTML += `<div class="chat-msg bot" style="color:var(--danger)">Lỗi: ${{data.detail || 'Không thể lấy phản hồi.'}}</div>`;
                    }}
                }} catch (e) {{
                    windowDiv.innerHTML += `<div class="chat-msg bot" style="color:var(--danger)">Lỗi mạng. Vui lòng thử lại.</div>`;
                }}
                
                btn.disabled = false;
                windowDiv.scrollTop = windowDiv.scrollHeight;
            }}

            function htmlEscape(str) {{ return str.replace(/[&<>'"]/g, tag => ({{ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }}[tag] || tag)); }}

            // ─── INIT ────────────────────────────────────────────────────────────────
            window.onload = checkAuth;
            setInterval(() => {{
                if(currentRole === 'admin' && (document.getElementById('tab-dashboard').classList.contains('active') || document.getElementById('tab-files').classList.contains('active'))) fetchStats();
            }}, 5000);

            // Drag/Drop event listeners
            const dropZone = document.getElementById('drop-zone');
            ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eName => dropZone?.addEventListener(eName, e => {{e.preventDefault(); e.stopPropagation();}}, false));
            dropZone?.addEventListener('drop', e => {{ const files = e.dataTransfer.files; if(files.length > 0) {{ document.getElementById('file-input').files = files; handleFileUpload({{target: {{files: files}}}}); }} }}, false);
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


# ─────────────────────────────────────────────────────────────────────────────
# /view/nodes — Node Viewer (replaces /health/nodes, no "Back to health" clutter)
# /view/node  — Single Node Detail
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_nodes(document_id: str, limit: int = 50) -> list[dict]:
    import httpx
    body = {
        "with_payload": True,
        "with_vector": False,
        "limit": limit,
        "filter": {"must": [{"key": "document_id", "match": {"value": document_id}}]},
    }
    headers = {"Content-Type": "application/json"}
    if settings.qdrant_api_key:
        headers["api-key"] = settings.qdrant_api_key
    try:
        with httpx.Client(timeout=5.0) as client:
            r = client.post(
                f"{settings.qdrant_url.rstrip('/')}/collections/{settings.qdrant_collection}/points/scroll",
                headers=headers, json=body,
            )
            r.raise_for_status()
            return r.json().get("result", {}).get("points", [])
    except Exception:
        return []


def _fetch_single_node(document_id: str, node_id: str) -> dict | None:
    import httpx
    body = {
        "with_payload": True,
        "with_vector": False,
        "limit": 1,
        "filter": {"must": [
            {"key": "document_id", "match": {"value": document_id}},
            {"key": "node_id", "match": {"value": node_id}},
        ]},
    }
    headers = {"Content-Type": "application/json"}
    if settings.qdrant_api_key:
        headers["api-key"] = settings.qdrant_api_key
    try:
        with httpx.Client(timeout=5.0) as client:
            r = client.post(
                f"{settings.qdrant_url.rstrip('/')}/collections/{settings.qdrant_collection}/points/scroll",
                headers=headers, json=body,
            )
            r.raise_for_status()
            pts = r.json().get("result", {}).get("points", [])
            return pts[0] if pts else None
    except Exception:
        return None


@router.get("/view/nodes")
async def view_nodes_page(document_id: str = ""):
    import html as html_lib
    import json
    points = _fetch_nodes(document_id) if document_id else []

    rows_html = ""
    for pt in points:
        p = pt.get("payload", {})
        nid = html_lib.escape(str(p.get("node_id", ""))[:8])
        nid_full = html_lib.escape(str(p.get("node_id", "")))
        ntype = html_lib.escape(str(p.get("node_type", "-")))
        section = html_lib.escape(str(p.get("section_title", "-")))
        page = html_lib.escape(str(p.get("page_number", "-")))
        text = str(p.get("text", "")).replace("\n", " ").strip()
        text_len = len(str(p.get("text", "")))
        preview = html_lib.escape(text[:150] + "..." if len(text) > 150 else text)
        rows_html += f"""
        <tr>
            <td style="font-family:monospace;font-size:12px" title="{nid_full}">{nid}...</td>
            <td><span class="badge {ntype.lower()}">{ntype}</span></td>
            <td>{section}</td>
            <td style="text-align:center">{page}</td>
            <td style="text-align:center">{text_len}</td>
            <td style="font-size:13px;color:#475569">{preview}</td>
            <td><a href="/view/node?document_id={html_lib.escape(document_id)}&node_id={html_lib.escape(str(p.get('node_id','')))}" target="_blank" style="color:#3b82f6;font-size:13px;">Xem chi tiết</a></td>
        </tr>"""

    if not rows_html:
        rows_html = "<tr><td colspan='7' style='text-align:center;color:#94a3b8;padding:30px'>Không tìm thấy Node nào</td></tr>"

    content = f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Node Viewer — {html_lib.escape(document_id[:16])}...</title>
<style>
  body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#f8fafc;color:#334155;margin:0;padding:20px}}
  .card{{background:#fff;border:1px solid #e2e8f0;border-radius:8px;padding:20px;box-shadow:0 1px 3px rgba(0,0,0,.08)}}
  table{{width:100%;border-collapse:collapse;margin-top:15px}}
  th,td{{padding:10px 12px;text-align:left;border-bottom:1px solid #e2e8f0;vertical-align:top}}
  th{{background:#f1f5f9;font-size:13px;font-weight:600;color:#475569}}
  td{{font-size:14px}}
  .badge{{padding:3px 8px;border-radius:10px;font-size:11px;font-weight:700;color:#fff;text-transform:uppercase}}
  .leaf,.text{{background:#3b82f6}}
  .section,.heading{{background:#8b5cf6}}
  .table{{background:#f59e0b;color:#fff}}
  .meta{{display:flex;gap:20px;margin-bottom:15px;flex-wrap:wrap}}
  .meta span{{background:#e0f2fe;color:#0369a1;padding:4px 10px;border-radius:4px;font-size:13px}}
  h2{{margin:0 0 15px;color:#0f172a}}
</style>
</head>
<body>
<div class="card">
  <h2>🔍 Vector Nodes — Tài liệu</h2>
  <div class="meta">
    <span>📄 Document ID: <strong>{html_lib.escape(document_id)}</strong></span>
    <span>🔢 Tổng số Node: <strong>{len(points)}</strong></span>
    <span>📦 Collection: <strong>{html_lib.escape(settings.qdrant_collection)}</strong></span>
  </div>
  <table>
    <thead>
      <tr>
        <th>Node ID</th><th>Loại</th><th>Tiêu đề Section</th>
        <th>Trang</th><th>Độ dài</th><th>Nội dung Preview</th><th>Chi tiết</th>
      </tr>
    </thead>
    <tbody>{rows_html}</tbody>
  </table>
</div>
</body>
</html>"""
    return HTMLResponse(content=content)


@router.get("/view/node")
async def view_node_detail_page(document_id: str = "", node_id: str = ""):
    import html as html_lib
    import json
    point = _fetch_single_node(document_id, node_id) if document_id and node_id else None

    if not point:
        content = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><style>body{{font-family:sans-serif;padding:30px;background:#f8fafc}}</style></head>
<body><h2 style="color:#ef4444">❌ Không tìm thấy Node</h2>
<p>Document ID: <code>{html_lib.escape(document_id)}</code><br>Node ID: <code>{html_lib.escape(node_id)}</code></p>
<a href="javascript:window.close()" style="color:#3b82f6">Đóng tab này</a>
</body></html>"""
        return HTMLResponse(content=content, status_code=404)

    p = point.get("payload", {})
    text = str(p.get("text", ""))
    metadata = p.get("metadata", {})

    content = f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Node Detail</title>
<style>
  body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#f8fafc;color:#334155;margin:0;padding:20px}}
  .card{{background:#fff;border:1px solid #e2e8f0;border-radius:8px;padding:20px;margin-bottom:15px;box-shadow:0 1px 3px rgba(0,0,0,.08)}}
  .meta-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px;margin-bottom:15px}}
  .meta-item{{background:#f1f5f9;padding:12px;border-radius:6px}}
  .meta-item label{{font-size:12px;color:#64748b;display:block;margin-bottom:4px;font-weight:600}}
  .meta-item value{{font-size:14px;color:#0f172a;word-break:break-all;font-family:monospace}}
  pre{{background:#1e293b;color:#e2e8f0;padding:20px;border-radius:8px;white-space:pre-wrap;font-size:13px;line-height:1.6;overflow:auto;max-height:500px}}
  h2{{margin:0 0 15px;color:#0f172a}}
  .back-btn{{display:inline-block;margin-bottom:15px;color:#3b82f6;font-size:14px;cursor:pointer;border:none;background:none;padding:0}}
</style>
</head>
<body>
<button class="back-btn" onclick="window.close()">✕ Đóng tab</button>
<div class="card">
  <h2>📄 Chi tiết Node</h2>
  <div class="meta-grid">
    <div class="meta-item"><label>Document ID</label><value>{html_lib.escape(str(p.get('document_id',''))[:])}</value></div>
    <div class="meta-item"><label>Node ID</label><value>{html_lib.escape(str(p.get('node_id','')))}</value></div>
    <div class="meta-item"><label>Loại Node</label><value>{html_lib.escape(str(p.get('node_type','-')))}</value></div>
    <div class="meta-item"><label>Section / Tiêu đề</label><value>{html_lib.escape(str(p.get('section_title','-')))}</value></div>
    <div class="meta-item"><label>Số trang</label><value>{html_lib.escape(str(p.get('page_number','-')))}</value></div>
    <div class="meta-item"><label>Parent Node ID</label><value>{html_lib.escape(str(p.get('parent_id','-')))}</value></div>
    <div class="meta-item"><label>Thứ tự (Order)</label><value>{html_lib.escape(str(p.get('order','-')))}</value></div>
    <div class="meta-item"><label>Độ dài văn bản</label><value>{len(text)} ký tự</value></div>
  </div>
</div>

<div class="card">
  <h2>📝 Nội dung văn bản (Text)</h2>
  <pre>{html_lib.escape(text)}</pre>
</div>

<div class="card">
  <h2>🗂️ Metadata</h2>
  <pre>{html_lib.escape(json.dumps(metadata, ensure_ascii=False, indent=2))}</pre>
</div>
</body>
</html>"""
    return HTMLResponse(content=content)
