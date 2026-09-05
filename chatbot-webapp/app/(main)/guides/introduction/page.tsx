"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { 
  Building2Icon, 
  DatabaseIcon, 
  BrainCircuitIcon, 
  ShieldCheckIcon,
  MessageSquareTextIcon,
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
  CheckCircle2Icon,
  PlayIcon,
  RotateCcwIcon,
  ActivityIcon,
} from "lucide-react";

export default function IntroductionGuidePage() {
  // Live Simulator step state
  const [simStep, setSimStep] = useState<number>(0);

  const simStepsData = [
    {
      title: "1. Client Gửi Yêu cầu & Xác thực",
      desc: "Ứng dụng ERP / Widget gửi câu hỏi kèm API Key (Authorization: Bearer trg_...). FastAPI Gateway xác thực Tenant & áp dụng Wildcard CORS.",
      badge: "FastAPI Gateway",
      highlight: "gateway",
    },
    {
      title: "2. Kiểm tra Redis Cache O(1)",
      desc: "Hệ thống chuẩn hóa câu hỏi và tra cứu ngay trong Redis Cache. Nếu khớp Exact Cache hoặc FAQ Cache, kết quả trả về ngay (0ms) mà không tốn Token LLM.",
      badge: "Redis O(1) Cache",
      highlight: "cache",
    },
    {
      title: "3. Truy xuất Vector & Reranking & Guardrail",
      desc: "Số hóa câu hỏi thành Vector → Quét Qdrant theo tenant_id → Chấm điểm bằng NVIDIA NIM Reranker. Nếu rỗng tài liệu, kích hoạt Strict Empty Context Guardrail.",
      badge: "Qdrant + NVIDIA Reranker",
      highlight: "rag",
    },
    {
      title: "4. LLM Streaming & Audit Logging",
      desc: "LLM (9Router) sinh câu trả lời theo luồng Stream (SSE). Kết quả được ghi lại vào Nhật ký Hỏi & Đáp (Admin Audit Dashboard) để Admin theo dõi.",
      badge: "9Router + Audit Log",
      highlight: "llm",
    },
  ];

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

      {/* ── BẢN ĐỒ KIẾN TRÚC HỆ THỐNG VÀ MÔ PHỎNG TRỰC QUAN (INTERACTIVE TABS) ── */}
      <section className="border border-border rounded-xl p-6 bg-card space-y-6 shadow-xs">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="space-y-1">
            <h2 className="text-lg font-bold text-foreground flex items-center gap-2">
              <NetworkIcon className="w-5 h-5 text-primary" />
              Sơ đồ Kiến trúc &amp; Luồng Dữ liệu Trực quan
            </h2>
            <p className="text-xs text-muted-foreground">
              Khám phá sơ đồ tổng quan hoặc chạy Mô phỏng luồng RAG tương tác trực tiếp.
            </p>
          </div>
        </div>

        <Tabs defaultValue="architecture" className="w-full">
          <TabsList className="grid w-full grid-cols-2 max-w-md">
            <TabsTrigger value="architecture" className="text-xs font-semibold">
              <LayersIcon className="w-3.5 h-3.5 mr-1.5" /> Sơ đồ Kiến trúc 4 Tầng
            </TabsTrigger>
            <TabsTrigger value="simulator" className="text-xs font-semibold">
              <ActivityIcon className="w-3.5 h-3.5 mr-1.5" /> Mô phỏng Luồng RAG (Live)
            </TabsTrigger>
          </TabsList>

          {/* TAB 1: SƠ ĐỒ KIẾN TRÚC 4 TẦNG TRỰC QUAN */}
          <TabsContent value="architecture" className="pt-4 space-y-4">
            <div className="flex flex-col gap-3">
              {/* Tầng 1: Client & Admin Layer */}
              <div className="border border-border rounded-xl p-4 bg-muted/20 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-primary flex items-center gap-1.5">
                    <Building2Icon className="w-3.5 h-3.5" /> Tầng 1: Client &amp; Control Plane
                  </span>
                  <Badge variant="outline" className="text-[10px]">Headless Integration</Badge>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div className="border border-border bg-card p-3 rounded-lg flex items-start gap-3">
                    <div className="p-2 rounded-md bg-primary/10 text-primary shrink-0">
                      <MessageSquareTextIcon className="w-4 h-4" />
                    </div>
                    <div>
                      <h4 className="font-semibold text-xs text-foreground">Phần mềm Doanh nghiệp (ERP / CRM)</h4>
                      <p className="text-[11px] text-muted-foreground mt-0.5">Nhúng Chatbot Widget hoặc REST API</p>
                    </div>
                  </div>

                  <div className="border border-border bg-card p-3 rounded-lg flex items-start gap-3">
                    <div className="p-2 rounded-md bg-primary/10 text-primary shrink-0">
                      <ShieldCheckIcon className="w-4 h-4" />
                    </div>
                    <div>
                      <h4 className="font-semibold text-xs text-foreground">Webapp Admin Control Plane</h4>
                      <p className="text-[11px] text-muted-foreground mt-0.5">Quản lý Tenants, Tài liệu, Audit AI &amp; FAQ</p>
                    </div>
                  </div>
                </div>
              </div>

              {/* Arrow Down */}
              <div className="flex justify-center text-muted-foreground">
                <ArrowRightLeftIcon className="w-4 h-4 rotate-90" />
              </div>

              {/* Tầng 2: FastAPI Gateway & Cache */}
              <div className="border border-border rounded-xl p-4 bg-muted/20 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-primary flex items-center gap-1.5">
                    <ServerIcon className="w-3.5 h-3.5" /> Tầng 2: API Gateway &amp; High-Speed Cache
                  </span>
                  <Badge variant="outline" className="text-[10px]">FastAPI + Redis</Badge>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-2.5">
                  <div className="border border-border bg-card p-3 rounded-lg text-center">
                    <KeyIcon className="w-4 h-4 text-primary mx-auto mb-1" />
                    <h5 className="font-semibold text-xs text-foreground">Tenant Auth &amp; CORS</h5>
                    <p className="text-[10px] text-muted-foreground mt-0.5">Xác thực Key `trg_...`, Mở Wildcard CORS `*`</p>
                  </div>

                  <div className="border border-border bg-card p-3 rounded-lg text-center">
                    <ZapIcon className="w-4 h-4 text-amber-500 mx-auto mb-1" />
                    <h5 className="font-semibold text-xs text-foreground">Exact &amp; FAQ Cache O(1)</h5>
                    <p className="text-[10px] text-muted-foreground mt-0.5">Tra cứu tức thì Redis 0ms, không tốn Token</p>
                  </div>

                  <div className="border border-border bg-card p-3 rounded-lg text-center">
                    <WorkflowIcon className="w-4 h-4 text-primary mx-auto mb-1" />
                    <h5 className="font-semibold text-xs text-foreground">Celery Worker Pool</h5>
                    <p className="text-[10px] text-muted-foreground mt-0.5">Tiến trình ngầm băm nhỏ &amp; số hóa vector</p>
                  </div>
                </div>
              </div>

              {/* Arrow Down */}
              <div className="flex justify-center text-muted-foreground">
                <ArrowRightLeftIcon className="w-4 h-4 rotate-90" />
              </div>

              {/* Tầng 3 & 4: Storage & AI Providers */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div className="border border-border rounded-xl p-4 bg-card space-y-2">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-primary flex items-center gap-1.5">
                    <DatabaseIcon className="w-3.5 h-3.5" /> Tầng 3: Data Storage
                  </span>
                  <div className="grid grid-cols-2 gap-2 text-center text-xs">
                    <div className="border border-border bg-muted/20 p-2.5 rounded-lg">
                      <span className="font-semibold text-foreground block text-[11px]">PostgreSQL</span>
                      <span className="text-[10px] text-muted-foreground">Tenants, Keys, FAQs, Logs</span>
                    </div>
                    <div className="border border-border bg-muted/20 p-2.5 rounded-lg">
                      <span className="font-semibold text-foreground block text-[11px]">Qdrant Vector DB</span>
                      <span className="text-[10px] text-muted-foreground">Chỉ mục Vector tài liệu băm</span>
                    </div>
                  </div>
                </div>

                <div className="border border-border rounded-xl p-4 bg-card space-y-2">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-primary flex items-center gap-1.5">
                    <CpuIcon className="w-3.5 h-3.5" /> Tầng 4: AI Model Provider &amp; Fallback
                  </span>
                  <div className="grid grid-cols-2 gap-2 text-center text-xs">
                    <div className="border border-border bg-muted/20 p-2.5 rounded-lg">
                      <span className="font-semibold text-foreground block text-[11px]">Cloud AI &amp; NIM</span>
                      <span className="text-[10px] text-muted-foreground">9Router LLM, NVIDIA NIM Reranker</span>
                    </div>
                    <div className="border border-border bg-muted/20 p-2.5 rounded-lg">
                      <span className="font-semibold text-foreground block text-[11px]">Docker Model Runner</span>
                      <span className="text-[10px] text-muted-foreground">Embedding local &amp; Fallback engine</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </TabsContent>

          {/* TAB 2: MÔ PHỎNG LUỒNG DỮ LIỆU TƯƠNG TÁC (LIVE SIMULATOR) */}
          <TabsContent value="simulator" className="pt-4 space-y-4">
            <div className="border border-border/80 rounded-xl p-5 bg-muted/10 space-y-4">
              <div className="flex items-center justify-between flex-wrap gap-2">
                <div>
                  <h3 className="font-bold text-sm text-foreground flex items-center gap-2">
                    <ActivityIcon className="w-4 h-4 text-primary animate-pulse" />
                    Mô phỏng Tiến trình Xử lý Yêu cầu Chat RAG
                  </h3>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Bấm các nút điều khiển bên dưới để quan sát luồng dữ liệu di chuyển thực tế qua từng thành phần hệ thống.
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-8 text-xs gap-1"
                    onClick={() => setSimStep(0)}
                  >
                    <RotateCcwIcon className="w-3.5 h-3.5" /> Reset
                  </Button>

                  <Button
                    size="sm"
                    className="h-8 text-xs gap-1 bg-primary text-primary-foreground"
                    onClick={() => setSimStep((prev) => (prev >= 4 ? 1 : prev + 1))}
                  >
                    <PlayIcon className="w-3.5 h-3.5" /> {simStep === 0 ? "Bắt đầu mô phỏng" : simStep === 4 ? "Chạy lại từ đầu" : "Bước tiếp theo"}
                  </Button>
                </div>
              </div>

              {/* Timeline Progress */}
              <div className="grid grid-cols-4 gap-2 pt-2">
                {[1, 2, 3, 4].map((step) => {
                  const isActive = simStep === step;
                  const isDone = simStep > step;
                  return (
                    <div
                      key={step}
                      onClick={() => setSimStep(step)}
                      className={`p-2.5 rounded-lg border text-center cursor-pointer transition-all ${
                        isActive
                          ? "bg-primary/10 border-primary text-primary font-bold shadow-xs"
                          : isDone
                          ? "bg-card border-border/80 text-foreground font-medium"
                          : "bg-muted/30 border-border/40 text-muted-foreground opacity-60"
                      }`}
                    >
                      <div className="text-[10px] uppercase font-semibold">Bước {step}</div>
                      <div className="text-xs truncate font-semibold mt-0.5">
                        {step === 1 && "1. Gateway"}
                        {step === 2 && "2. Redis Cache"}
                        {step === 3 && "3. RAG Search"}
                        {step === 4 && "4. LLM Stream"}
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Active Step Display Box */}
              {simStep > 0 ? (
                <Card className="border-primary/30 bg-card shadow-sm">
                  <CardHeader className="p-4 pb-2">
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-sm font-bold flex items-center gap-2 text-primary">
                        <CheckCircle2Icon className="w-4 h-4" />
                        {simStepsData[simStep - 1].title}
                      </CardTitle>
                      <Badge variant="secondary" className="text-[10px] font-mono">
                        {simStepsData[simStep - 1].badge}
                      </Badge>
                    </div>
                  </CardHeader>
                  <CardContent className="p-4 pt-1 text-xs text-muted-foreground leading-relaxed">
                    {simStepsData[simStep - 1].desc}
                  </CardContent>
                </Card>
              ) : (
                <div className="p-6 text-center border border-dashed border-border rounded-xl text-xs text-muted-foreground">
                  Nhấn nút <strong>&quot;Bắt đầu mô phỏng&quot;</strong> ở góc phải để kích hoạt mô hình trực quan.
                </div>
              )}
            </div>
          </TabsContent>
        </Tabs>
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
                  <p>Nếu Tenant chưa được gán quyền tài liệu hoặc tìm kiếm rỗng, hệ thống khóa prompt bắt buộc AI trả lời câu chuẩn mực: <em>&quot;Xin lỗi, hiện tại hệ thống chưa tìm thấy dữ liệu hoặc tài liệu chưa được phân quyền truy cập cho Tenant...&quot;</em>. AI tuyệt đối <strong>KHÔNG DÙNG kiến thức chung bên ngoài hay tự suy đoán</strong>.</p>
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
