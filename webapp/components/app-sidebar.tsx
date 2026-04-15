"use client";

import { useSession } from "next-auth/react";
import { usePathname, useRouter } from "next/navigation";
import {
  LayoutDashboard,
  FileText,
  Users,
  MessageSquare,
  Settings,
} from "lucide-react";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";
import { UserNav } from "@/components/user-nav";

const adminNavItems = [
  { title: "Dashboard", href: "/admin", icon: LayoutDashboard },
  { title: "Tài liệu", href: "/admin/documents", icon: FileText },
  { title: "Người dùng", href: "/admin/users", icon: Users },
  { title: "Chat", href: "/chat", icon: MessageSquare },
  { title: "Cài đặt", href: "/settings", icon: Settings },
];

const memberNavItems = [
  { title: "Chat", href: "/chat", icon: MessageSquare },
  { title: "Cài đặt", href: "/settings", icon: Settings },
];

export function AppSidebar() {
  const { data: session } = useSession();
  const pathname = usePathname();
  const router = useRouter();
  const isAdmin = session?.role === "admin";
  const items = isAdmin ? adminNavItems : memberNavItems;

  return (
    <Sidebar>
      <SidebarHeader className="border-b px-4 py-3">
        <h2 className="text-lg font-semibold">RAG Chatbot</h2>
        <p className="text-xs text-muted-foreground">Hệ thống hỏi đáp tài liệu</p>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Menu</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {items.map((item) => (
                <SidebarMenuItem key={item.href}>
                  <SidebarMenuButton
                    isActive={pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href + "/"))}
                    onClick={() => router.push(item.href)}
                  >
                    <item.icon className="h-4 w-4" />
                    <span>{item.title}</span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter className="border-t p-2">
        <UserNav />
      </SidebarFooter>
    </Sidebar>
  );
}
