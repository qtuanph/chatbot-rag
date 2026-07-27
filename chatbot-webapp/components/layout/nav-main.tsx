"use client";

import { useState } from "react";

import Link from "next/link";
import { usePathname } from "next/navigation";
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

function NavCollapsibleItem({ item, pathname }: { item: NavItem; pathname: string }) {
  const isActive = isPathActive(pathname, item.href);
  const [open, setOpen] = useState(isActive);

  return (
    <Collapsible open={open} onOpenChange={setOpen} className="group/collapsible" render={<SidebarMenuItem />}>
      <CollapsibleTrigger render={<SidebarMenuButton tooltip={item.title} isActive={isActive} />}>
        {item.icon}
        <span>{item.title}</span>
        <ChevronRightIcon className="ml-auto transition-transform duration-200 group-data-open/collapsible:rotate-90" />
      </CollapsibleTrigger>
      <CollapsibleContent>
        <SidebarMenuSub>
          {item.children!.map((subItem) => (
            <SidebarMenuSubItem key={subItem.href}>
              <SidebarMenuSubButton
                isActive={pathname === subItem.href}
                render={<Link href={subItem.href} />}
              >
                <span>{subItem.title}</span>
              </SidebarMenuSubButton>
            </SidebarMenuSubItem>
          ))}
        </SidebarMenuSub>
      </CollapsibleContent>
    </Collapsible>
  );
}

export type NavGroup = {
  label: string;
  items: NavItem[];
};

export function NavMain({
  groups,
}: {
  groups: NavGroup[];
}) {
  const pathname = usePathname();

  return (
    <>
      {groups.map((group) => (
        <SidebarGroup key={group.label}>
          <SidebarGroupLabel>{group.label}</SidebarGroupLabel>
          <SidebarMenu>
            {group.items.map((item) => {
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

              return <NavCollapsibleItem key={item.href} item={item} pathname={pathname} />;
            })}
          </SidebarMenu>
        </SidebarGroup>
      ))}
    </>
  );
}
