"use client";

import { useEffect, useState, useCallback } from "react";
import { useSession } from "next-auth/react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Brain,
  Plus,
  Trash2,
  ToggleLeft,
  ToggleRight,
  Loader2,
} from "lucide-react";
import { memoriesApi, type MemoryItem } from "@/lib/api-client";
import { toast } from "sonner";

const MEMORY_TYPE_LABELS: Record<string, string> = {
  preference: "Sở thích",
  correction: "Sửa đổi",
  instruction: "Chỉ dẫn",
  fact: "Thông tin",
};

const MEMORY_TYPE_COLORS: Record<string, string> = {
  preference: "bg-blue-500/15 text-blue-700 dark:text-blue-400",
  correction: "bg-orange-500/15 text-orange-700 dark:text-orange-400",
  instruction: "bg-purple-500/15 text-purple-700 dark:text-purple-400",
  fact: "bg-green-500/15 text-green-700 dark:text-green-400",
};

export default function SettingsPage() {
  const { data: session } = useSession();
  const [memories, setMemories] = useState<MemoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [newContent, setNewContent] = useState("");
  const [newType, setNewType] = useState("instruction");
  const [saving, setSaving] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const fetchMemories = useCallback(async () => {
    if (!session) return;
    try {
      const result = await memoriesApi.list();
      setMemories(result.items);
    } catch {
      toast.error("Không thể tải bộ nhớ");
    } finally {
      setLoading(false);
    }
  }, [session]);

  useEffect(() => {
    const timer = setTimeout(() => {
      void fetchMemories();
    }, 0);
    return () => clearTimeout(timer);
  }, [fetchMemories]);

  const handleAdd = useCallback(async () => {
    if (!session || !newContent.trim()) return;
    setSaving(true);
    try {
      const item = await memoriesApi.create(
        { memory_type: newType, content: newContent.trim() },
      );
      setMemories((prev) => [item, ...prev]);
      setNewContent("");
      toast.success("Đã thêm ghi nhớ");
    } catch {
      toast.error("Không thể thêm ghi nhớ");
    } finally {
      setSaving(false);
    }
  }, [session, newContent, newType]);

  const handleToggle = useCallback(
    async (id: string, isActive: boolean) => {
      if (!session) return;
      try {
        const updated = await memoriesApi.update(
          id,
          { is_active: !isActive },
        );
        setMemories((prev) =>
          prev.map((m) => (m.id === id ? updated : m)),
        );
        toast.success(updated.is_active ? "Đã bật ghi nhớ" : "Đã tắt ghi nhớ");
      } catch {
        toast.error("Không thể cập nhật");
      }
    },
    [session],
  );

  const handleDelete = useCallback(
    async (id: string) => {
      if (!session) return;
      setDeletingId(id);
      try {
        await memoriesApi.delete(id);
        setMemories((prev) => prev.filter((m) => m.id !== id));
        toast.success("Đã xóa ghi nhớ");
      } catch {
        toast.error("Không thể xóa");
      } finally {
        setDeletingId(null);
      }
    },
    [session],
  );

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Cài đặt</h1>

      {/* Account info */}
      <Card>
        <CardHeader>
          <CardTitle>Thông tin tài khoản</CardTitle>
          <CardDescription>Thông tin người dùng hiện tại</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 items-start sm:items-center gap-1 sm:gap-4">
            <Label className="text-muted-foreground">Tên đăng nhập</Label>
            <div className="sm:col-span-2 font-medium">{session?.user?.name}</div>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 items-start sm:items-center gap-1 sm:gap-4">
            <Label className="text-muted-foreground">Vai trò</Label>
            <div className="sm:col-span-2">
              <Badge variant="secondary">{session?.role}</Badge>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* AI Memory */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Brain className="h-5 w-5" />
            Bộ nhớ AI
          </CardTitle>
          <CardDescription>
            Quản lý những gì AI ghi nhớ về bạn. AI sẽ sử dụng các ghi nhớ này
            để cá nhân hóa câu trả lời.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Add new memory */}
          <div className="flex flex-col sm:flex-row gap-2">
            <div className="flex gap-2">
              <Select value={newType} onValueChange={(v) => setNewType(v ?? "instruction")}>
                <SelectTrigger className="w-[140px] shrink-0">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="instruction">Chỉ dẫn</SelectItem>
                  <SelectItem value="preference">Sở thích</SelectItem>
                  <SelectItem value="correction">Sửa đổi</SelectItem>
                  <SelectItem value="fact">Thông tin</SelectItem>
                </SelectContent>
              </Select>
              <div className="block sm:hidden flex-1">
                <Button
                  onClick={handleAdd}
                  disabled={!newContent.trim() || saving}
                  className="w-full gap-1"
                >
                  {saving ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Plus className="h-4 w-4" />
                  )}
                  Thêm
                </Button>
              </div>
            </div>
            <Input
              placeholder="Nhập ghi nhớ... (vd: Trả lời ngắn gọn, đi thẳng vào vấn đề)"
              value={newContent}
              onChange={(e) => setNewContent(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && newContent.trim()) handleAdd();
              }}
              className="flex-1"
            />
            <Button
              onClick={handleAdd}
              disabled={!newContent.trim() || saving}
              className="hidden sm:flex shrink-0 gap-1"
            >
              {saving ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Plus className="h-4 w-4" />
              )}
              Thêm
            </Button>
          </div>

          {/* Memory list */}
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : memories.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <Brain className="mx-auto h-8 w-8 mb-2 opacity-50" />
              <p className="text-sm">Chưa có ghi nhớ nào</p>
              <p className="text-xs mt-1">
                Thêm chỉ dẫn để AI hiểu bạn hơn, hoặc AI sẽ tự học từ cuộc trò chuyện
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {memories.map((memory) => (
                <div
                  key={memory.id}
                  className={`flex items-start gap-3 rounded-lg border p-3 transition-opacity ${
                    !memory.is_active ? "opacity-50" : ""
                  }`}
                >
                  <Badge
                    variant="outline"
                    className={`shrink-0 mt-0.5 ${MEMORY_TYPE_COLORS[memory.memory_type] || ""}`}
                  >
                    {MEMORY_TYPE_LABELS[memory.memory_type] || memory.memory_type}
                  </Badge>
                  <p className="flex-1 text-sm">{memory.content}</p>
                  <div className="flex items-center gap-1 shrink-0">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7"
                      onClick={() => handleToggle(memory.id, memory.is_active)}
                      title={memory.is_active ? "Tắt" : "Bật"}
                    >
                      {memory.is_active ? (
                        <ToggleRight className="h-4 w-4 text-green-600" />
                      ) : (
                        <ToggleLeft className="h-4 w-4 text-muted-foreground" />
                      )}
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7"
                      disabled={deletingId === memory.id}
                      onClick={() => handleDelete(memory.id)}
                    >
                      {deletingId === memory.id ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Trash2 className="h-4 w-4 text-destructive" />
                      )}
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
