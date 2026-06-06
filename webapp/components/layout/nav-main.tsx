"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { ChevronRightIcon } from "lucide-react";

import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import {
  SidebarGroup,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
} from "@/components/ui/sidebar";

type NavChild = {
  title: string;
  href: string;
};

type NavItem = {
  title: string;
  href: string;
  icon?: React.ReactNode;
  children?: NavChild[];
};

function isPathActive(pathname: string, href: string) {
  if (href === "/admin") {
    return pathname === "/admin";
  }

  return pathname === href || pathname.startsWith(`${href}/`);
}

export function NavMain({
  label,
  items,
}: {
  label: string;
  items: NavItem[];
}) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const currentTab = searchParams.get("tab") || "embedding";

  return (
    <SidebarGroup>
      <SidebarGroupLabel>{label}</SidebarGroupLabel>
      <SidebarMenu>
        {items.map((item) => {
          if (!item.children?.length) {
            return (
              <SidebarMenuItem key={item.href}>
                <SidebarMenuButton isActive={isPathActive(pathname, item.href)} tooltip={item.title} render={<Link href={item.href} />}>
                  {item.icon}
                  <span>{item.title}</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
            );
          }

          const groupActive = pathname === "/admin/providers";

          return (
            <Collapsible key={item.href} defaultOpen={groupActive} className="group/collapsible" render={<SidebarMenuItem />}>
              <CollapsibleTrigger render={<SidebarMenuButton tooltip={item.title} isActive={groupActive} />}>
                {item.icon}
                <span>{item.title}</span>
                <ChevronRightIcon className="ml-auto transition-transform duration-200 group-data-open/collapsible:rotate-90" />
              </CollapsibleTrigger>
              <CollapsibleContent>
                <SidebarMenuSub>
                  {item.children.map((subItem) => {
                    const childTab = new URLSearchParams(subItem.href.split("?")[1] || "").get("tab") || "embedding";

                    return (
                      <SidebarMenuSubItem key={subItem.href}>
                        <SidebarMenuSubButton
                          isActive={pathname === "/admin/providers" && currentTab === childTab}
                          render={<Link href={subItem.href} />}
                        >
                          <span>{subItem.title}</span>
                        </SidebarMenuSubButton>
                      </SidebarMenuSubItem>
                    );
                  })}
                </SidebarMenuSub>
              </CollapsibleContent>
            </Collapsible>
          );
        })}
      </SidebarMenu>
    </SidebarGroup>
  );
}
