"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Sheet, SheetContent, SheetFooter, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Field, FieldContent, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Plus, Power, TestTube, Key, Trash2, Cpu } from "lucide-react";
import { settingsApi, ApiError } from "@/lib/api-client";
import { toast } from "sonner";
import type { AIProvider, AIProviderCreate, AIProviderUpdate, ApiKeyItem } from "@/types/api";

const TAB_LABELS: Record<string, string> = {
  embedding: "Embedding",
  reranker: "Reranker",
  llm: "LLM",
};

const PROVIDER_COLORS: Record<string, string> = {
  dmr: "bg-sky-500/15 text-sky-600 dark:text-sky-400",
  nvidia: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400",
  openai: "bg-green-500/15 text-green-600 dark:text-green-400",
  openrouter: "bg-amber-500/15 text-amber-600 dark:text-amber-400",
  "9router": "bg-violet-500/15 text-violet-600 dark:text-violet-400",
  cohere: "bg-blue-500/15 text-blue-600 dark:text-blue-400",
  gemini: "bg-rose-500/15 text-rose-600 dark:text-rose-400",
};

const PROVIDER_LETTERS: Record<string, string> = {
  dmr: "DM",
  nvidia: "NV",
  openai: "OA",
  openrouter: "OR",
  "9router": "9R",
  cohere: "CH",
  gemini: "GM",
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

export function ProviderPage({ serviceType }: { serviceType: "embedding" | "reranker" | "llm" }) {
  const tab = serviceType;

  const [providers, setProviders] = useState<AIProvider[]>([]);
  const [loading, setLoading] = useState(true);
  const [addDialog, setAddDialog] = useState(false);
  const [editDialog, setEditDialog] = useState<AIProvider | null>(null);
  const [keyDialog, setKeyDialog] = useState<AIProvider | null>(null);
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

  useEffect(() => {
    settingsApi.listProviders(tab).then(setProviders).catch(() => toast.error("Không thể tải danh sách providers")).finally(() => setLoading(false));
  }, [tab]);

  const llmBuiltin = tab === "llm";

  const resetForm = () => {
    setFormData({ service_type: tab, provider_name: "", display_name: "", url: "", model: "", api_key: "" });
  };

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    const data: AIProviderCreate = {
      ...formData,
      provider_name: formData.provider_name || formData.display_name.toLowerCase().replace(/[^a-z0-9]/g, "_"),
    };
    try {
      await settingsApi.createProvider(data);
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
    try {
      await settingsApi.updateProvider(editDialog.id, data);
      toast.success("Đã cập nhật");
      setEditDialog(null);
      loadProviders();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.detail : "Cập nhật thất bại");
    }
  };

  const handleActivate = async (p: AIProvider) => {
    try {
      await settingsApi.activateProvider(p.id);
      toast.success(`Đã kích hoạt ${p.display_name}`);
      loadProviders();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.detail : "Kích hoạt thất bại");
    }
  };

  const handleTest = async (p: AIProvider) => {
    try {
      const res = await settingsApi.testProvider(p.id);
      toast[res.success ? "success" : "error"](res.message);
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

  const loadProviders = async () => {
    try {
      setLoading(true);
      const data = await settingsApi.listProviders(tab);
      setProviders(data);
    } catch {
      toast.error("Không thể tải danh sách providers");
    } finally {
      setLoading(false);
    }
  };

  const openKeys = async (p: AIProvider) => {
    setKeyDialog(p);
    try {
      const data = await settingsApi.listKeys(p.id);
      setKeys(data);
    } catch {
      setKeys([]);
    }
  };

  const addKey = async () => {
    if (!keyDialog || !newKeyValue.trim()) return;
    try {
      await settingsApi.addKey(keyDialog.id, newKeyValue.trim());
      setNewKeyValue("");
      toast.success("Đã thêm API key");
      const data = await settingsApi.listKeys(keyDialog.id);
      setKeys(data);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.detail : "Thêm key thất bại");
    }
  };

  const deleteKey = async (k: ApiKeyItem) => {
    if (!keyDialog) return;
    try {
      await settingsApi.deleteKey(keyDialog.id, k.id);
      setKeys((prev) => prev.filter((x) => x.id !== k.id));
      toast.success("Đã xóa key");
    } catch {
      toast.error("Xóa key thất bại");
    }
  };

  const list = providers.filter((p) => p.service_type === tab);

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">{TAB_LABELS[tab]}</h1>
        {!llmBuiltin && (
          <Button className="gap-2" onClick={() => { resetForm(); setAddDialog(true); }}>
            <Plus className="h-4 w-4" /> Thêm provider
          </Button>
        )}
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
          {list.map((p) => (
            <Card
              key={p.id}
              className={`${p.is_active ? "hover:bg-muted/30 cursor-pointer" : "opacity-60"} transition-colors`}
              onClick={() => setEditDialog(p)}
            >
              <div className="flex items-center justify-between p-4">
                <div className="flex items-center gap-3 min-w-0">
                  <ProviderIcon providerName={p.provider_name} />
                    <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <h3 className="font-semibold truncate">{p.display_name}</h3>
                      {p.is_builtin && <Badge variant="outline" className="text-[10px] h-4 shrink-0">Mặc định</Badge>}
                      {p.is_active && <Badge className="text-[10px] h-4 shrink-0">Đang dùng</Badge>}
                      {p.last_test_status === "failed" && (
                        <Badge variant="destructive" className="text-[10px] h-4 shrink-0">Lỗi</Badge>
                      )}
                      {p.last_test_status === "success" && (
                        <Badge variant="secondary" className="text-[10px] h-4 shrink-0">Đã test</Badge>
                      )}
                    </div>
                    <p className="text-xs text-muted-foreground truncate mt-0.5">{p.provider_name}</p>
                    {p.last_error && (
                      <p className="text-[10px] text-destructive truncate mt-0.5" title={p.last_error}>{p.last_error}</p>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-1 shrink-0" onClick={(e) => e.stopPropagation()}>
                  {!p.is_active && !llmBuiltin && (
                    <Button variant="ghost" size="icon-sm" title="Kích hoạt" onClick={() => handleActivate(p)}>
                      <Power className="h-3.5 w-3.5 text-primary" />
                    </Button>
                  )}
                  <Button variant="ghost" size="icon-sm" title="Kiểm tra" onClick={() => handleTest(p)}>
                    <TestTube className="h-3.5 w-3.5" />
                  </Button>
                  <Button variant="ghost" size="icon-sm" title="API key" onClick={() => openKeys(p)}>
                    <Key className="h-3.5 w-3.5" />
                  </Button>
                  {!p.is_builtin && (
                    <Button variant="ghost" size="icon-sm" title="Xóa" onClick={() => handleDelete(p)}>
                      <Trash2 className="h-3.5 w-3.5 text-destructive" />
                    </Button>
                  )}
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* ── Add Sheet ── */}
      <Sheet open={addDialog} onOpenChange={setAddDialog}>
        <SheetContent className="w-[90vw] sm:max-w-xl overflow-y-auto" side="right">
          <SheetHeader>
            <SheetTitle>Thêm provider — {TAB_LABELS[tab]}</SheetTitle>
          </SheetHeader>
          <form id="add-form" onSubmit={handleAdd}>
            <FieldGroup>
            <Field>
              <FieldContent>
                <FieldLabel htmlFor="add-name">Tên hiển thị</FieldLabel>
                <Input id="add-name" value={formData.display_name} onChange={(e) => setFormData({ ...formData, display_name: e.target.value })} required />
              </FieldContent>
            </Field>
            <Field>
              <FieldContent>
                <FieldLabel htmlFor="add-url">URL</FieldLabel>
                <Input id="add-url" value={formData.url} onChange={(e) => setFormData({ ...formData, url: e.target.value })} required />
              </FieldContent>
            </Field>
            <Field>
              <FieldContent>
                <FieldLabel htmlFor="add-model">Model</FieldLabel>
                <Input id="add-model" value={formData.model} onChange={(e) => setFormData({ ...formData, model: e.target.value })} />
              </FieldContent>
            </Field>
            <Field>
              <FieldContent>
                <FieldLabel htmlFor="add-api_key">API Key</FieldLabel>
                <Input id="add-api_key" type="password" value={formData.api_key} onChange={(e) => setFormData({ ...formData, api_key: e.target.value })} />
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
            <Field>
              <FieldContent>
                <FieldLabel htmlFor="edit-api_key">API key</FieldLabel>
                <Input id="edit-api_key" name="edit-api_key" type="password" defaultValue={editDialog?.api_key} placeholder="Để trống nếu muốn giữ nguyên" />
                <FieldDescription>
                  Khuyến nghị: quản lý key tại nút <strong>API key</strong>. Để trống ở đây sẽ giữ nguyên key hiện tại.
                </FieldDescription>
              </FieldContent>
            </Field>
            </FieldGroup>
          </form>
          <SheetFooter>
            <Button type="button" variant="outline" onClick={() => setEditDialog(null)}>Hủy</Button>
            <Button type="submit" form="edit-form">Lưu</Button>
          </SheetFooter>
        </SheetContent>
      </Sheet>

      {/* ── API Key Sheet ── */}
      <Sheet open={!!keyDialog} onOpenChange={() => setKeyDialog(null)}>
        <SheetContent className="w-[90vw] sm:max-w-xl overflow-y-auto" side="right">
          <SheetHeader>
            <SheetTitle>API key — {keyDialog?.display_name}</SheetTitle>
          </SheetHeader>
          <FieldGroup>
            <Field orientation="horizontal">
              <FieldContent>
                <FieldLabel htmlFor="new-provider-key">API key mới</FieldLabel>
                <Input
                  id="new-provider-key"
                  type="password"
                  placeholder="Nhập API key mới..."
                  value={newKeyValue}
                  onChange={(e) => setNewKeyValue(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addKey())}
                />
              </FieldContent>
              <Button onClick={addKey} disabled={!newKeyValue.trim()}>Thêm</Button>
            </Field>
          </FieldGroup>
          {keys.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-4">
              <Key className="mx-auto h-6 w-6 mb-1" />
              Chưa có API key
            </p>
          ) : (
            <ScrollArea className="max-h-60">
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
        </SheetContent>
      </Sheet>
    </div>
  );
}
