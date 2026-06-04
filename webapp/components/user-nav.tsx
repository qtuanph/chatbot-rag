"use client";

import { LogOut, Settings } from "lucide-react";
import { signOut, useSession } from "next-auth/react";
import { useRouter } from "next/navigation";

import { authApi } from "@/lib/api-client";
import { formatRoleLabel } from "@/lib/format";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

export function UserNav() {
  const { data: session } = useSession();
  const router = useRouter();

  if (!session) return null;

  const initials = session.user?.name?.slice(0, 2).toUpperCase() || "U";

  const handleLogout = async () => {
    try {
      await authApi.logout();
    } finally {
      await signOut({ callbackUrl: "/login" });
    }
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger className="flex items-center gap-2 rounded-md px-2 py-1.5 outline-none hover:bg-muted">
        <Avatar className="h-7 w-7">
          <AvatarFallback className="text-xs">{initials}</AvatarFallback>
        </Avatar>
        <div className="flex flex-col items-start text-sm">
          <span className="font-medium">{session.user?.name}</span>
          <Badge variant="secondary" className="px-1 py-0 text-[10px]">
            {formatRoleLabel(session.role)}
          </Badge>
        </div>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-52">
        <DropdownMenuItem onClick={() => router.push("/settings")}>
          <Settings className="mr-2 h-4 w-4" />
          Cài đặt
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem className="text-destructive" onClick={handleLogout}>
          <LogOut className="mr-2 h-4 w-4" />
          Đăng xuất
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
