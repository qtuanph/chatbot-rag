"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { Separator } from "@/components/ui/separator";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { cn } from "@/lib/utils";

interface MarkdownRendererProps {
  content: string;
  showCursor?: boolean;
}

export function MarkdownRenderer({ content, showCursor = false }: MarkdownRendererProps) {
  return (
    <div
      className={cn(
        "prose dark:prose-invert max-w-none text-[15px] leading-7 text-foreground",
        "prose-p:my-3 prose-p:leading-7",
        "prose-p:first:mt-0 prose-p:last:mb-0",
        "prose-headings:mb-3 prose-headings:mt-6 prose-headings:font-semibold",
        "prose-headings:tracking-tight prose-headings:text-foreground",
        "prose-h1:text-2xl prose-h2:text-xl prose-h3:text-lg",
        "prose-ul:my-3 prose-ol:my-3 prose-li:my-1.5",
        "prose-strong:font-semibold prose-code:font-medium",
        "prose-pre:my-4 prose-table:my-4",
      )}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          pre({ children }) {
            return (
              <pre className="overflow-x-auto rounded-xl border border-border bg-foreground px-4 py-3.5 text-[13px] leading-6 text-background shadow-sm">
                {children}
              </pre>
            );
          },
          code({ className, children, ...props }) {
            const isInline = !className;
            if (isInline) {
              return (
                <code className="rounded-md bg-muted px-1.5 py-0.5 text-[0.9em] font-mono text-foreground" {...props}>
                  {children}
                </code>
              );
            }
            return (
              <code className={`${className} text-[13px]`} {...props}>
                {children}
              </code>
            );
          },
          table({ children }) {
            return <Table className="my-4 min-w-full text-sm">{children}</Table>;
          },
          thead({ children }) {
            return <TableHeader>{children}</TableHeader>;
          },
          tbody({ children }) {
            return <TableBody>{children}</TableBody>;
          },
          tr({ children }) {
            return <TableRow>{children}</TableRow>;
          },
          th({ children }) {
            return <TableHead className="h-11 px-3 text-[12px] font-semibold uppercase tracking-wide text-muted-foreground">{children}</TableHead>;
          },
          td({ children }) {
            return <TableCell className="px-3 py-2.5 text-[14px] leading-6 whitespace-normal">{children}</TableCell>;
          },
          blockquote({ children }) {
            return (
              <blockquote className="my-4 border-l-4 border-primary/30 bg-muted/40 px-4 py-3 text-[14px] italic text-muted-foreground">
                {children}
              </blockquote>
            );
          },
          hr() {
            return <Separator className="my-5" />;
          },
        }}
      >
        {content}
      </ReactMarkdown>
      {showCursor && <span className="inline-block w-0.5 h-4 bg-foreground/70 ml-0.5 align-text-bottom animate-pulse" />}
    </div>
  );
}
