"use client";

import Link from "next/link";
import { useSession } from "next-auth/react";
import {
  BarChart3Icon,
  BotIcon,
  Building2Icon,
  ChevronsUpDownIcon,
  FileTextIcon,
  LayoutDashboardIcon,
  MessageSquareIcon,
  PlugIcon,
  Settings2Icon,
  ShieldUserIcon,
} from "lucide-react";

import { NavMain } from "@/components/layout/nav-main";
import { NavUser } from "@/components/layout/nav-user";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
  useSidebar,
} from "@/components/ui/sidebar";

const platformItems = [
  { title: "Tổng quan", href: "/admin", icon: <LayoutDashboardIcon /> },
  { title: "Tenant", href: "/admin/tenants", icon: <Building2Icon /> },
  { title: "Tài liệu", href: "/admin/documents", icon: <FileTextIcon /> },
  { title: "Người dùng", href: "/admin/users", icon: <ShieldUserIcon /> },
  { title: "Thống kê", href: "/admin/analytics", icon: <BarChart3Icon /> },
  {
    title: "Kết nối AI",
    href: "/admin/providers",
    icon: <PlugIcon />,
    children: [
      { title: "Embedding", href: "/admin/providers?tab=embedding" },
      { title: "Reranker", href: "/admin/providers?tab=reranker" },
      { title: "LLM", href: "/admin/providers?tab=llm" },
    ],
  },
  { title: "Chat test", href: "/chat", icon: <MessageSquareIcon /> },
  { title: "Cài đặt", href: "/settings", icon: <Settings2Icon /> },
];

const tenantItems = [
  { title: "Chat test", href: "/chat", icon: <MessageSquareIcon /> },
  { title: "Tài liệu", href: "/documents", icon: <FileTextIcon /> },
  { title: "Thống kê", href: "/analytics", icon: <BarChart3Icon /> },
  { title: "Cài đặt tenant", href: "/settings", icon: <Settings2Icon /> },
];

function PlatformSwitcher() {
  const { isMobile } = useSidebar();

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger
            render={
              <SidebarMenuButton size="lg" className="data-open:bg-sidebar-accent data-open:text-sidebar-accent-foreground" />
            }
          >
            <div className="flex aspect-square size-8 items-center justify-center rounded-lg bg-sidebar-primary text-sidebar-primary-foreground">
              <BotIcon />
            </div>
            <div className="grid flex-1 text-left text-sm leading-tight group-data-[collapsible=icon]:hidden">
              <span className="truncate font-medium">RAG Platform</span>
              <span className="truncate text-xs text-muted-foreground">Nền tảng quản trị</span>
            </div>
            <ChevronsUpDownIcon className="ml-auto group-data-[collapsible=icon]:hidden" />
          </DropdownMenuTrigger>
          <DropdownMenuContent className="w-fit min-w-56 rounded-lg" align="start" side={isMobile ? "bottom" : "right"} sideOffset={4}>
            <DropdownMenuGroup>
              <DropdownMenuLabel className="text-xs text-muted-foreground">Điều hướng nhanh</DropdownMenuLabel>
              <DropdownMenuItem render={<Link href="/admin" />}>Trang quản trị</DropdownMenuItem>
              <DropdownMenuItem render={<Link href="/chat" />}>Chat test</DropdownMenuItem>
              <DropdownMenuItem render={<Link href="/settings" />}>Cài đặt</DropdownMenuItem>
            </DropdownMenuGroup>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  );
}

export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
  const { data: session } = useSession();

  const items = session?.role === "platform_admin" ? platformItems : tenantItems;
  const label = session?.role === "platform_admin" ? "Platform" : "Tenant";

  return (
    <Sidebar collapsible="icon" variant="inset" {...props}>
      <SidebarHeader>
        <PlatformSwitcher />
      </SidebarHeader>
      <SidebarContent>
        <NavMain label={label} items={items} />
      </SidebarContent>
      <SidebarFooter>
        <NavUser />
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}
