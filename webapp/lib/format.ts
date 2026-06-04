export function formatNumber(value: number): string {
  return new Intl.NumberFormat("vi-VN").format(value || 0);
}

export function formatVnd(value: number): string {
  return new Intl.NumberFormat("vi-VN", {
    style: "currency",
    currency: "VND",
    maximumFractionDigits: 0,
  }).format(Math.max(0, Math.round(value || 0)));
}

export function microsVndToRoundedVnd(value: number): number {
  return Math.round((value || 0) / 1_000_000);
}

export function formatLatency(ms: number): string {
  if (!ms) return "—";
  if (ms < 1000) return `${ms} ms`;
  return `${(ms / 1000).toFixed(2)} s`;
}

export function formatRoleLabel(role?: string | null): string {
  if (role === "platform_admin") return "Quản trị nền tảng";
  if (role === "tenant_admin") return "Quản trị tenant";
  return role || "Không rõ";
}

export function timeAgo(dateIso: string): string {
  const now = Date.now();
  const then = new Date(dateIso).getTime();
  const diffMinutes = Math.max(0, Math.floor((now - then) / 60000));

  if (diffMinutes < 1) return "vừa xong";
  if (diffMinutes < 60) return `${diffMinutes} phút trước`;

  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours} giờ trước`;

  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays} ngày trước`;
}

export function formatDateTimeVN(dateIso?: string | null): string {
  if (!dateIso) return "—";
  const date = new Date(dateIso);
  if (Number.isNaN(date.getTime())) return dateIso;
  return new Intl.DateTimeFormat("vi-VN", {
    timeZone: "Asia/Ho_Chi_Minh",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(date);
}
