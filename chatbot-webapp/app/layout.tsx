import type { Metadata } from "next";
import { Suspense } from "react";

export const runtime = "edge";
import { Inter, Geist_Mono } from "next/font/google";
import { SessionProvider } from "next-auth/react";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  display: "swap",
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "RAG Platform",
  description: "Nền tảng hỏi đáp tài liệu đa tenant cho doanh nghiệp",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="vi" suppressHydrationWarning data-scroll-behavior="smooth">
      <body
        className={`${inter.variable} ${geistMono.variable} font-sans antialiased`}
      >
        <SessionProvider>
          <TooltipProvider>
            <Suspense>
              {children}
            </Suspense>
            <Toaster richColors position="top-right" />
          </TooltipProvider>
        </SessionProvider>
      </body>
    </html>
  );
}
