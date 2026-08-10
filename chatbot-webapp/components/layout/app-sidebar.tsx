"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import {
  BarChart3Icon,
  Building2Icon,
  ChevronsUpDownIcon,
  FileTextIcon,
  LayoutDashboardIcon,
  CpuIcon,
  Settings2Icon,
  ShieldUserIcon,
  BookOpenIcon,
  MessageSquareIcon,
  HelpCircle,
  CheckIcon,
  CodeIcon,
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

// ── 1. Trang Quản trị (Admin System Mode) Navigation ────────────────────────
const adminNavGroups: NavGroup[] = [
  {
    label: "Hệ thống & Báo cáo",
    items: [
      { title: "Tổng quan Quản trị", href: "/admin", icon: <LayoutDashboardIcon /> },
      { title: "Thống kê & Quota", href: "/admin/analytics", icon: <BarChart3Icon /> },
      { title: "Nhật ký Hỏi & Đáp", href: "/admin/conversations", icon: <MessageSquareIcon /> },
    ],
  },
  {
    label: "Tri thức & Dữ liệu",
    items: [
      { title: "Kho Tài liệu", href: "/admin/documents", icon: <FileTextIcon /> },
      { title: "Quản lý FAQ", href: "/admin/faqs", icon: <HelpCircle /> },
    ],
  },
  {
    label: "Tổ chức & Phân quyền",
    items: [
      { title: "Quản lý Công ty (Tenants)", href: "/admin/tenants", icon: <Building2Icon /> },
      { title: "Quản lý Người dùng", href: "/admin/users", icon: <ShieldUserIcon /> },
    ],
  },
  {
    label: "Cấu hình & Kết nối AI",
    items: [
      {
        title: "Kết nối Provider AI",
        href: "/admin/providers/embedding",
        icon: <CpuIcon />,
        children: [
          { title: "Embedding Engine", href: "/admin/providers/embedding" },
          { title: "Reranker Model", href: "/admin/providers/reranker" },
          { title: "LLM Provider", href: "/admin/providers/llm" },
          { title: "Parser Engine", href: "/admin/providers/parser" },
        ],
      },
      { title: "Cấu hình Hệ thống", href: "/settings", icon: <Settings2Icon /> },
    ],
  },
];

// ── 2. Hướng dẫn sử dụng Phần mềm (User Guides Mode) Navigation ─────────────
const guidesNavGroups: NavGroup[] = [
  {
    label: "Tổng quan & Bắt đầu",
    items: [
      { title: "Giới thiệu Hướng dẫn", href: "/guides/introduction", icon: <BookOpenIcon /> },
      { title: "Tích hợp phần mềm", href: "/guides/integration", icon: <CpuIcon /> },
      { title: "Đặc tả API Enterprise", href: "/guides/api-reference", icon: <CodeIcon /> },
    ],
  },
  {
    label: "Hướng dẫn Quản trị",
    items: [
      { title: "Quản lý Tenants", href: "/guides/tenants", icon: <Building2Icon /> },
      { title: "Nạp & Phân quyền Tài liệu", href: "/guides/documents", icon: <FileTextIcon /> },
      { title: "Cấu hình AI & Providers", href: "/guides/providers", icon: <Settings2Icon /> },
    ],
  },
  {
    label: "Tài liệu Kỹ thuật SAO",
    items: [
      {
        title: "Kỹ thuật & Phân hệ SAO",
        href: "/guides/introduction",
        icon: <FileTextIcon />,
        children: [
          { title: "Tổng quan Kế toán SAO", href: "/guides/introduction" },
          { title: "Tích hợp API Widget", href: "/guides/integration" },
          { title: "Cấu hình Doanh nghiệp", href: "/guides/tenants" },
        ],
      },
    ],
  },
  {
    label: "Trợ giúp & FAQ",
    items: [
      { title: "Câu hỏi thường gặp", href: "/admin/faqs", icon: <HelpCircle /> },
    ],
  },
];

// ── Tenant User Default Navigation ─────────────────────────────────────────
const tenantUserGroups: NavGroup[] = [
  {
    label: "Tài liệu & Hỗ trợ",
    items: [
      { title: "Hướng dẫn sử dụng", href: "/guides/introduction", icon: <BookOpenIcon /> },
    ],
  },
  {
    label: "Workspace",
    items: [
      { title: "Thống kê Sử dụng", href: "/analytics", icon: <BarChart3Icon /> },
      { title: "Nhật ký Hỏi & Đáp", href: "/admin/conversations", icon: <MessageSquareIcon /> },
      { title: "Cài đặt Tenant", href: "/settings", icon: <Settings2Icon /> },
    ],
  },
  {
    label: "Dữ liệu",
    items: [
      { title: "Kho Tài liệu", href: "/documents", icon: <FileTextIcon /> },
    ],
  },
];

interface SidebarModeSwitcherProps {
  currentMode: "admin" | "guides";
  onSelectMode: (mode: "admin" | "guides") => void;
}

function SidebarModeSwitcher({ currentMode, onSelectMode }: SidebarModeSwitcherProps) {
  const { isMobile } = useSidebar();

  const activeTitle = currentMode === "admin" ? "Trang quản trị (Tổng quan)" : "Hướng dẫn sử dụng";
  const activeSubtext = currentMode === "admin" ? "Quản trị Hệ thống RAG" : "Tài liệu & Kỹ thuật Phần mềm";
  const ActiveIcon = currentMode === "admin" ? LayoutDashboardIcon : BookOpenIcon;

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger
            render={
              <SidebarMenuButton size="lg" className="data-open:bg-sidebar-accent data-open:text-sidebar-accent-foreground" />
            }
          >
            <div className="flex aspect-square size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <ActiveIcon className="size-4.5" />
            </div>
            <div className="grid flex-1 text-left text-sm leading-tight group-data-[collapsible=icon]:hidden">
              <span className="truncate font-semibold">{activeTitle}</span>
              <span className="truncate text-xs text-muted-foreground">{activeSubtext}</span>
            </div>
            <ChevronsUpDownIcon className="ml-auto group-data-[collapsible=icon]:hidden text-muted-foreground" />
          </DropdownMenuTrigger>
          <DropdownMenuContent
            className="w-fit min-w-64 rounded-xl p-1.5 shadow-xl border border-border"
            align="start"
            side={isMobile ? "bottom" : "right"}
            sideOffset={4}
          >
            <DropdownMenuGroup>
              <DropdownMenuLabel className="text-xs text-muted-foreground px-2 py-1.5">
                Chuyển chế độ Sidebar
              </DropdownMenuLabel>

              {/* Mode 1: Trang Quản trị */}
              <DropdownMenuItem
                onClick={() => onSelectMode("admin")}
                className="flex items-center justify-between gap-2 px-2.5 py-2 rounded-lg cursor-pointer font-medium text-xs"
              >
                <div className="flex items-center gap-2.5">
                  <div className="p-1.5 rounded-md bg-primary/10 text-primary">
                    <LayoutDashboardIcon className="h-4 w-4" />
                  </div>
                  <div>
                    <div className="font-semibold text-foreground">Trang quản trị (Tổng quan)</div>
                    <div className="text-[11px] text-muted-foreground">Quản lý hệ thống, AI & Tenants</div>
                  </div>
                </div>
                {currentMode === "admin" && <CheckIcon className="h-4 w-4 text-primary shrink-0" />}
              </DropdownMenuItem>

              {/* Mode 2: Hướng dẫn sử dụng */}
              <DropdownMenuItem
                onClick={() => onSelectMode("guides")}
                className="flex items-center justify-between gap-2 px-2.5 py-2 rounded-lg cursor-pointer font-medium text-xs mt-1"
              >
                <div className="flex items-center gap-2.5">
                  <div className="p-1.5 rounded-md bg-amber-500/10 text-amber-600 dark:text-amber-400">
                    <BookOpenIcon className="h-4 w-4" />
                  </div>
                  <div>
                    <div className="font-semibold text-foreground">Hướng dẫn sử dụng Phần mềm</div>
                    <div className="text-[11px] text-muted-foreground">Tài liệu kỹ thuật & Hướng dẫn SAO</div>
                  </div>
                </div>
                {currentMode === "guides" && <CheckIcon className="h-4 w-4 text-primary shrink-0" />}
              </DropdownMenuItem>
            </DropdownMenuGroup>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  );
}

export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
  const { data: session } = useSession();
  const pathname = usePathname();
  const router = useRouter();

  // Mode state: 'admin' | 'guides'
  const [sidebarMode, setSidebarMode] = React.useState<"admin" | "guides">("admin");

  // Auto-detect mode based on current URL path
  React.useEffect(() => {
    if (pathname.startsWith("/guides")) {
      setSidebarMode("guides");
    } else if (pathname.startsWith("/admin") || pathname.startsWith("/settings")) {
      setSidebarMode("admin");
    }
  }, [pathname]);

  const handleSelectMode = (mode: "admin" | "guides") => {
    setSidebarMode(mode);
    if (mode === "admin") {
      router.push("/admin");
    } else {
      router.push("/guides/introduction");
    }
  };

  const isPlatformAdmin = session?.role === "platform_admin";

  let activeGroups: NavGroup[];
  if (!isPlatformAdmin) {
    activeGroups = tenantUserGroups;
  } else {
    activeGroups = sidebarMode === "guides" ? guidesNavGroups : adminNavGroups;
  }

  return (
    <Sidebar collapsible="icon" variant="inset" {...props}>
      <SidebarHeader>
        <SidebarModeSwitcher currentMode={sidebarMode} onSelectMode={handleSelectMode} />
      </SidebarHeader>

      <SidebarContent>
        <NavMain groups={activeGroups} />
      </SidebarContent>

      <SidebarFooter>
        <NavUser />
      </SidebarFooter>
      
      <SidebarRail />
    </Sidebar>
  );
}
