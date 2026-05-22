"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsTrigger } from "@/components/ui/tabs";
import { Plus, Trash2, Power, TestTube, Key, Globe, Cpu } from "lucide-react";
import { settingsApi, ApiError } from "@/lib/api-client";
import { toast } from "sonner";
import type { AIProvider, AIProviderCreate, AIProviderUpdate, ProviderTemplate, ApiKeyItem } from "@/types/api";

const TAB_KEYS = ["embedding", "reranker", "llm"] as const;
type TabKey = (typeof TAB_KEYS)[number];

const TAB_LABELS: Record<TabKey, string> = {
  embedding: "Embedding",
  reranker: "Reranker",
  llm: "LLM",
};

const PROVIDER_ICONS: Record<string, string> = {
  tei: "🖥",
  openai: "🟢",
  openrouter: "🔀",
  nvidia: "🟩",
  gemini: "🔵",
  cohere: "🟠",
  "9router": "🔌",
};

export default function ProvidersPage() {
  const searchParams = useSearchParams();
  const tabParam = searchParams.get("tab") as TabKey;
  const [tab, setTab] = useState<TabKey>(
    tabParam && TAB_KEYS.includes(tabParam) ? tabParam : "embedding"
  );
  const [providers, setProviders] = useState<AIProvider[]>([]);
  const [templates, setTemplates] = useState<ProviderTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [addDialog, setAddDialog] = useState(false);
  const [editDialog, setEditDialog] = useState<AIProvider | null>(null);
  const [keyDialog, setKeyDialog] = useState<AIProvider | null>(null);
  const [keys, setKeys] = useState<ApiKeyItem[]>([]);
  const [newKeyValue, setNewKeyValue] = useState("");

  useEffect(() => {
    if (tabParam && TAB_KEYS.includes(tabParam)) {
      setTab(tabParam);
    }
  }, [tabParam]);

  // Add form state
  const [useTemplate, setUseTemplate] = useState(true);
  const [selectedTemplate, setSelectedTemplate] = useState<string>("");
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
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    settingsApi.listProviders(tab).then(setProviders).catch(() => toast.error("Không thể tải danh sách providers")).finally(() => setLoading(false));
  }, [tab]);

  useEffect(() => {
    settingsApi.getTemplates().then(setTemplates).catch(() => {});
  }, []);

  // Filter templates + providers for current tab
  const tabTemplates = templates.filter((t) => t.service_type === tab);
  const llmBuiltin = tab === "llm";

  // ── Handlers ─────────────────────────────────────────────

  const resetForm = () => {
    setFormData({ service_type: tab, provider_name: "", display_name: "", url: "", model: "", api_key: "" });
    setSelectedTemplate("");
    setUseTemplate(true);
  };

  const handleTemplateSelect = (templateName: string) => {
    setSelectedTemplate(templateName);
    const t = tabTemplates.find((tp) => tp.provider_name === templateName);
    if (t) {
      setFormData({
        service_type: tab,
        provider_name: t.provider_name,
        display_name: t.display_name,
        url: t.url,
        model: t.model,
        api_key: "",
      });
    }
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
    if (f["edit-api_key"]) data.api_key = f["edit-api_key"].value;
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

  const providerCard = (p: AIProvider) => (
    <Card key={p.id} className={p.is_active ? "border-primary/50" : "opacity-70"}>
      <CardContent className="p-4">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <span className="text-2xl">{PROVIDER_ICONS[p.provider_name] ?? "🔗"}</span>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-semibold">{p.display_name}</span>
                {p.is_builtin && (
                  <Badge variant="outline" className="text-xs">
                    Built-in
                  </Badge>
                )}
                {p.is_active && (
                  <Badge className="bg-green-600 text-xs">Active</Badge>
                )}
              </div>
              <p className="text-xs text-muted-foreground mt-1 font-mono">{p.url || "—"}</p>
              <p className="text-xs text-muted-foreground font-mono">{p.model || "—"}</p>
            </div>
          </div>
          <div className="flex items-center gap-1">
            {!p.is_active && !llmBuiltin && (
              <Button variant="ghost" size="icon" onClick={() => handleActivate(p)} title="Activate">
                <Power className="h-4 w-4 text-green-600" />
              </Button>
            )}
            <Button variant="ghost" size="icon" onClick={() => setEditDialog(p)} title="Edit">
              <Globe className="h-4 w-4" />
            </Button>
            <Button variant="ghost" size="icon" onClick={() => handleTest(p)} title="Test connection">
              <TestTube className="h-4 w-4" />
            </Button>
            <Button variant="ghost" size="icon" onClick={() => openKeys(p)} title="API Keys">
              <Key className="h-4 w-4" />
            </Button>
            {!p.is_builtin && (
              <Button variant="ghost" size="icon" onClick={() => handleDelete(p)} title="Delete">
                <Trash2 className="h-4 w-4 text-destructive" />
              </Button>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Kết nối AI</h1>
        {!llmBuiltin && (
          <Button className="gap-2" onClick={() => { resetForm(); setAddDialog(true); }}>
            <Plus className="h-4 w-4" /> Thêm provider
          </Button>
        )}
      </div>

      <Tabs value={tab}>
        {TAB_KEYS.map((k) => (
          <TabsContent key={k} value={k} className="space-y-3 mt-4">
            {loading ? (
              <p className="text-sm text-muted-foreground">Loading...</p>
            ) : providers.filter((p) => p.service_type === k).length === 0 ? (
              <Card>
                <CardContent className="p-8 text-center text-muted-foreground">
                  <Cpu className="mx-auto h-8 w-8 mb-2" />
                  <p>Chưa có provider nào</p>
                  <p className="text-xs">Thêm provider mới để bắt đầu</p>
                </CardContent>
              </Card>
            ) : (
              providers.filter((p) => p.service_type === k).map(providerCard)
            )}
          </TabsContent>
        ))}
      </Tabs>

      {/* ── Add Dialog ── */}
      <Dialog open={addDialog} onOpenChange={setAddDialog}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Thêm provider — {TAB_LABELS[tab]}</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleAdd} className="space-y-4">
            {useTemplate && tabTemplates.length > 0 && (
              <div className="space-y-2">
                <Label>Chọn mẫu</Label>
                <div className="grid grid-cols-2 gap-2">
                  {tabTemplates.map((t) => (
                    <Button
                      key={t.provider_name}
                      type="button"
                      variant={selectedTemplate === t.provider_name ? "default" : "outline"}
                      className="justify-start text-xs h-auto py-2"
                      onClick={() => handleTemplateSelect(t.provider_name)}
                    >
                      <span className="mr-1">{PROVIDER_ICONS[t.provider_name] ?? "🔗"}</span>
                      {t.display_name}
                    </Button>
                  ))}
                </div>
                <Button type="button" variant="ghost" size="sm" onClick={() => setUseTemplate(false)}>
                  Nhập thủ công
                </Button>
              </div>
            )}
            {!useTemplate && (
              <Button type="button" variant="ghost" size="sm" onClick={() => setUseTemplate(true)}>
                Chọn mẫu
              </Button>
            )}
            <div className="space-y-2">
              <Label htmlFor="add-name">Tên hiển thị</Label>
              <Input id="add-name" value={formData.display_name} onChange={(e) => setFormData({ ...formData, display_name: e.target.value })} required />
            </div>
            <div className="space-y-2">
              <Label htmlFor="add-url">URL</Label>
              <Input id="add-url" value={formData.url} onChange={(e) => setFormData({ ...formData, url: e.target.value })} required />
            </div>
            <div className="space-y-2">
              <Label htmlFor="add-model">Model</Label>
              <Input id="add-model" value={formData.model} onChange={(e) => setFormData({ ...formData, model: e.target.value })} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="add-api_key">API Key</Label>
              <Input id="add-api_key" type="password" value={formData.api_key} onChange={(e) => setFormData({ ...formData, api_key: e.target.value })} />
            </div>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => setAddDialog(false)}>Hủy</Button>
              <Button type="submit">Thêm</Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      {/* ── Edit Dialog ── */}
      <Dialog open={!!editDialog} onOpenChange={() => setEditDialog(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Sửa — {editDialog?.display_name}</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleUpdate} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="edit-url">URL</Label>
              <Input id="edit-url" name="edit-url" defaultValue={editDialog?.url} required />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-model">Model</Label>
              <Input id="edit-model" name="edit-model" defaultValue={editDialog?.model} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-api_key">API Key</Label>
              <Input id="edit-api_key" name="edit-api_key" type="password" defaultValue={editDialog?.api_key} placeholder="Leave empty to keep current" />
            </div>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => setEditDialog(null)}>Hủy</Button>
              <Button type="submit">Lưu</Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      {/* ── API Key Dialog ── */}
      <Dialog open={!!keyDialog} onOpenChange={() => setKeyDialog(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>API Keys — {keyDialog?.display_name}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div className="flex gap-2">
              <Input
                type="password"
                placeholder="Nhập API key mới..."
                value={newKeyValue}
                onChange={(e) => setNewKeyValue(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addKey())}
              />
              <Button onClick={addKey} disabled={!newKeyValue.trim()}>Thêm</Button>
            </div>
            {keys.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-4">
                <Key className="mx-auto h-6 w-6 mb-1" />
                Chưa có API key
              </p>
            ) : (
              <div className="space-y-2 max-h-60 overflow-y-auto">
                {keys.map((k) => (
                  <div key={k.id} className="flex items-center justify-between border rounded p-2 text-sm">
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
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
