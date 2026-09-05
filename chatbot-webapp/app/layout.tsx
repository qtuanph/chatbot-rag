import type { Metadata } from "next";
import { Suspense } from "react";
import { Inter, Geist_Mono } from "next/font/google";
import { SessionProvider } from "next-auth/react";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { SettingsDialog } from "@/components/settings/settings-dialog";
import { SettingsDialogProvider } from "@/components/settings/settings-dialog-context";
import { ThemeProvider } from "@/components/theme-provider";
import "./globals.css";
import { cn } from "@/lib/utils";

const inter = Inter({subsets:['latin'],variable:'--font-sans'});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: { default: "SSE Chatbot", template: "%s | SSE Chatbot" },
  description: "Nền tảng hỏi đáp tài liệu đa tenant cho doanh nghiệp",
  openGraph: {
    title: "SSE Chatbot",
    description: "Nền tảng hỏi đáp tài liệu đa tenant cho doanh nghiệp",
    type: "website",
    locale: "vi_VN",
  },
  icons: { icon: "/favicon.ico" },
  robots: { index: true, follow: true },
};

export const viewport = {
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="vi" suppressHydrationWarning data-scroll-behavior="smooth" className={cn("font-sans", inter.variable)}>
      <body
        className={`${inter.variable} ${geistMono.variable} font-sans antialiased`}
      >
        <SessionProvider>
          <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
            <TooltipProvider>
              <SettingsDialogProvider>
                <Suspense>
                  {children}
                </Suspense>
                <SettingsDialog />
                <Toaster richColors position="top-right" />
              </SettingsDialogProvider>
            </TooltipProvider>
          </ThemeProvider>
        </SessionProvider>
      </body>
    </html>
  );
}
