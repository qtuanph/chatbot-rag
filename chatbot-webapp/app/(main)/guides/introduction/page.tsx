"use client";

import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { 
  Building2Icon, 
  DatabaseIcon, 
  BrainCircuitIcon, 
  ShieldCheckIcon,
  MessageSquareTextIcon,
  HelpCircleIcon,
  InfoIcon,
  ServerIcon,
  KeyIcon,
  ArrowRightLeftIcon,
  CpuIcon,
  LayersIcon,
  ShieldAlertIcon,
  NetworkIcon,
  WorkflowIcon,
  ZapIcon,
  SparklesIcon,
  FileTextIcon,
  CheckCircle2Icon,
  BotIcon,
} from "lucide-react";

export default function IntroductionGuidePage() {
  return (
    <div className="space-y-8 pb-16 max-w-4xl">
      {/* Title & Overview */}
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <h1 className="text-3xl font-bold tracking-tight text-foreground">Giới thiệu &amp; Kiến trúc Nền tảng RAG Enterprise</h1>
          <Badge variant="default" className="text-xs bg-primary text-primary-foreground">
            {process.env.NEXT_PUBLIC_APP_VERSION || "v1.2"}
          </Badge>
        </div>
        <p className="text-sm text-muted-foreground leading-relaxed max-w-3xl">
          Tài liệu kỹ thuật tổng quan về Nền tảng Hỏi đáp dữ liệu tự động (RAG - Retrieval-Augmented Generation) đa doanh nghiệp. 
          Hệ thống được thiết kế theo mô hình <strong>API-First / Headless Enterprise</strong>, tối ưu cho việc tích hợp trực tiếp vào các phần mềm nghiệp vụ (ERP, CRM, Portal).
        </p>
      </div>

      {/* Target Audience Alert */}
      <Alert className="bg-muted/50 border-border">
        <InfoIcon className="h-5 w-5 text-primary" />
        <AlertTitle className="font-bold text-foreground">Cẩm nang vận hành dành cho Ban Quản trị, PM, BA và Kỹ sư Phần mềm</AlertTitle>
        <AlertDescription className="text-xs leading-5 mt-1 text-muted-foreground">
          Giao diện Webapp này đóng vai trò <strong>Admin Control Plane</strong> giúp quản trị Tenants, nạp tri thức tài liệu, giám sát nhật ký AI và khởi tạo FAQ. Trí tuệ AI sẽ được nhúng thẳng vào các ứng dụng doanh nghiệp hiện hữu thông qua API Key chuẩn hoặc Widget Chatbot nhúng.
        </AlertDescription>
      </Alert>

      {/* ── BẢN ĐỒ KIẾN TRÚC HỆ THỐNG ── */}
      <section className="border border-border rounded-xl p-6 bg-card space-y-6">
        <div className="space-y-1">
          <h2 className="text-lg font-bold text-foreground flex items-center gap-2">
            <NetworkIcon className="w-5 h-5 text-primary" />
            Sơ đồ kiến trúc &amp; Luồng xử lý dữ liệu
          </h2>
          <p className="text-xs text-muted-foreground leading-relaxed">
            Mô hình tương tác 4 tầng: Client Layer (ERP/Widget) ➔ API Gateway ➔ RAG Core Service ➔ Storage &amp; AI Provider
          </p>
        </div>

        {/* CSS Architecture Flow Chart */}
        <div className="flex flex-col gap-4 pt-2">
          {/* Top Row: Client layer */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="border border-border rounded-lg p-3 bg-muted/20 flex flex-col items-center justify-center text-center space-y-1">
              <span className="text-[10px] uppercase font-semibold text-muted-foreground">Client Layer</span>
              <span className="font-bold text-xs text-foreground">Phần mềm Doanh nghiệp (ERP / CRM / Web)</span>
              <p className="text-[10px] text-muted-foreground">Nhúng Widget Chatbot hoặc gọi trực tiếp API REST</p>
            </div>
            <div className="border border-border rounded-lg p-3 bg-muted/20 flex flex-col items-center justify-center text-center space-y-1">
              <span className="text-[10px] uppercase font-semibold text-muted-foreground">Control Plane</span>
              <span className="font-bold text-xs text-foreground">Webapp Dashboard (Next.js)</span>
              <p className="text-[10px] text-muted-foreground">Admin quản lý Tenants, Kho tài liệu, Audit AI &amp; FAQ</p>
            </div>
          </div>

          {/* Vertical Arrow */}
          <div className="flex justify-center text-muted-foreground my-1">
            <ArrowRightLeftIcon className="w-4 h-4 rotate-90" />
          </div>

          {/* Middle Row: Backend Layer */}
          <div className="border border-border rounded-lg p-4 bg-muted/10 space-y-3">
            <div className="flex justify-between items-center border-b border-border pb-2">
              <span className="text-[10px] uppercase font-bold text-muted-foreground">Backend Engine Layer (FastAPI + Redis + Celery)</span>
              <Badge variant="outline" className="text-[10px]">Docker Microservices</Badge>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-2.5">
              <div className="border border-border bg-card rounded p-2.5 text-center">
                <span className="font-semibold text-xs text-foreground block">FastAPI Gateway</span>
                <span className="text-[10px] text-muted-foreground">Xác thực Tenant API Key, xử lý Wildcard CORS &amp; Rate Limit</span>
              </div>
              <div className="border border-border bg-card rounded p-2.5 text-center">
                <span className="font-semibold text-xs text-foreground block">Exact &amp; FAQ Cache</span>
                <span className="text-[10px] text-muted-foreground">Tra cứu O(1) tức thì từ Redis Cache, tiết kiệm Token LLM</span>
              </div>
              <div className="border border-border bg-card rounded p-2.5 text-center">
                <span className="font-semibold text-xs text-foreground block">RAG Engine</span>
                <span className="text-[10px] text-muted-foreground">Truy xuất Vector Qdrant, Reranker NVIDIA NIM &amp; Prompt Lock</span>
              </div>
              <div className="border border-border bg-card rounded p-2.5 text-center">
                <span className="font-semibold text-xs text-foreground block">Celery Workers</span>
                <span className="text-[10px] text-muted-foreground">Tiến trình ngầm: Parse tài liệu, băm chunk &amp; số hóa vector</span>
              </div>
            </div>
          </div>

          {/* Vertical Arrow */}
          <div className="flex justify-center text-muted-foreground my-1">
            <ArrowRightLeftIcon className="w-4 h-4 rotate-90" />
          </div>

          {/* Bottom Row: Data & AI Layer */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="border border-border rounded-lg p-3 bg-muted/20 space-y-2">
              <span className="text-[10px] uppercase font-bold text-muted-foreground block text-center">Data Storage Layer</span>
              <div className="grid grid-cols-2 gap-2 text-center text-xs">
                <div className="border border-border bg-card p-2 rounded">
                  <span className="font-semibold text-foreground block text-[11px]">PostgreSQL</span>
                  <span className="text-[9px] text-muted-foreground">Tenants, API Keys, Audit Logs, FAQS</span>
                </div>
                <div className="border border-border bg-card p-2 rounded">
                  <span className="font-semibold text-foreground block text-[11px]">Qdrant (Vector DB)</span>
                  <span className="text-[9px] text-muted-foreground">Chỉ mục Vector tài liệu băm nhỏ</span>
                </div>
              </div>
            </div>

            <div className="border border-border rounded-lg p-3 bg-muted/20 space-y-2">
              <span className="text-[10px] uppercase font-bold text-muted-foreground block text-center">AI Model Provider Layer</span>
              <div className="grid grid-cols-2 gap-2 text-center text-xs">
                <div className="border border-border bg-card p-2 rounded">
                  <span className="font-semibold text-foreground block text-[11px]">LLM &amp; Reranker</span>
                  <span className="text-[9px] text-muted-foreground">9Router LLM, NVIDIA NIM Reranker</span>
                </div>
                <div className="border border-border bg-card p-2 rounded">
                  <span className="font-semibold text-foreground block text-[11px]">Docker Model Runner</span>
                  <span className="text-[9px] text-muted-foreground">Embedding local &amp; Fallback engine</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── CHI TIẾT CÁC QUY TRÌNH HỆ THỐNG ── */}
      <div className="space-y-3">

        {/* 1. PIPELINE INGESTION */}
        <Accordion multiple className="border border-border rounded-xl shadow-sm bg-card">
          <AccordionItem value="ingestion-pipeline">
            <AccordionTrigger className="px-5 hover:no-underline font-semibold text-foreground text-sm">
              <div className="flex items-center gap-3">
                <WorkflowIcon className="w-4 h-4 text-primary shrink-0" />
                1. Quy trình nạp &amp; Xử lý tri thức tài liệu (Data Ingestion Pipeline)
              </div>
            </AccordionTrigger>
            <AccordionContent className="px-5 pb-5 text-muted-foreground text-xs leading-relaxed space-y-4">
              <p>
                Khi tài liệu (PDF, DOCX, TXT, Markdown) được upload, Celery Worker sẽ tự động xử lý tiến trình qua 4 bước:
              </p>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
                <div className="space-y-1 border border-border p-3 rounded-lg bg-muted/10">
                  <h4 className="font-bold text-foreground text-[11px] flex items-center gap-1.5">
                    <span className="w-4 h-4 rounded bg-primary text-primary-foreground text-[10px] font-bold flex items-center justify-center">1</span>
                    Trích xuất văn bản thô (Parsing)
                  </h4>
                  <p>
                    Lọc bỏ hình ảnh trang trí, định dạng phông chữ màu mè để thu về văn bản thô (Raw Text) thuần túy nhất.
                  </p>
                </div>

                <div className="space-y-1 border border-border p-3 rounded-lg bg-muted/10">
                  <h4 className="font-bold text-foreground text-[11px] flex items-center gap-1.5">
                    <span className="w-4 h-4 rounded bg-primary text-primary-foreground text-[10px] font-bold flex items-center justify-center">2</span>
                    Băm nhỏ ngữ nghĩa (Chunking)
                  </h4>
                  <p>
                    Tài liệu được chia thành các đoạn văn bản (chunk) chuẩn hóa từ 500-1000 từ để AI định vị thông tin chính xác.
                  </p>
                </div>

                <div className="space-y-1 border border-border p-3 rounded-lg bg-muted/10">
                  <h4 className="font-bold text-foreground text-[11px] flex items-center gap-1.5">
                    <span className="w-4 h-4 rounded bg-primary text-primary-foreground text-[10px] font-bold flex items-center justify-center">3</span>
                    Số hóa vector (Embedding Generation)
                  </h4>
                  <p>
                    Mỗi đoạn văn bản băm nhỏ được đẩy qua Embedding Model (Docker Model Runner local) chuyển thành tọa độ số học đa chiều.
                  </p>
                </div>

                <div className="space-y-1 border border-border p-3 rounded-lg bg-muted/10">
                  <h4 className="font-bold text-foreground text-[11px] flex items-center gap-1.5">
                    <span className="w-4 h-4 rounded bg-primary text-primary-foreground text-[10px] font-bold flex items-center justify-center">4</span>
                    Lập chỉ mục Vector (Qdrant Indexing)
                  </h4>
                  <p>
                    Vector cùng văn bản thô gốc và metadata phân quyền được lưu vào Qdrant Vector DB sẵn sàng phục vụ tra cứu siêu tốc.
                  </p>
                </div>
              </div>
            </AccordionContent>
          </AccordionItem>
        </Accordion>

        {/* 2. CHAT RETRIEVAL & EMPTY CONTEXT GUARDRAIL */}
        <Accordion multiple className="border border-border rounded-xl shadow-sm bg-card">
          <AccordionItem value="chat-pipeline">
            <AccordionTrigger className="px-5 hover:no-underline font-semibold text-foreground text-sm">
              <div className="flex items-center gap-3">
                <BrainCircuitIcon className="w-4 h-4 text-primary shrink-0" />
                2. Luồng xử lý câu hỏi &amp; Khóa an toàn AI (Chat Query &amp; Guardrail)
              </div>
            </AccordionTrigger>
            <AccordionContent className="px-5 pb-5 text-muted-foreground text-xs leading-relaxed space-y-4">
              <div className="space-y-3 pt-1">
                <div className="border-l-2 border-primary pl-3.5 space-y-1">
                  <h4 className="font-bold text-foreground text-xs">Bước 1: Tra cứu Redis Cache O(1)</h4>
                  <p>Hệ thống chuẩn hóa câu hỏi và kiểm tra xem câu hỏi này đã nằm trong Exact Cache hoặc FAQ Cache chưa. Nếu trúng Cache, phản hồi được trả về tức thì (0ms) mà không tốn Token LLM.</p>
                </div>

                <div className="border-l-2 border-primary pl-3.5 space-y-1">
                  <h4 className="font-bold text-foreground text-xs">Bước 2: Tìm kiếm tương đồng Vector &amp; Reranking</h4>
                  <p>Số hóa câu hỏi và so quét trong Qdrant theo đúng <code>tenant_id</code> được phân quyền. Các đoạn văn bản tìm được sẽ qua bộ lọc Reranker (NVIDIA NIM) để chấm điểm khắt khe.</p>
                </div>

                <div className="border-l-2 border-primary pl-3.5 space-y-1">
                  <h4 className="font-bold text-foreground text-xs">Bước 3: Khóa an toàn AI khi rỗng tài liệu (Strict Empty Context Guardrail)</h4>
                  <p>Nếu Tenant chưa được gán quyền tài liệu hoặc tìm kiếm rỗng, hệ thống khóa prompt bắt buộc AI trả lời câu chuẩn mực: <em>"Xin lỗi, hiện tại hệ thống chưa tìm thấy dữ liệu hoặc tài liệu chưa được phân quyền truy cập cho Tenant..."</em>. AI tuyệt đối <strong>KHÔNG DÙNG kiến thức chung bên ngoài hay tự suy đoán</strong>.</p>
                </div>
              </div>
            </AccordionContent>
          </AccordionItem>
        </Accordion>

        {/* 3. AUDIT CONVERSATIONS & FAQ PROMOTION */}
        <Accordion multiple className="border border-border rounded-xl shadow-sm bg-card">
          <AccordionItem value="faq-promotion">
            <AccordionTrigger className="px-5 hover:no-underline font-semibold text-foreground text-sm">
              <div className="flex items-center gap-3">
                <SparklesIcon className="w-4 h-4 text-primary shrink-0" />
                3. Nhật ký Hỏi đáp (Audit) &amp; Biến phản hồi AI thành FAQ
              </div>
            </AccordionTrigger>
            <AccordionContent className="px-5 pb-5 text-muted-foreground text-xs leading-relaxed space-y-3">
              <p>
                Trang <strong>Nhật ký Hỏi &amp; Đáp (Admin Audit Dashboard)</strong> tại <code>/admin/conversations</code> cho phép Admin:
              </p>
              <ul className="list-disc pl-5 space-y-1.5">
                <li>Xem lại toàn bộ lịch sử hỏi đáp thực tế phân loại theo Tên công ty (Tenant Name).</li>
                <li>Lọc hội thoại theo từng Công ty/Tenant cụ thể.</li>
                <li>Giám sát chi tiết Model AI, độ trễ ms, số Token tiêu tốn và dẫn chứng trích dẫn (Citations).</li>
                <li>Nút <strong>Sparkles Tạo FAQ từ AI</strong>: Cho phép chuyển câu trả lời hay của AI thành FAQ chuẩn hóa áp dụng cho 1 hoặc nhiều Công ty đồng thời qua lưới chọn Multi-tenant.</li>
              </ul>
            </AccordionContent>
          </AccordionItem>
        </Accordion>

        {/* 4. HARD DELETION RULES */}
        <Accordion multiple className="border border-border rounded-xl shadow-sm bg-card">
          <AccordionItem value="delete-rules">
            <AccordionTrigger className="px-5 hover:no-underline font-semibold text-foreground text-sm">
              <div className="flex items-center gap-3">
                <ShieldAlertIcon className="w-4 h-4 text-primary shrink-0" />
                4. Thứ tự xóa dữ liệu triệt để (Strict Hard-Delete Order)
              </div>
            </AccordionTrigger>
            <AccordionContent className="px-5 pb-5 text-muted-foreground text-xs leading-relaxed space-y-2">
              <p>
                Để bảo đảm toàn vẹn dữ liệu và bảo mật, hệ thống thực thi xóa triệt để (Hard-Delete) bắt buộc theo đúng thứ tự:
              </p>
              <div className="flex flex-col md:flex-row gap-2 justify-center items-center py-2">
                <div className="border border-border bg-muted/30 rounded p-2 text-center text-[10px] w-full md:w-auto font-medium">1. Xóa Vector trong Qdrant</div>
                <ArrowRightLeftIcon className="w-3 h-3 text-muted-foreground rotate-90 md:rotate-0" />
                <div className="border border-border bg-muted/30 rounded p-2 text-center text-[10px] w-full md:w-auto font-medium">2. Xóa các Sections trong DB</div>
                <ArrowRightLeftIcon className="w-3 h-3 text-muted-foreground rotate-90 md:rotate-0" />
                <div className="border border-border bg-muted/30 rounded p-2 text-center text-[10px] w-full md:w-auto font-medium">3. Xóa tệp nguồn Storage</div>
                <ArrowRightLeftIcon className="w-3 h-3 text-muted-foreground rotate-90 md:rotate-0" />
                <div className="border border-border bg-muted/30 rounded p-2 text-center text-[10px] w-full md:w-auto font-medium">4. Xóa dòng DB Document</div>
              </div>
              <p>Quy trình này đảm bảo triệt tiêu hoàn toàn vector mồ côi (orphaned vectors) trên Vector DB.</p>
            </AccordionContent>
          </AccordionItem>
        </Accordion>

      </div>
    </div>
  );
}
