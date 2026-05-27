"use client";

import { useCallback, useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { Eye, Plus, Trash2, Users } from "lucide-react";
import { toast } from "sonner";

import { authApi, ApiError } from "@/lib/api-client";
import type {
  CreateUserRequest,
  RoleItem,
  UserItem,
  UserUsageDetail,
  UserUsageSummaryItem,
} from "@/types/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

function formatInt(n: number): string {
  return new Intl.NumberFormat("vi-VN").format(n || 0);
}

function formatUsd(n: number): string {
  return `$${(n || 0).toFixed(6)}`;
}

export default function UsersPage() {
  const { data: session } = useSession();

  const [users, setUsers] = useState<UserItem[]>([]);
  const [roles, setRoles] = useState<RoleItem[]>([]);
  const [usageByUserId, setUsageByUserId] = useState<Record<string, UserUsageSummaryItem>>({});

  const [dialogOpen, setDialogOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [detailTarget, setDetailTarget] = useState<UserItem | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailUsage, setDetailUsage] = useState<UserUsageDetail | null>(null);

  const fetchUsers = useCallback(async () => {
    if (!session) return;
    try {
      setUsers(await authApi.getUsers());
    } catch {
      toast.error("Không thể tải danh sách người dùng");
    }
  }, [session]);

  const fetchRoles = useCallback(async () => {
    if (!session) return;
    try {
      setRoles(await authApi.getRoles());
    } catch {
      toast.error("Không thể tải danh sách vai trò");
    }
  }, [session]);

  const fetchUsageSummary = useCallback(async () => {
    if (!session) return;
    try {
      const res = await authApi.getUsersUsageSummary();
      const map: Record<string, UserUsageSummaryItem> = {};
      for (const item of res.items) map[item.user_id] = item;
      setUsageByUserId(map);
    } catch {
      toast.error("Không thể tải thống kê token theo người dùng");
    }
  }, [session]);

  useEffect(() => {
    const timer = setTimeout(() => {
      void fetchUsers();
      void fetchRoles();
      void fetchUsageSummary();
    }, 0);
    return () => clearTimeout(timer);
  }, [fetchUsers, fetchRoles, fetchUsageSummary]);

  const handleCreate = useCallback(
    async (e: React.FormEvent<HTMLFormElement>) => {
      e.preventDefault();
      if (!session) return;

      const formData = new FormData(e.currentTarget);
      const username = ((formData.get("username") as string) ?? "").trim();
      const password = ((formData.get("password") as string) ?? "").trim();
      const role = (formData.get("role") as CreateUserRequest["role"]) ?? "member";

      if (username.length < 3) {
        toast.error("Tên đăng nhập phải có ít nhất 3 ký tự");
        return;
      }
      if (password.length < 6) {
        toast.error("Mật khẩu phải có ít nhất 6 ký tự");
        return;
      }

      try {
        await authApi.createUser({ username, password, role });
        toast.success("Tạo người dùng thành công");
        setDialogOpen(false);
        await fetchUsers();
        await fetchUsageSummary();
      } catch (err) {
        toast.error(err instanceof ApiError ? err.detail : "Tạo người dùng thất bại");
      }
    },
    [session, fetchUsers, fetchUsageSummary],
  );

  const handleDelete = useCallback(
    async (username: string) => {
      if (!session) return;
      try {
        await authApi.deleteUser(username);
        toast.success(`Đã xóa người dùng ${username}`);
        setDeleteTarget(null);
        await fetchUsers();
        await fetchUsageSummary();
      } catch (err) {
        toast.error(err instanceof ApiError ? err.detail : "Xóa thất bại");
      }
    },
    [session, fetchUsers, fetchUsageSummary],
  );

  const openDetail = useCallback(async (user: UserItem) => {
    setDetailTarget(user);
    setDetailLoading(true);
    setDetailUsage(null);
    try {
      setDetailUsage(await authApi.getUserUsageDetail(user.id));
    } catch (err) {
      toast.error(err instanceof ApiError ? err.detail : "Không thể tải chi tiết thống kê");
    } finally {
      setDetailLoading(false);
    }
  }, []);

  const closeDetail = useCallback(() => {
    setDetailTarget(null);
    setDetailUsage(null);
    setDetailLoading(false);
  }, []);

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Người dùng</h1>
          <p className="text-sm text-muted-foreground">{users.length} người dùng</p>
        </div>

        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <Button className="gap-2" onClick={() => setDialogOpen(true)}>
            <Plus className="h-4 w-4" />
            Thêm người dùng
          </Button>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Thêm người dùng mới</DialogTitle>
            </DialogHeader>
            <form onSubmit={handleCreate} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="username">Tên đăng nhập</Label>
                <Input id="username" name="username" required minLength={3} maxLength={64} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="password">Mật khẩu</Label>
                <Input id="password" name="password" type="password" required minLength={6} maxLength={256} />
                <p className="text-xs text-muted-foreground">Mật khẩu tối thiểu 6 ký tự.</p>
              </div>
              <div className="space-y-2">
                <Label htmlFor="role">Vai trò</Label>
                <Select name="role" defaultValue={roles[0]?.name ?? "member"}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {roles.length === 0 ? (
                      <SelectItem value="member">member</SelectItem>
                    ) : (
                      roles.map((role) => (
                        <SelectItem key={role.id} value={role.name}>
                          {role.name}
                        </SelectItem>
                      ))
                    )}
                  </SelectContent>
                </Select>
              </div>
              <div className="flex justify-end gap-2">
                <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>
                  Hủy
                </Button>
                <Button type="submit">Tạo</Button>
              </div>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Tên đăng nhập</TableHead>
              <TableHead>Vai trò</TableHead>
              <TableHead>Token In/Out (LLM, 30 ngày)</TableHead>
              <TableHead>Chi phí (30 ngày, 3 model)</TableHead>
              <TableHead className="text-right">Thao tác</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {users.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} className="text-center py-8 text-muted-foreground">
                  <Users className="mx-auto h-8 w-8 mb-2" />
                  Chưa có người dùng
                </TableCell>
              </TableRow>
            ) : (
              users.map((user) => {
                const usage = usageByUserId[user.id];
                return (
                  <TableRow key={user.id}>
                    <TableCell className="font-medium">{user.username}</TableCell>
                    <TableCell>
                      <Badge variant={user.role === "admin" ? "default" : "secondary"}>
                        {user.role}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      {usage ? (
                        <span className="text-sm">
                          {formatInt(usage.tokens_in)} / {formatInt(usage.tokens_out)}
                        </span>
                      ) : (
                        <span className="text-sm text-muted-foreground">0 / 0</span>
                      )}
                    </TableCell>
                    <TableCell>{usage ? formatUsd(usage.cost_usd) : "$0.000000"}</TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-2">
                        <Button variant="outline" size="sm" onClick={() => void openDetail(user)}>
                          <Eye className="h-4 w-4 mr-1" />
                          Xem chi tiết
                        </Button>
                        {user.username !== session?.user?.name && (
                          <Button variant="ghost" size="icon" onClick={() => setDeleteTarget(user.username)}>
                            <Trash2 className="h-4 w-4 text-destructive" />
                          </Button>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })
            )}
          </TableBody>
        </Table>
      </div>

      <Dialog open={!!deleteTarget} onOpenChange={() => setDeleteTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Xác nhận xóa</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Xóa người dùng <strong>{deleteTarget}</strong>? Hành động này không thể hoàn tác.
          </p>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>
              Hủy
            </Button>
            <Button variant="destructive" onClick={() => deleteTarget && void handleDelete(deleteTarget)}>
              Xóa
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={!!detailTarget} onOpenChange={(open) => !open && closeDetail()}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Thống kê 30 ngày: {detailTarget?.username ?? "-"}</DialogTitle>
          </DialogHeader>
          {detailLoading ? (
            <p className="text-sm text-muted-foreground">Đang tải dữ liệu...</p>
          ) : !detailUsage ? (
            <p className="text-sm text-muted-foreground">Không có dữ liệu.</p>
          ) : (
            <div className="space-y-4">
              <div className="rounded-md border p-4 space-y-2">
                <h3 className="font-semibold">Tổng quan 30 ngày</h3>
                <div className="text-sm">
                  <div>
                    Token In/Out: {formatInt(detailUsage.window_30d.tokens_in)} /{" "}
                    {formatInt(detailUsage.window_30d.tokens_out)}
                  </div>
                  <div>Tổng token: {formatInt(detailUsage.window_30d.total_tokens)}</div>
                  <div>Chi phí ước tính: {formatUsd(detailUsage.window_30d.estimated_cost_usd)}</div>
                </div>
              </div>

              <div className="rounded-md border p-4 space-y-2">
                <h3 className="font-semibold">Chi tiết theo model (30 ngày)</h3>
                <div className="text-sm space-y-1">
                  <div>
                    LLM: {formatInt(detailUsage.window_30d.by_model_type.llm.tokens_in)} /{" "}
                    {formatInt(detailUsage.window_30d.by_model_type.llm.tokens_out)} token
                  </div>
                  <div>
                    Embedding: {formatInt(detailUsage.window_30d.by_model_type.embedding.tokens_in)} /{" "}
                    {formatInt(detailUsage.window_30d.by_model_type.embedding.tokens_out)} token
                  </div>
                  <div>
                    Reranker: {formatInt(detailUsage.window_30d.by_model_type.reranker.tokens_in)} /{" "}
                    {formatInt(detailUsage.window_30d.by_model_type.reranker.tokens_out)} token
                  </div>
                </div>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
