"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Sheet, SheetContent, SheetFooter, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Field, FieldContent, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Plus, Power, TestTube, Key, KeyRound, Trash2, Cpu } from "lucide-react";
import { settingsApi, ApiError } from "@/lib/api-client";
import { AIProviderCreateSchema, AIProviderUpdateSchema, ProviderApiKeyCreateRequestSchema } from "@/lib/schemas";
import { toast } from "sonner";
import type { AIProvider, AIProviderCreate, AIProviderUpdate, ApiKeyItem } from "@/types/api";

const TAB_LABELS: Record<string, string> = {
  embedding: "Embedding",
  reranker: "Reranker",
  llm: "LLM",
  parser: "Parser Engine",
};

const PROVIDER_COLORS: Record<string, string> = {
  dmr: "bg-sky-500/15 text-sky-600 dark:text-sky-400",
  nvidia: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400",
  openai: "bg-green-500/15 text-green-600 dark:text-green-400",
  openrouter: "bg-amber-500/15 text-amber-600 dark:text-amber-400",
  "9router": "bg-violet-500/15 text-violet-600 dark:text-violet-400",
  deepseek: "bg-teal-500/15 text-teal-600 dark:text-teal-400",
  cohere: "bg-blue-500/15 text-blue-600 dark:text-blue-400",
  gemini: "bg-rose-500/15 text-rose-600 dark:text-rose-400",
  fpt: "bg-red-500/15 text-red-600 dark:text-red-400",
  llamaparse: "bg-fuchsia-500/15 text-fuchsia-600 dark:text-fuchsia-400",
  docling: "bg-indigo-500/15 text-indigo-600 dark:text-indigo-400",
};

const PROVIDER_LETTERS: Record<string, string> = {
  dmr: "DM",
  nvidia: "NV",
  openai: "OA",
  openrouter: "OR",
  "9router": "9R",
  deepseek: "DS",
  cohere: "CH",
  gemini: "GM",
  fpt: "FPT",
  llamaparse: "LP",
  docling: "DL",
};

function ProviderIcon({ providerName }: { providerName: string }) {
  const colorClass = PROVIDER_COLORS[providerName] || "bg-muted text-muted-foreground";
  const letter = PROVIDER_LETTERS[providerName] || providerName.slice(0, 2).toUpperCase();
  return (
    <div className={`size-9 shrink-0 rounded-lg flex items-center justify-center text-xs font-bold ${colorClass}`}>
      {letter}
    </div>
  );
}

export function ProviderPage({ serviceType }: { serviceType: "embedding" | "reranker" | "llm" | "parser" }) {
  const tab = serviceType;

  const [providers, setProviders] = useState<AIProvider[]>([]);
  const [loading, setLoading] = useState(true);
  const [addDialog, setAddDialog] = useState(false);
  const [editDialog, setEditDialog] = useState<AIProvider | null>(null);
  const [keys, setKeys] = useState<ApiKeyItem[]>([]);
  const [newKeyValue, setNewKeyValue] = useState("");

  const [formData, setFormData] = useState<AIProviderCreate>({
    service_type: tab,
    provider_name: "",
    display_name: "",
    url: "",
    model: "",
    api_key: "",
  });

  const loadProviders = async () => {
    try {
      const data = await settingsApi.listProviders(tab);
      setProviders(data);
    } catch {
      toast.error("Không thể tải danh sách providers");
    }
  };

  useEffect(() => {
    setLoading(true);
    loadProviders().finally(() => setLoading(false));
  }, [tab]);

  const resetForm = () => {
    setFormData({ service_type: tab, provider_name: "", display_name: "", url: "", model: "", api_key: "" });
  };

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    const data: AIProviderCreate = {
      ...formData,
      provider_name: formData.provider_name || formData.display_name.toLowerCase().replace(/[^a-z0-9]/g, "_"),
    };

    const parsedData = AIProviderCreateSchema.safeParse(data);
    if (!parsedData.success) {
      toast.error("Thông tin provider không hợp lệ");
      return;
    }

    try {
      await settingsApi.createProvider(parsedData.data);
      toast.success("Đã thêm provider");
      setAddDialog(false);
      resetForm();
      loadProviders();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.detail : "Thêm thất bại");
    }
  };

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editDialog) return;
    const data: AIProviderUpdate = {};
    const f = (e.target as HTMLFormElement).elements as unknown as Record<string, HTMLInputElement>;
    if (f["edit-url"]) data.url = f["edit-url"].value;
    if (f["edit-model"]) data.model = f["edit-model"].value;
    if (f["edit-api_key"] && f["edit-api_key"].value.trim()) data.api_key = f["edit-api_key"].value.trim();

    const config: Record<string, unknown> = { ...(editDialog.config || {}) };
    if (f["edit-max_sequence_length"]) {
      const v = f["edit-max_sequence_length"].value.trim();
      if (v) {
        const num = parseInt(v, 10);
        if (!isNaN(num) && num > 0) config.max_sequence_length = num;
      } else {
        delete config.max_sequence_length;
      }
    }
    if (f["edit-sparse"]) {
      const v = f["edit-sparse"].value;
      if (v && v !== "auto") config.sparse = v;
      else delete config.sparse;
    }
    if (f["edit-reasoning"]) {
      const v = f["edit-reasoning"].value;
      if (v && v !== "none") config.reasoning_effort = v;
      else delete config.reasoning_effort;
    }

    if (f["edit-thinking"]) {
      const v = f["edit-thinking"].value;
      if (v && v !== "none") config.thinking = { type: v };
      else delete config.thinking;
    }
    if (f["edit-custom-json"] && f["edit-custom-json"].value.trim()) {
      try {
        const customObj = JSON.parse(f["edit-custom-json"].value.trim());
        Object.assign(config, customObj);
      } catch {
        toast.error("JSON cấu hình nâng cao không hợp lệ");
        return;
      }
    }
    data.config = config;

    const parsedData = AIProviderUpdateSchema.safeParse(data);
    if (!parsedData.success) {
      toast.error("Dữ liệu cập nhật provider không hợp lệ");
      return;
    }

    try {
      await settingsApi.updateProvider(editDialog.id, parsedData.data);
      toast.success("Đã cập nhật");
      setEditDialog(null);
      loadProviders();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.detail : "Cập nhật thất bại");
    }
  };

  const handleToggleActive = async (p: AIProvider) => {
    try {
      if (p.is_active) {
        await settingsApi.deactivateProvider(p.id);
        toast.success(`Đã tắt ${p.display_name}`);
      } else {
        await settingsApi.activateProvider(p.id);
        toast.success(`Đã kích hoạt ${p.display_name}`);
      }
      loadProviders();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.detail : "Thao tác thất bại");
    }
  };

  const handleTest = async (p: AIProvider) => {
    try {
      const res = await settingsApi.testProvider(p.id);
      toast[res.success ? "success" : "error"](res.message);
      loadProviders();
    } catch {
      toast.error("Test connection failed");
    }
  };

  const handleDelete = async (p: AIProvider) => {
    if (p.is_builtin) {
      toast.error("Không thể xóa provider mặc định");
      return;
    }
    try {
      await settingsApi.deleteProvider(p.id);
      toast.success(`Đã xóa ${p.display_name}`);
      loadProviders();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.detail : "Xóa thất bại");
    }
  };

  const openEdit = async (p: AIProvider) => {
    setEditDialog(p);
    try {
      const data = await settingsApi.listKeys(p.id);
      setKeys(data);
    } catch {
      setKeys([]);
    }
  };

  const addKey = async () => {
    if (!editDialog || !newKeyValue.trim()) return;

    const parsedPayload = ProviderApiKeyCreateRequestSchema.safeParse({ key_value: newKeyValue.trim() });
    if (!parsedPayload.success) {
      toast.error("API key không hợp lệ");
      return;
    }

    try {
      await settingsApi.addKey(editDialog.id, parsedPayload.data.key_value);
      setNewKeyValue("");
      toast.success("Đã thêm API key");
      const data = await settingsApi.listKeys(editDialog.id);
      setKeys(data);
      loadProviders();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.detail : "Thêm key thất bại");
    }
  };

  const deleteKey = async (k: ApiKeyItem) => {
    if (!editDialog) return;
    try {
      await settingsApi.deleteKey(editDialog.id, k.id);
      setKeys((prev) => prev.filter((x) => x.id !== k.id));
      toast.success("Đã xóa key");
      loadProviders();
    } catch {
      toast.error("Xóa key thất bại");
    }
  };

  const list = providers.filter((p) => p.service_type === tab);

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">{TAB_LABELS[tab]}</h1>
        <Button className="gap-2" onClick={() => { setFormData({ service_type: tab, provider_name: "", display_name: "", url: "", model: "", api_key: "" }); setAddDialog(true); }}>
          <Plus className="h-4 w-4" /> Thêm provider
        </Button>
      </div>

      {loading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <Card key={i}>
              <div className="flex items-center gap-3 p-4">
                <div className="size-9 rounded-lg bg-muted animate-pulse" />
                <div className="flex-1 space-y-2">
                  <div className="h-4 w-24 rounded bg-muted animate-pulse" />
                  <div className="h-3 w-32 rounded bg-muted animate-pulse" />
                </div>
              </div>
            </Card>
          ))}
        </div>
      ) : list.length === 0 ? (
        <div className="flex flex-col items-center gap-2 py-16 text-muted-foreground">
          <Cpu className="h-10 w-10" />
          <p className="text-sm">Chưa có provider nào</p>
          <p className="text-xs">Thêm provider mới để bắt đầu</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {list.map((p) => {
            const hasKey = p.has_key || (p.key_count !== undefined && p.key_count > 0);
            return (
              <Card
                key={p.id}
                className={`transition-all duration-200 cursor-pointer ${
                  p.is_active
                    ? "ring-2 ring-emerald-500/60 border-emerald-500/50 bg-emerald-500/5 hover:bg-emerald-500/10 shadow-md"
                    : hasKey
                    ? "border-blue-500/30 bg-blue-500/5 hover:bg-blue-500/10 opacity-95"
                    : "opacity-60 hover:opacity-100 hover:bg-muted/30"
                }`}
                onClick={() => openEdit(p)}
              >
                <div className="flex items-center justify-between p-4">
                  <div className="flex items-center gap-3 min-w-0">
                    <ProviderIcon providerName={p.provider_name} />
                    <div className="min-w-0">
                      <h3 className="font-semibold truncate text-sm">{p.display_name}</h3>
                      <p className="text-xs text-muted-foreground truncate mt-0.5">{p.provider_name}</p>

                      <div className="flex flex-wrap items-center gap-1.5 mt-2">
                        {p.is_builtin && <Badge variant="outline" className="text-[10px] h-4 shrink-0">Mặc định</Badge>}
                        {p.is_active && <Badge className="text-[10px] h-4 shrink-0 bg-emerald-600 hover:bg-emerald-700">Đang dùng</Badge>}
                        <Badge
                          variant="outline"
                          className={`text-[10px] h-4 px-1.5 shrink-0 inline-flex items-center gap-1 font-mono ${
                            hasKey
                              ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400 font-semibold"
                              : "bg-muted/40 text-muted-foreground border-border/50"
                          }`}
                          title={`Số lượng API Key: ${p.key_count || 0}`}
                        >
                          <Key className="w-3 h-3" /> {p.key_count || 0}
                        </Badge>
                        {p.last_test_status === "failed" && (
                          <Badge variant="destructive" className="text-[10px] h-4 shrink-0">Lỗi</Badge>
                        )}
                        {p.last_test_status === "success" && (
                          <Badge variant="secondary" className="text-[10px] h-4 shrink-0">Đã test</Badge>
                        )}
                      </div>

                      {p.last_error && (
                        <p className="text-[10px] text-destructive truncate mt-1" title={p.last_error}>{p.last_error}</p>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-1 shrink-0" onClick={(e) => e.stopPropagation()}>
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      title={p.is_active ? "Tắt provider" : "Kích hoạt provider"}
                      onClick={() => handleToggleActive(p)}
                    >
                      <Power className={`h-3.5 w-3.5 ${p.is_active ? "text-emerald-500 font-bold" : "text-muted-foreground hover:text-primary"}`} />
                    </Button>
                    <Button variant="ghost" size="icon-sm" title="Kiểm tra" onClick={() => handleTest(p)}>
                      <TestTube className="h-3.5 w-3.5" />
                    </Button>
                    {!p.is_builtin && (
                      <Button variant="ghost" size="icon-sm" title="Xóa" onClick={() => handleDelete(p)}>
                        <Trash2 className="h-3.5 w-3.5 text-destructive" />
                      </Button>
                    )}
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {/* ── Add Sheet ── */}
      <Sheet open={addDialog} onOpenChange={setAddDialog}>
        <SheetContent className="w-[90vw] sm:max-w-xl overflow-y-auto" side="right">
          <SheetHeader>
            <SheetTitle>Thêm provider — {TAB_LABELS[tab]}</SheetTitle>
          </SheetHeader>
          <form id="add-form" onSubmit={handleAdd}>
            {tab === "llm" && (
              <div className="mb-4 rounded-xl border bg-muted/30 p-3">
                <span className="text-xs font-semibold text-muted-foreground block mb-2">⚡ Chọn mẫu kết nối nhanh (Presets):</span>
                <div className="flex flex-wrap gap-2">
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    className="h-8 text-xs rounded-lg border-teal-500/30 hover:bg-teal-500/10 text-teal-600 dark:text-teal-400 font-semibold"
                    onClick={() => setFormData({
                      service_type: "llm",
                      provider_name: "deepseek",
                      display_name: "DeepSeek Official",
                      url: "https://api.deepseek.com/v1",
                      model: "deepseek-v4-flash",
                      api_key: "",
                    })}
                  >
                    🐳 DeepSeek Official
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    className="h-8 text-xs rounded-lg border-red-500/30 hover:bg-red-500/10 text-red-600 dark:text-red-400 font-semibold"
                    onClick={() => setFormData({
                      service_type: "llm",
                      provider_name: "fpt",
                      display_name: "FPT Cloud LLM",
                      url: "https://mkp-api.fptcloud.com/v1",
                      model: "gpt-oss-20b",
                      api_key: "",
                      config: {
                        top_k: 40,
                        top_p: 1,
                        presence_penalty: 0,
                        frequency_penalty: 0,
                      },
                    })}
                  >
                    🔴 FPT Cloud LLM
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    className="h-8 text-xs rounded-lg"
                    onClick={() => setFormData({
                      service_type: "llm",
                      provider_name: "openai",
                      display_name: "OpenAI Official",
                      url: "https://api.openai.com/v1",
                      model: "gpt-4o",
                      api_key: "",
                    })}
                  >
                    🟢 OpenAI Official
                  </Button>
                </div>
              </div>
            )}
            <FieldGroup>
            <Field>
              <FieldContent>
                <FieldLabel htmlFor="add-name">Tên hiển thị</FieldLabel>
                <Input id="add-name" value={formData.display_name} onChange={(e) => setFormData({ ...formData, display_name: e.target.value })} placeholder="Ví dụ: 9Router Proxy LLM" required />
                <FieldDescription>Tên gợi nhớ hiển thị trên giao diện quản trị.</FieldDescription>
              </FieldContent>
            </Field>
            <Field>
              <FieldContent>
                <FieldLabel htmlFor="add-url">URL Endpoint</FieldLabel>
                <Input id="add-url" value={formData.url} onChange={(e) => setFormData({ ...formData, url: e.target.value })} placeholder="http://ai-proxy:2908/v1" required />
                <FieldDescription>Địa chỉ URL kết nối dịch vụ API Model Proxy hoặc Inference Engine.</FieldDescription>
              </FieldContent>
            </Field>
            <Field>
              <FieldContent>
                <FieldLabel htmlFor="add-model">Model ID</FieldLabel>
                <Input id="add-model" value={formData.model} onChange={(e) => setFormData({ ...formData, model: e.target.value })} placeholder="Ví dụ: chatbot-rag, gpt-4o, qwen3-embedding" />
                <FieldDescription>Mã định danh mô hình AI chính xác theo cấu hình upstream.</FieldDescription>
              </FieldContent>
            </Field>
            <Field>
              <FieldContent>
                <FieldLabel htmlFor="add-api_key">API Key</FieldLabel>
                <Input id="add-api_key" type="password" value={formData.api_key} onChange={(e) => setFormData({ ...formData, api_key: e.target.value })} placeholder="Dán API Key bảo mật..." />
                <FieldDescription>Khóa API bảo mật của nhà cung cấp (để trống nếu sử dụng Proxy nội bộ).</FieldDescription>
              </FieldContent>
            </Field>
            </FieldGroup>
          </form>
          <SheetFooter>
            <Button type="button" variant="outline" onClick={() => setAddDialog(false)}>Hủy</Button>
            <Button type="submit" form="add-form">Thêm</Button>
          </SheetFooter>
        </SheetContent>
      </Sheet>

      {/* ── Edit Sheet ── */}
      <Sheet open={!!editDialog} onOpenChange={() => setEditDialog(null)}>
        <SheetContent className="w-[90vw] sm:max-w-xl overflow-y-auto" side="right">
          <SheetHeader>
            <SheetTitle>Sửa — {editDialog?.display_name}</SheetTitle>
          </SheetHeader>
          <form id="edit-form" key={editDialog?.id} onSubmit={handleUpdate}>
            <FieldGroup>
            <Field>
              <FieldContent>
                <FieldLabel htmlFor="edit-url">URL</FieldLabel>
                <Input id="edit-url" name="edit-url" defaultValue={editDialog?.url} required />
              </FieldContent>
            </Field>
            <Field>
              <FieldContent>
                <FieldLabel htmlFor="edit-model">Model</FieldLabel>
                <Input id="edit-model" name="edit-model" defaultValue={editDialog?.model} />
              </FieldContent>
            </Field>

            {tab === "embedding" && (
              <>
                <Field>
                  <FieldContent>
                    <FieldLabel htmlFor="edit-max_sequence_length">Max Sequence Length (Độ dài chuỗi tối đa - Tokens)</FieldLabel>
                    <Input
                      id="edit-max_sequence_length"
                      name="edit-max_sequence_length"
                      type="number"
                      defaultValue={
                        (editDialog?.config?.max_sequence_length as number) ||
                        (editDialog?.config?.context_window as number) ||
                        (editDialog?.config?.max_length as number) ||
                        2048
                      }
                      placeholder="2048"
                    />
                    <FieldDescription>
                      Giới hạn độ dài ngữ cảnh tối đa của mô hình Embedding (Ví dụ: Vietnamese Embedding Model = 2048).
                    </FieldDescription>
                  </FieldContent>
                </Field>

                <Field>
                  <FieldContent>
                    <FieldLabel htmlFor="edit-sparse">Chế độ Sparse Vectors (BM25 / Hybrid)</FieldLabel>
                    <select
                      id="edit-sparse"
                      name="edit-sparse"
                      defaultValue={(editDialog?.config?.sparse as string) || "auto"}
                      className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                    >
                      <option value="auto">Tự động phát hiện (Auto Probe)</option>
                      <option value="native">Native Sparse (Dùng sparse weights của model)</option>
                      <option value="bm25">BM25 Fallback (Dùng BM25 của Qdrant)</option>
                    </select>
                    <FieldDescription>Cấu hình cách tạo sparse vectors cho tìm kiếm Hybrid.</FieldDescription>
                  </FieldContent>
                </Field>
              </>
            )}

            {tab === "llm" && (
              <>
                <Field>
                  <FieldContent>
                    <FieldLabel htmlFor="edit-reasoning">Reasoning Effort (Mức độ suy luận)</FieldLabel>
                    <select
                      id="edit-reasoning"
                      name="edit-reasoning"
                      defaultValue={(editDialog?.config?.reasoning_effort as string) || "none"}
                      className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                    >
                      <option value="none">Mặc định (Không đặt)</option>
                      <option value="high">high (Cao)</option>
                      <option value="medium">medium (Trung bình)</option>
                      <option value="low">low (Thấp)</option>
                    </select>
                    <FieldDescription>Tham số reasoning_effort điều khiển độ sâu suy luận của LLM.</FieldDescription>
                  </FieldContent>
                </Field>

                <Field>
                  <FieldContent>
                    <FieldLabel htmlFor="edit-thinking">Chế độ Thinking Mode (extra_body)</FieldLabel>
                    <select
                      id="edit-thinking"
                      name="edit-thinking"
                      defaultValue={(editDialog?.config?.thinking as { type?: string })?.type || "none"}
                      className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                    >
                      <option value="none">Mặc định (Không đặt)</option>
                      <option value="enabled">enabled (Bật suy luận)</option>
                      <option value="disabled">disabled (Tắt suy luận)</option>
                    </select>
                    <FieldDescription>Tự động đính kèm extra_body: &#123;&quot;thinking&quot;: &#123;&quot;type&quot;: &quot;enabled&quot;&#125;&#125; cho các mô hình suy luận.</FieldDescription>
                  </FieldContent>
                </Field>
              </>
            )}

            <Field>
              <FieldContent>
                <FieldLabel htmlFor="edit-custom-json">JSON Cấu hình tùy chỉnh bổ sung (SQLite config)</FieldLabel>
                <textarea
                  id="edit-custom-json"
                  name="edit-custom-json"
                  rows={3}
                  defaultValue={
                    editDialog?.config && Object.keys(editDialog.config).length > 0
                      ? JSON.stringify(editDialog.config, null, 2)
                      : ""
                  }
                  placeholder='{"temperature": 0.7}'
                  className="w-full rounded-lg border border-input bg-background p-2.5 text-xs font-mono focus:outline-none focus:ring-2 focus:ring-ring"
                />
                <FieldDescription>Cấu hình JSON bổ sung lưu trực tiếp vào SQLite `ai_providers.config`.</FieldDescription>
              </FieldContent>
            </Field>

            </FieldGroup>
          </form>
          
          <div className="mt-6 border-t pt-6">
            <h3 className="mb-4 text-sm font-semibold">Danh sách API Key</h3>
            <FieldGroup>
              <Field orientation="horizontal">
                <FieldContent>
                  <FieldLabel htmlFor="new-provider-key">Thêm API key mới</FieldLabel>
                  <Input
                    id="new-provider-key"
                    type="password"
                    placeholder="Nhập API key mới..."
                    value={newKeyValue}
                    onChange={(e) => setNewKeyValue(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addKey())}
                    disabled={["llamaparse", "9router"].includes(editDialog?.provider_name || "") && keys.length >= 1}
                  />
                  {["llamaparse", "9router"].includes(editDialog?.provider_name || "") && keys.length >= 1 && (
                    <p className="text-[10px] text-muted-foreground mt-1">Provider này chỉ hỗ trợ tối đa 1 key.</p>
                  )}
                </FieldContent>
                <Button 
                  onClick={addKey} 
                  disabled={!newKeyValue.trim() || (["llamaparse", "9router"].includes(editDialog?.provider_name || "") && keys.length >= 1)}
                >
                  Thêm
                </Button>
              </Field>
            </FieldGroup>
            {keys.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-4">
                <Key className="mx-auto h-6 w-6 mb-1" />
                Chưa có API key
              </p>
            ) : (
              <ScrollArea className="max-h-60 mt-4">
                <div className="flex flex-col gap-2 pr-3">
                {keys.map((k) => (
                  <div key={k.id} className="flex items-center justify-between border rounded-md p-2 text-sm">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs truncate max-w-[200px]">
                        {k.key_value.slice(0, 12)}...{k.key_value.slice(-4)}
                      </span>
                      {k.failure_count > 0 && (
                        <Badge variant="destructive" className="text-xs">{k.failure_count} lỗi</Badge>
                      )}
                    </div>
                    <Button variant="ghost" size="icon" onClick={() => deleteKey(k)}>
                      <Trash2 className="h-3 w-3 text-destructive" />
                    </Button>
                  </div>
                ))}
                </div>
              </ScrollArea>
            )}
          </div>

          <SheetFooter className="mt-6">
            <Button type="button" variant="outline" onClick={() => setEditDialog(null)}>Hủy</Button>
            <Button type="submit" form="edit-form">Lưu</Button>
          </SheetFooter>
        </SheetContent>
      </Sheet>
    </div>
  );
}
