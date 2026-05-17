"use client";

import { useEffect, useState, useCallback } from "react";
import { useSession } from "next-auth/react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import { toast } from "sonner";
import { adminApi } from "@/lib/api-client";
import type { ProviderItem, ModelItem } from "@/types/api";
import {
  Plus,
  Trash2,
  Power,
  PowerOff,
  RefreshCw,
  Unplug,
  Key,
  Globe,
  Tag,
  Brain,
  Cpu,
  Zap,
  Sparkles,
  Cable,
} from "lucide-react";

interface ProviderPreset {
  name: string;
  label: string;
  base_url: string;
  models: string;
  icon: string;
  description: string;
}

const PRESETS: ProviderPreset[] = [
  { name: "openai", label: "OpenAI", base_url: "https://api.openai.com/v1", models: "gpt-4o, gpt-4o-mini", icon: "sparkles", description: "GPT-4o, GPT-4o-mini và các model OpenAI" },
  { name: "nvidia-nim", label: "NVIDIA NIM", base_url: "https://integrate.api.nvidia.com/v1", models: "meta/llama-3.1-8b-instruct, meta/llama-3.1-70b-instruct, deepseek-ai/DeepSeek-R1", icon: "cpu", description: "Llama 3.1, DeepSeek R1 và các model NVIDIA" },
  { name: "groq", label: "Groq", base_url: "https://api.groq.com/openai/v1", models: "llama-3.3-70b-versatile, deepseek-r1-distill-llama-70b", icon: "zap", description: "Llama 3, DeepSeek với tốc độ cực nhanh" },
  { name: "deepseek", label: "DeepSeek", base_url: "https://api.deepseek.com/v1", models: "deepseek-chat, deepseek-reasoner", icon: "brain", description: "DeepSeek-V3, DeepSeek-R1 với thinking mode" },
];

function PresetIcon({ icon }: { icon: string }) {
  switch (icon) {
    case "sparkles": return <Sparkles className="h-5 w-5" />;
    case "cpu": return <Cpu className="h-5 w-5" />;
    case "zap": return <Zap className="h-5 w-5" />;
    case "brain": return <Brain className="h-5 w-5" />;
    default: return <Cable className="h-5 w-5" />;
  }
}

export default function ProvidersPage() {
  const { data: session } = useSession();
  const [providers, setProviders] = useState<ProviderItem[]>([]);
  const [models, setModels] = useState<ModelItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: "", base_url: "", api_key: "", models: "", alias: "" });
  const [submitting, setSubmitting] = useState(false);

  const fetchData = useCallback(async () => {
    if (!session) return;
    try {
      setLoading(true);
      const [providersData, modelsData] = await Promise.all([
        adminApi.listProviders(),
        adminApi.listModels(),
      ]);
      setProviders(providersData);
      setModels(modelsData);
    } catch (err) {
      toast.error("Không thể tải danh sách providers");
    } finally {
      setLoading(false);
    }
  }, [session]);

  useEffect(() => {
    if (session) void fetchData();
  }, [session, fetchData]);

  const applyPreset = (preset: ProviderPreset) => {
    setForm({
      name: preset.name,
      base_url: preset.base_url,
      api_key: form.api_key,
      models: preset.models,
      alias: "",
    });
  };

  const handleAdd = async () => {
    if (!form.name || !form.base_url || !form.api_key) {
      toast.error("Vui lòng nhập tên, base URL và API key");
      return;
    }
    setSubmitting(true);
    try {
      await adminApi.addProvider({
        name: form.name,
        base_url: form.base_url,
        api_key: form.api_key,
        models: form.models ? form.models.split(",").map((m) => m.trim()) : [],
        alias: form.alias || undefined,
      });
      toast.success(`Đã thêm provider "${form.name}"`);
      setShowForm(false);
      setForm({ name: "", base_url: "", api_key: "", models: "", alias: "" });
      void fetchData();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Lỗi khi thêm provider");
    } finally {
      setSubmitting(false);
    }
  };

  const handleToggle = async (name: string) => {
    try {
      const result = await adminApi.toggleProvider(name);
      toast.success(result.disabled ? `Đã tắt "${name}"` : `Đã bật "${name}"`);
      void fetchData();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Lỗi khi chuyển trạng thái");
    }
  };

  const handleDelete = async (name: string) => {
    if (!confirm(`Xóa provider "${name}"?`)) return;
    try {
      await adminApi.deleteProvider(name);
      toast.success(`Đã xóa "${name}"`);
      void fetchData();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Lỗi khi xóa provider");
    }
  };

  if (loading && providers.length === 0) {
    return (
      <div className="p-6 space-y-6">
        <h1 className="text-2xl font-bold">Kết nối Provider</h1>
        <div className="space-y-3">
          {[...Array(3)].map((_, i) => (
            <Skeleton key={i} className="h-20" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Kết nối Provider</h1>
          <p className="text-sm text-muted-foreground">
            Thêm và quản lý các AI provider để sử dụng trong chat
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={fetchData} disabled={loading}>
            <RefreshCw className={`h-4 w-4 mr-2 ${loading ? "animate-spin" : ""}`} />
            Làm mới
          </Button>
          <Button size="sm" onClick={() => { setShowForm(true); setForm({ name: "", base_url: "", api_key: "", models: "", alias: "" }); }}>
            <Plus className="h-4 w-4 mr-2" />
            Thêm provider
          </Button>
        </div>
      </div>

      {/* Add form */}
      {showForm && (
        <Card>
          <CardHeader>
            <CardTitle>Thêm provider mới</CardTitle>
            <p className="text-sm text-muted-foreground">
              Chọn một template nhanh hoặc nhập thủ công thông tin provider
            </p>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Quick connect presets */}
            <div>
              <Label className="mb-2 block">Template nhanh</Label>
              <div className="grid gap-2 sm:grid-cols-2">
                {PRESETS.map((preset) => (
                  <button
                    key={preset.name}
                    type="button"
                    onClick={() => applyPreset(preset)}
                    className={`flex items-start gap-3 p-3 rounded-lg border text-left transition-all hover:border-primary hover:bg-primary/5 ${
                      form.name === preset.name ? "border-primary bg-primary/5 ring-1 ring-primary" : "border-border"
                    }`}
                  >
                    <div className="mt-0.5 text-muted-foreground">
                      <PresetIcon icon={preset.icon} />
                    </div>
                    <div className="min-w-0">
                      <div className="font-medium text-sm">{preset.label}</div>
                      <div className="text-xs text-muted-foreground mt-0.5 line-clamp-2">{preset.description}</div>
                    </div>
                  </button>
                ))}
              </div>
            </div>

            <Separator />

            {/* Manual form */}
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="name" className="flex items-center gap-1.5">
                  <Tag className="h-3.5 w-3.5" />
                  Tên provider *
                </Label>
                <Input id="name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="VD: openai, nvidia-nim" />
              </div>
              <div className="space-y-2">
                <Label htmlFor="alias" className="flex items-center gap-1.5">
                  <Sparkles className="h-3.5 w-3.5" />
                  Alias (tùy chọn)
                </Label>
                <Input id="alias" value={form.alias} onChange={(e) => setForm({ ...form, alias: e.target.value })} placeholder="VD: GPT-4o" />
              </div>
              <div className="space-y-2 md:col-span-2">
                <Label htmlFor="base_url" className="flex items-center gap-1.5">
                  <Globe className="h-3.5 w-3.5" />
                  Base URL *
                </Label>
                <Input id="base_url" value={form.base_url} onChange={(e) => setForm({ ...form, base_url: e.target.value })} placeholder="https://integrate.api.nvidia.com/v1" />
              </div>
              <div className="space-y-2 md:col-span-2">
                <Label htmlFor="api_key" className="flex items-center gap-1.5">
                  <Key className="h-3.5 w-3.5" />
                  API Key *
                </Label>
                <Input id="api_key" type="password" value={form.api_key} onChange={(e) => setForm({ ...form, api_key: e.target.value })} placeholder="API key của provider" />
              </div>
              <div className="space-y-2 md:col-span-2">
                <Label htmlFor="models">Models (cách nhau bằng dấu phẩy)</Label>
                <Input id="models" value={form.models} onChange={(e) => setForm({ ...form, models: e.target.value })} placeholder="meta/llama-3.1-8b-instruct, deepseek-ai/DeepSeek-R1" />
              </div>
            </div>

            <div className="flex gap-2 pt-2">
              <Button onClick={handleAdd} disabled={submitting}>
                {submitting ? "Đang thêm..." : "Thêm provider"}
              </Button>
              <Button variant="outline" onClick={() => setShowForm(false)}>Hủy</Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Provider list */}
      {providers.length === 0 ? (
        <Card>
          <CardContent className="pt-10 pb-10 text-center text-muted-foreground">
            <Unplug className="h-12 w-12 mx-auto mb-3 opacity-50" />
            <p className="font-medium">Chưa có provider nào</p>
            <p className="text-sm mt-1">Thêm provider đầu tiên để bắt đầu sử dụng AI chat</p>
            <Button className="mt-4" size="sm" onClick={() => setShowForm(true)}>
              <Plus className="h-4 w-4 mr-2" />
              Thêm provider
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {providers.map((p) => (
            <Card key={p.name} className={p.disabled ? "opacity-60" : ""}>
              <CardContent className="pt-4 pb-4">
                <div className="flex items-center justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium truncate">{p.name}</span>
                      <Badge variant={p.disabled ? "outline" : "default"}>
                        {p.disabled ? "Đã tắt" : "Đang hoạt động"}
                      </Badge>
                    </div>
                    <p className="text-xs text-muted-foreground truncate mt-0.5 font-mono">{p.base_url}</p>
                    {p.models.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-1.5">
                        {p.models.map((m) => (
                          <Badge key={m.name} variant="secondary" className="text-xs">
                            {m.alias || m.name}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </div>
                  <div className="flex items-center gap-1 shrink-0">
                    <Button size="icon" variant="ghost" onClick={() => handleToggle(p.name)} title={p.disabled ? "Bật" : "Tắt"}>
                      {p.disabled ? <PowerOff className="h-4 w-4" /> : <Power className="h-4 w-4" />}
                    </Button>
                    <Button size="icon" variant="ghost" onClick={() => handleDelete(p.name)} title="Xóa">
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Models summary */}
      {models.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Models khả dụng ({models.length})</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {models.map((m) => (
                <Badge key={`${m.provider}/${m.name}`} variant="outline">
                  {m.provider}/{m.name}
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
