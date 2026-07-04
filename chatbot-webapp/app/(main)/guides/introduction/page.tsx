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
  Share2Icon,
  WorkflowIcon
} from "lucide-react";

export default function IntroductionGuidePage() {
  return (
    <div className="space-y-8 pb-16 max-w-4xl">
      {/* Title & Overview */}
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <h1 className="text-4xl font-extrabold tracking-tight text-foreground">Giới thiệu &amp; Kiến trúc Nền tảng</h1>
          <Badge variant="default" className="text-xs bg-primary text-primary-foreground">
            {process.env.NEXT_PUBLIC_APP_VERSION || "v1.0"}
          </Badge>
        </div>
        <p className="text-base text-muted-foreground leading-relaxed max-w-3xl">
          Chào mừng bạn đến với tài liệu kỹ thuật tổng quan của Nền tảng Hỏi đáp tài liệu tự động (RAG) đa doanh nghiệp. 
          Tài liệu này trình bày chi tiết kiến trúc hệ thống, các luồng dữ liệu cốt lõi, cơ chế cô lập và phương án tích hợp thực tế.
        </p>
      </div>

      {/* Target Audience Alert */}
      <Alert className="bg-muted/50 border-border">
        <InfoIcon className="h-5 w-5 text-primary" />
        <AlertTitle className="font-bold text-foreground">Cẩm nang vận hành dành cho BA, PM và Developers</AlertTitle>
        <AlertDescription className="text-xs leading-5 mt-1 text-muted-foreground">
          Nền tảng được thiết kế theo hướng <strong>API-First / Headless</strong>. Giao diện Webapp này đóng vai trò 
          Quản trị (Admin Dashboard), giúp bạn huấn luyện dữ liệu và cấu hình AI. Trí tuệ thực tế sẽ được nhúng thẳng 
          vào các phần mềm nghiệp vụ hiện hữu (như ERP, CRM) thông qua các endpoint API chuẩn.
        </AlertDescription>
      </Alert>

      {/* ── BẢN ĐỒ KIẾN TRÚC HỆ THỐNG (CSS DIAGRAM) ── */}
      <section className="border border-border rounded-xl p-6 bg-card space-y-6">
        <div className="space-y-1">
          <h2 className="text-lg font-bold text-foreground flex items-center gap-2">
            <NetworkIcon className="w-5 h-5 text-primary" />
            Sơ đồ kiến trúc &amp; Luồng xử lý
          </h2>
          <p className="text-xs text-muted-foreground leading-relaxed">
            Mô hình tương tác giữa Client App (ERP), Backend API Service, Cơ sở dữ liệu và các Model AI:
          </p>
        </div>

        {/* Pure CSS/HTML Architecture Flow Chart */}
        <div className="flex flex-col gap-4 pt-2">
          
          {/* Top Row: Client layer */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="border border-border rounded-lg p-3 bg-muted/20 flex flex-col items-center justify-center text-center space-y-1">
              <span className="text-[10px] uppercase font-semibold text-muted-foreground">Client Layer</span>
              <span className="font-bold text-xs text-foreground">Phần mềm Doanh nghiệp (ERP / CRM)</span>
              <p className="text-[10px] text-muted-foreground">Nhúng Chatbot Widget, gửi câu hỏi trực tiếp qua API</p>
            </div>
            <div className="border border-border rounded-lg p-3 bg-muted/20 flex flex-col items-center justify-center text-center space-y-1">
              <span className="text-[10px] uppercase font-semibold text-muted-foreground">Admin Layer</span>
              <span className="font-bold text-xs text-foreground">Webapp Dashboard (Next.js)</span>
              <p className="text-[10px] text-muted-foreground">Tenant Admin cấu hình chatbot &amp; Upload tài liệu</p>
            </div>
          </div>

          {/* Vertical Arrow */}
          <div className="flex justify-center text-muted-foreground my-1">
            <ArrowRightLeftIcon className="w-4 h-4 rotate-90" />
          </div>

          {/* Middle Row: Backend Layer */}
          <div className="border border-border rounded-lg p-4 bg-muted/10 space-y-3">
            <div className="flex justify-between items-center border-b border-border pb-2">
              <span className="text-[10px] uppercase font-bold text-muted-foreground">Backend Service Layer (FastAPI &amp; Celery)</span>
              <Badge variant="outline" className="text-[10px]">Docker Containerized</Badge>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div className="border border-border bg-card rounded p-2.5 text-center">
                <span className="font-semibold text-xs text-foreground block">FastAPI Router</span>
                <span className="text-[10px] text-muted-foreground">Xác thực API Key, kiểm tra rate limit, định tuyến request</span>
              </div>
              <div className="border border-border bg-card rounded p-2.5 text-center">
                <span className="font-semibold text-xs text-foreground block">RAG Engine</span>
                <span className="text-[10px] text-muted-foreground">Chuẩn hóa câu hỏi, gọi Qdrant, tích hợp Prompt Context</span>
              </div>
              <div className="border border-border bg-card rounded p-2.5 text-center">
                <span className="font-semibold text-xs text-foreground block">Celery Worker</span>
                <span className="text-[10px] text-muted-foreground">Chạy ngầm tác vụ: Parse PDF, băm nhỏ chunk, generate embedding</span>
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
              <span className="text-[10px] uppercase font-bold text-muted-foreground block text-center">Storage Layer</span>
              <div className="grid grid-cols-2 gap-2 text-center text-xs">
                <div className="border border-border bg-card p-2 rounded">
                  <span className="font-semibold text-foreground block text-[11px]">PostgreSQL</span>
                  <span className="text-[9px] text-muted-foreground">Lưu cấu hình Tenants, Keys, Audit Logs</span>
                </div>
                <div className="border border-border bg-card p-2 rounded">
                  <span className="font-semibold text-foreground block text-[11px]">Qdrant (Vector DB)</span>
                  <span className="text-[9px] text-muted-foreground">Lưu trữ toạ độ vector của các đoạn tài liệu băm</span>
                </div>
              </div>
            </div>

            <div className="border border-border rounded-lg p-3 bg-muted/20 space-y-2">
              <span className="text-[10px] uppercase font-bold text-muted-foreground block text-center">AI Model Layer (9Router &amp; Local)</span>
              <div className="grid grid-cols-2 gap-2 text-center text-xs">
                <div className="border border-border bg-card p-2 rounded">
                  <span className="font-semibold text-foreground block text-[11px]">Cloud AI Model</span>
                  <span className="text-[9px] text-muted-foreground">NVIDIA NIM (Reranker), OpenAI API (LLM)</span>
                </div>
                <div className="border border-border bg-card p-2 rounded">
                  <span className="font-semibold text-foreground block text-[11px]">Docker Runner (DMR)</span>
                  <span className="text-[9px] text-muted-foreground">Local Embedding &amp; Reranker Fallback</span>
                </div>
              </div>
            </div>
          </div>

        </div>
      </section>

      {/* ── CHI TIẾT CÁC ACCORDION (PRODUCT DOCS STYLE) ── */}
      <div className="space-y-3">

        {/* 1. PIPELINE INGESTION */}
        <Accordion multiple className="border border-border rounded-xl shadow-sm bg-card">
          <AccordionItem value="ingestion-pipeline">
            <AccordionTrigger className="px-5 hover:no-underline font-semibold text-foreground text-sm">
              <div className="flex items-center gap-3">
                <WorkflowIcon className="w-4 h-4 text-primary shrink-0" />
                Quy trình nạp tài liệu (Data Ingestion Pipeline)
              </div>
            </AccordionTrigger>
            <AccordionContent className="px-5 pb-5 text-muted-foreground text-xs leading-relaxed space-y-4">
              <p>
                Khi một tệp tài liệu (PDF, DOCX) được upload lên từ giao diện của Tenant Admin, hệ thống không lưu trữ nó như một tệp tĩnh thông thường. Tệp sẽ trải qua một quy trình xử lý bất đồng bộ (Background Pipeline) được điều phối bởi Celery Workers:
              </p>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
                <div className="space-y-1 border border-border p-3 rounded-lg bg-muted/10">
                  <h4 className="font-bold text-foreground text-[11px] flex items-center gap-1.5">
                    <span className="w-4 h-4 rounded bg-primary text-primary-foreground text-[10px] font-bold flex items-center justify-center">1</span>
                    Phân tích văn bản thô (Parsing)
                  </h4>
                  <p>
                    Hệ thống trích xuất văn bản từ tệp nguồn. Đối với các file PDF hoặc DOCX, hệ thống sẽ lọc bỏ hình ảnh trang trí, định dạng phông chữ màu mè để thu về văn bản thô (Raw Text) thuần túy nhất.
                  </p>
                </div>

                <div className="space-y-1 border border-border p-3 rounded-lg bg-muted/10">
                  <h4 className="font-bold text-foreground text-[11px] flex items-center gap-1.5">
                    <span className="w-4 h-4 rounded bg-primary text-primary-foreground text-[10px] font-bold flex items-center justify-center">2</span>
                    Băm nhỏ ngữ nghĩa (Semantic Chunking)
                  </h4>
                  <p>
                    Văn bản dài hàng trăm trang không thể đưa toàn bộ vào prompt cho LLM vì giới hạn cửa sổ ngữ cảnh (Token limits). Hệ thống sử dụng giải thuật phân tách văn bản thông minh để chia nhỏ tài liệu thành các đoạn (chunk) từ 500 đến 1000 từ.
                  </p>
                </div>

                <div className="space-y-1 border border-border p-3 rounded-lg bg-muted/10">
                  <h4 className="font-bold text-foreground text-[11px] flex items-center gap-1.5">
                    <span className="w-4 h-4 rounded bg-primary text-primary-foreground text-[10px] font-bold flex items-center justify-center">3</span>
                    Số hóa vector (Embedding Generation)
                  </h4>
                  <p>
                    Mỗi đoạn văn bản băm nhỏ được đẩy qua Embedding Model (chạy trên local Docker Model Runner hoặc cloud API) để chuyển đổi thành tọa độ số học (Vector) gồm hàng ngàn chiều biểu thị cho ý nghĩa ngữ nghĩa của đoạn đó.
                  </p>
                </div>

                <div className="space-y-1 border border-border p-3 rounded-lg bg-muted/10">
                  <h4 className="font-bold text-foreground text-[11px] flex items-center gap-1.5">
                    <span className="w-4 h-4 rounded bg-primary text-primary-foreground text-[10px] font-bold flex items-center justify-center">4</span>
                    Lưu trữ &amp; Đánh chỉ mục (Vector Indexing)
                  </h4>
                  <p>
                    Các tọa độ vector cùng thông tin văn bản thô gốc được lưu trữ vào <strong>Qdrant Vector Database</strong>. Qdrant sẽ lập chỉ mục không gian vector này để chuẩn bị cho việc tra cứu siêu tốc sau này.
                  </p>
                </div>
              </div>
            </AccordionContent>
          </AccordionItem>
        </Accordion>

        {/* 2. CHAT RETRIEVAL PIPELINE */}
        <Accordion multiple className="border border-border rounded-xl shadow-sm bg-card">
          <AccordionItem value="chat-pipeline">
            <AccordionTrigger className="px-5 hover:no-underline font-semibold text-foreground text-sm">
              <div className="flex items-center gap-3">
                <BrainCircuitIcon className="w-4 h-4 text-primary shrink-0" />
                Luồng truy xuất &amp; Trả lời (Chat Query Pipeline)
              </div>
            </AccordionTrigger>
            <AccordionContent className="px-5 pb-5 text-muted-foreground text-xs leading-relaxed space-y-4">
              <p>
                Khi có yêu cầu gửi từ client đến endpoint <code>/v1/chat/completions</code>, hệ thống thực hiện một chuỗi các thao tác xử lý tuần tự:
              </p>

              <div className="space-y-4 pt-2">
                <div className="flex gap-3 items-start border-l-2 border-border pl-4">
                  <div className="space-y-1">
                    <h4 className="font-bold text-foreground text-xs">Bước 1: Nhận diện Tenant &amp; Chuẩn hóa câu hỏi</h4>
                    <p>
                      Mã API Key gửi lên ở header được đối soát. Hệ thống tự động xác định <code>tenant_id</code> để thu hẹp phạm vi tìm kiếm tài liệu. Câu hỏi của người dùng được chuẩn hóa và loại bỏ các từ dừng (stopwords) vô nghĩa.
                    </p>
                  </div>
                </div>

                <div className="flex gap-3 items-start border-l-2 border-border pl-4">
                  <div className="space-y-1">
                    <h4 className="font-bold text-foreground text-xs">Bước 2: Tìm kiếm tương đồng vector (Similarity Search)</h4>
                    <p>
                      Câu hỏi được số hóa thành vector bằng Embedding model tương ứng. Hệ thống so quét vector này với hàng triệu vector tài liệu của Tenant đó trong Qdrant. Các đoạn văn bản có khoảng cách cosine nhỏ nhất (ý nghĩa tương đương nhất) sẽ được lôi ra.
                    </p>
                  </div>
                </div>

                <div className="flex gap-3 items-start border-l-2 border-border pl-4">
                  <div className="space-y-1">
                    <h4 className="font-bold text-foreground text-xs">Bước 3: Tái xếp hạng (Reranking)</h4>
                    <p>
                      Để nâng cao độ chính xác, hệ thống gửi các đoạn văn bản thô cùng câu hỏi đến Reranker model (như NVIDIA NIM). Reranker sử dụng mô hình cross-encoder chấm điểm và sắp xếp lại độ liên quan cực kỳ khắt khe, chỉ giữ lại các đoạn có điểm cao vượt trội.
                    </p>
                  </div>
                </div>

                <div className="flex gap-3 items-start border-l-2 border-border pl-4">
                  <div className="space-y-1">
                    <h4 className="font-bold text-foreground text-xs">Bước 4: Tiêm ngữ cảnh &amp; Trả lời (Prompt Injection &amp; Streaming)</h4>
                    <p>
                      Các đoạn văn bản tốt nhất được đóng gói thành ngữ cảnh (Context) và tiêm trực tiếp vào System Prompt của LLM. LLM sẽ đọc và viết câu trả lời. Kết quả được stream từng dòng (Event-Stream) trả về cho client giúp tối ưu trải nghiệm và giảm thời gian chờ đợi của người dùng.
                    </p>
                  </div>
                </div>
              </div>
            </AccordionContent>
          </AccordionItem>
        </Accordion>

        {/* 3. HARD DELETION RULES */}
        <Accordion multiple className="border border-border rounded-xl shadow-sm bg-card">
          <AccordionItem value="delete-rules">
            <AccordionTrigger className="px-5 hover:no-underline font-semibold text-foreground text-sm">
              <div className="flex items-center gap-3">
                <ShieldAlertIcon className="w-4 h-4 text-primary shrink-0" />
                Quy trình Xóa dữ liệu triệt để (Hard-Delete Order)
              </div>
            </AccordionTrigger>
            <AccordionContent className="px-5 pb-5 text-muted-foreground text-xs leading-relaxed space-y-2">
              <p>
                Để bảo vệ quyền riêng tư và dọn sạch dữ liệu rác, hệ thống thực thi quy trình xóa triệt để (Hard-Delete) bắt buộc theo thứ tự nghiêm ngặt sau:
              </p>
              <div className="flex flex-col md:flex-row gap-2 justify-center items-center py-2">
                <div className="border border-border bg-muted/30 rounded p-2 text-center text-[10px] w-full md:w-auto font-medium">1. Xóa Vector trong Qdrant</div>
                <ArrowRightLeftIcon className="w-3 h-3 text-muted-foreground rotate-90 md:rotate-0" />
                <div className="border border-border bg-muted/30 rounded p-2 text-center text-[10px] w-full md:w-auto font-medium">2. Xóa các Sections trong DB</div>
                <ArrowRightLeftIcon className="w-3 h-3 text-muted-foreground rotate-90 md:rotate-0" />
                <div className="border border-border bg-muted/30 rounded p-2 text-center text-[10px] w-full md:w-auto font-medium">3. Xóa tệp nguồn trên Storage</div>
                <ArrowRightLeftIcon className="w-3 h-3 text-muted-foreground rotate-90 md:rotate-0" />
                <div className="border border-border bg-muted/30 rounded p-2 text-center text-[10px] w-full md:w-auto font-medium">4. Xóa dòng ghi DB</div>
              </div>
              <p>
                Quy trình này đảm bảo không có vector mồ côi (orphaned vectors) tồn tại lãng phí trong bộ nhớ Vector DB và tài liệu đã xoá sẽ biến mất hoàn toàn khỏi bộ nhớ AI.
              </p>
            </AccordionContent>
          </AccordionItem>
        </Accordion>

        {/* 4. FAULT TOLERANCE & FALLBACK */}
        <Accordion multiple className="border border-border rounded-xl shadow-sm bg-card">
          <AccordionItem value="fault-tolerance">
            <AccordionTrigger className="px-5 hover:no-underline font-semibold text-foreground text-sm">
              <div className="flex items-center gap-3">
                <ServerIcon className="w-4 h-4 text-primary shrink-0" />
                Cơ chế Dự phòng lõi (Auto-Fallback)
              </div>
            </AccordionTrigger>
            <AccordionContent className="px-5 pb-5 text-muted-foreground text-xs leading-relaxed space-y-3">
              <p>
                Hệ thống được thiết kế với cơ chế tự phục hồi lỗi (Fault Tolerance) tự động ở tầng API Gateway:
              </p>
              <ul className="list-disc pl-5 space-y-2">
                <li>
                  <strong className="text-foreground">Sự cố Cloud:</strong> Nếu các dịch vụ AI đám mây (như NVIDIA NIM hay OpenAI API) bị quá tải, hết hạn gói cước, hoặc gặp sự cố kết nối.
                </li>
                <li>
                  <strong className="text-foreground">Định tuyến dự phòng:</strong> Backend sẽ tự động phát hiện lỗi và chuyển tiếp request Reranker/Embedding sang <strong>Docker Model Runner (dmr)</strong> chạy cục bộ trên server nội bộ của bạn.
                </li>
                <li>
                  <strong className="text-foreground">Hiệu quả:</strong> Chatbot vẫn tiếp tục hoạt động mà không gây ra bất kỳ lỗi gián đoạn dịch vụ nào đối với các ứng dụng khách.
                </li>
              </ul>
            </AccordionContent>
          </AccordionItem>
        </Accordion>

      </div>
    </div>
  );
}
