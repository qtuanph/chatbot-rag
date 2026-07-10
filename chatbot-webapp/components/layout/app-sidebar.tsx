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
  CpuIcon,
  Settings2Icon,
  ShieldUserIcon,
  BookOpenIcon,
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

import type { NavGroup } from "@/components/layout/nav-main";

const platformGroups: NavGroup[] = [
  {
    label: "Tài liệu & Hỗ trợ",
    items: [
      {
        title: "Hướng dẫn sử dụng",
        href: "/guides/introduction",
        icon: <BookOpenIcon />,
        children: [
          { title: "Giới thiệu chung", href: "/guides/introduction" },
          { title: "Quản lý Tenant", href: "/guides/tenants" },
          { title: "Quản lý Tài liệu", href: "/guides/documents" },
          { title: "Tích hợp phần mềm", href: "/guides/integration" },
          { title: "Cấu hình AI & Model", href: "/guides/providers" },
        ],
      },
    ],
  },
  {
    label: "Hệ thống",
    items: [
      { title: "Tổng quan", href: "/admin", icon: <LayoutDashboardIcon /> },
      { title: "Cài đặt", href: "/settings", icon: <Settings2Icon /> },
    ],
  },
  {
    label: "Quản trị",
    items: [
      { title: "Tenant", href: "/admin/tenants", icon: <Building2Icon /> },
      { title: "Người dùng", href: "/admin/users", icon: <ShieldUserIcon /> },
      { title: "Thống kê", href: "/admin/analytics", icon: <BarChart3Icon /> },
    ],
  },
  {
    label: "Dữ liệu & AI",
    items: [
      { title: "Tài liệu", href: "/admin/documents", icon: <FileTextIcon /> },
      {
        title: "Kết nối AI",
        href: "/admin/providers/embedding",
        icon: <CpuIcon />,
        children: [
          { title: "Embedding", href: "/admin/providers/embedding" },
          { title: "Reranker", href: "/admin/providers/reranker" },
          { title: "LLM", href: "/admin/providers/llm" },
          { title: "Parser Engine", href: "/admin/providers/parser" },
        ],
      },
    ],
  },
];

const tenantGroups: NavGroup[] = [
  {
    label: "Tài liệu & Hỗ trợ",
    items: [
      {
        title: "Hướng dẫn sử dụng",
        href: "/guides/introduction",
        icon: <BookOpenIcon />,
        children: [
          { title: "Giới thiệu chung", href: "/guides/introduction" },
          { title: "Quản lý Tài liệu", href: "/guides/documents" },
          { title: "Tích hợp phần mềm", href: "/guides/integration" },
        ],
      },
    ],
  },
  {
    label: "Workspace",
    items: [
      { title: "Thống kê", href: "/analytics", icon: <BarChart3Icon /> },
      { title: "Cài đặt tenant", href: "/settings", icon: <Settings2Icon /> },
    ],
  },
  {
    label: "Dữ liệu & AI",
    items: [
      { title: "Tài liệu", href: "/documents", icon: <FileTextIcon /> },
    ],
  },
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
              <span className="truncate text-xs text-muted-foreground">{process.env.NEXT_PUBLIC_APP_VERSION || "v1.0"}</span>
            </div>
            <ChevronsUpDownIcon className="ml-auto group-data-[collapsible=icon]:hidden" />
          </DropdownMenuTrigger>
          <DropdownMenuContent className="w-fit min-w-56 rounded-lg" align="start" side={isMobile ? "bottom" : "right"} sideOffset={4}>
            <DropdownMenuGroup>
              <DropdownMenuLabel className="text-xs text-muted-foreground">Điều hướng nhanh</DropdownMenuLabel>
              <DropdownMenuItem render={<Link href="/admin" />}>Trang quản trị</DropdownMenuItem>
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

  const groups = session?.role === "platform_admin" ? platformGroups : tenantGroups;

  return (
    <Sidebar collapsible="icon" variant="inset" {...props}>
      <SidebarHeader>
        <PlatformSwitcher />
      </SidebarHeader>
      <SidebarContent>
        <NavMain groups={groups} />
      </SidebarContent>
      <SidebarFooter>
        <NavUser />
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}
