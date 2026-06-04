"use client";

import { useState } from "react";
import { useSession } from "next-auth/react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  BarChart3,
  Building2,
  ChevronRight,
  FileText,
  LayoutDashboard,
  MessageSquare,
  Plug,
  Settings,
  Users,
} from "lucide-react";

import { UserNav } from "@/components/user-nav";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
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

type NavItem = {
  title: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  children?: Array<{ title: string; href: string }>;
};

const platformItems: NavItem[] = [
  { title: "Tổng quan", href: "/admin", icon: LayoutDashboard },
  { title: "Tenant", href: "/admin/tenants", icon: Building2 },
  { title: "Tài liệu", href: "/admin/documents", icon: FileText },
  { title: "Người dùng", href: "/admin/users", icon: Users },
  { title: "Thống kê", href: "/admin/analytics", icon: BarChart3 },
  {
    title: "Kết nối AI",
    href: "/admin/providers",
    icon: Plug,
    children: [
      { title: "Embedding", href: "/admin/providers?tab=embedding" },
      { title: "Reranker", href: "/admin/providers?tab=reranker" },
      { title: "LLM", href: "/admin/providers?tab=llm" },
    ],
  },
  { title: "Chat test", href: "/chat", icon: MessageSquare },
  { title: "Cài đặt", href: "/settings", icon: Settings },
];

const tenantItems: NavItem[] = [
  { title: "Chat test", href: "/chat", icon: MessageSquare },
  { title: "Tài liệu", href: "/documents", icon: FileText },
  { title: "Thống kê", href: "/analytics", icon: BarChart3 },
  { title: "Cài đặt tenant", href: "/settings", icon: Settings },
];

export function AppSidebar() {
  const { data: session } = useSession();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const router = useRouter();
  const providerTab = searchParams.get("tab");
  const [isAiOpen, setIsAiOpen] = useState(false);

  const items = session?.role === "platform_admin" ? platformItems : tenantItems;
  const isAiExpanded = pathname === "/admin/providers" || isAiOpen;

  const isActive = (href: string) => pathname === href || (href !== "/" && pathname.startsWith(`${href}/`));

  return (
    <Sidebar>
      <SidebarHeader className="border-b px-4 py-3">
        <h2 className="text-lg font-semibold">RAG Platform</h2>
        <p className="text-xs text-muted-foreground">Nền tảng chatbot tài liệu đa tenant</p>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Điều hướng</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {items.map((item) => (
                <SidebarMenuItem key={item.href}>
                  {item.children?.length ? (
                    <Collapsible open={isAiExpanded} onOpenChange={setIsAiOpen}>
                      <CollapsibleTrigger className="w-full">
                        <SidebarMenuButton isActive={isActive(item.href)}>
                          <item.icon className="h-4 w-4" />
                          <span>{item.title}</span>
                          <ChevronRight className={`ml-auto h-4 w-4 transition-transform ${isAiExpanded ? "rotate-90" : ""}`} />
                        </SidebarMenuButton>
                      </CollapsibleTrigger>
                      <CollapsibleContent>
                        <SidebarMenuSub>
                          {item.children.map((child) => (
                            <SidebarMenuSubItem key={child.href}>
                              <SidebarMenuSubButton
                                isActive={
                                  pathname === "/admin/providers" &&
                                  providerTab === new URLSearchParams(child.href.split("?")[1] || "").get("tab")
                                }
                                onClick={(event) => {
                                  event.preventDefault();
                                  router.push(child.href);
                                }}
                              >
                                <span>{child.title}</span>
                              </SidebarMenuSubButton>
                            </SidebarMenuSubItem>
                          ))}
                        </SidebarMenuSub>
                      </CollapsibleContent>
                    </Collapsible>
                  ) : (
                    <SidebarMenuButton isActive={isActive(item.href)} onClick={() => router.push(item.href)}>
                      <item.icon className="h-4 w-4" />
                      <span>{item.title}</span>
                    </SidebarMenuButton>
                  )}
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
