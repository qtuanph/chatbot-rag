import { Suspense } from "react";

import { AppSidebar } from "@/components/layout/app-sidebar";
import { Separator } from "@/components/ui/separator";
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";

export default function MainLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <SidebarProvider className="h-svh overflow-hidden bg-background transition-colors duration-300">
      <Suspense>
        <AppSidebar />
      </Suspense>
      <SidebarInset>
        <header className="sticky top-0 z-20 flex h-12 shrink-0 items-center gap-2 border-b border-border/70 bg-background/85 px-4 backdrop-blur-xl supports-[backdrop-filter]:bg-background/70">
          <SidebarTrigger className="-ml-1 transition-transform duration-200 hover:scale-[1.02] active:scale-[0.98]" />
          <Separator orientation="vertical" className="h-4" />
          <div className="flex-1 overflow-hidden">
            <h1 className="truncate text-sm font-medium">RAG Platform</h1>
          </div>
        </header>
        <main className="flex-1 overflow-auto bg-background">
          <div className="animate-in fade-in slide-in-from-bottom-1 duration-300">
            <Suspense>{children}</Suspense>
          </div>
        </main>
      </SidebarInset>
    </SidebarProvider>
  );
}
