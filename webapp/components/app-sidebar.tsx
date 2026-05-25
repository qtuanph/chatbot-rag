"use client";

import { useState } from "react";
import { useSession } from "next-auth/react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  ChevronDown,
  LayoutDashboard,
  FileText,
  Users,
  MessageSquare,
  Settings,
  BarChart3,
  Plug,
  Cpu,
  PanelRightClose,
  Brain,
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
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
} from "@/components/ui/sidebar";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { UserNav } from "@/components/user-nav";

const adminNavItems = [
  { title: "Dashboard", href: "/admin", icon: LayoutDashboard },
  { title: "Thống kê", href: "/admin/analytics", icon: BarChart3 },
  { title: "Tài liệu", href: "/admin/documents", icon: FileText },
  { title: "Kết nối AI", href: "/admin/providers", icon: Plug, subItems: [
    { title: "Embedding", href: "/admin/providers?tab=embedding", icon: Cpu },
    { title: "Reranker", href: "/admin/providers?tab=reranker", icon: PanelRightClose },
    { title: "LLM", href: "/admin/providers?tab=llm", icon: Brain },
  ]},
  { title: "Người dùng", href: "/admin/users", icon: Users },
  { title: "Chat", href: "/chat", icon: MessageSquare },
  { title: "Cài đặt", href: "/settings", icon: Settings },
];

const memberNavItems = [
  { title: "Chat", href: "/chat", icon: MessageSquare },
  { title: "Cài đặt", href: "/settings", icon: Settings },
];

interface NavItem {
  title: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  subItems?: { title: string; href: string; icon: React.ComponentType<{ className?: string }> }[];
}

export function AppSidebar() {
  const { data: session } = useSession();
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const currentTab = searchParams.get("tab");
  const isAdmin = session?.role === "admin";
  const items: NavItem[] = isAdmin ? adminNavItems : memberNavItems;
  const [openGroups, setOpenGroups] = useState<Set<string>>(new Set());

  const isActive = (href: string) => {
    const base = href.split("?")[0];
    return pathname === base || (base !== "/" && pathname.startsWith(base + "/"));
  };

  const isSubActive = (subHref: string) => {
    const tab = subHref.split("?tab=")[1];
    return currentTab === tab;
  };

  const toggleGroup = (href: string) => {
    setOpenGroups((prev) => {
      const next = new Set(prev);
      if (next.has(href)) next.delete(href);
      else next.add(href);
      return next;
    });
  };

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
              {items.map((item) =>
                item.subItems ? (
                  <Collapsible
                    key={item.href}
                    className="group/collapsible"
                    open={openGroups.has(item.href)}
                    onOpenChange={() => toggleGroup(item.href)}
                  >
                    <SidebarMenuItem>
                      <CollapsibleTrigger className="w-full cursor-pointer">
                        <SidebarMenuButton isActive={isActive(item.href)}>
                          <item.icon className="h-4 w-4" />
                          <span>{item.title}</span>
                          <ChevronDown className="ml-auto h-4 w-4 transition-transform group-data-[state=open]/collapsible:rotate-180" />
                        </SidebarMenuButton>
                      </CollapsibleTrigger>
                      <CollapsibleContent>
                        <SidebarMenuSub>
                          {item.subItems.map((sub) => (
                            <SidebarMenuSubItem key={sub.href}>
                              <SidebarMenuSubButton
                                isActive={isSubActive(sub.href)}
                                onClick={() => router.push(sub.href)}
                              >
                                <sub.icon className="h-4 w-4" />
                                <span>{sub.title}</span>
                              </SidebarMenuSubButton>
                            </SidebarMenuSubItem>
                          ))}
                        </SidebarMenuSub>
                      </CollapsibleContent>
                    </SidebarMenuItem>
                  </Collapsible>
                ) : (
                  <SidebarMenuItem key={item.href}>
                    <SidebarMenuButton
                      isActive={isActive(item.href)}
                      onClick={() => router.push(item.href)}
                    >
                      <item.icon className="h-4 w-4" />
                      <span>{item.title}</span>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                )
              )}
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
