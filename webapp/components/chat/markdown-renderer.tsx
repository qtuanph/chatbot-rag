"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

interface MarkdownRendererProps {
  content: string;
  showCursor?: boolean;
}

export function MarkdownRenderer({ content, showCursor = false }: MarkdownRendererProps) {
  return (
    <div className="prose prose-sm dark:prose-invert max-w-none prose-p:my-1 prose-headings:my-2 prose-ul:my-1 prose-ol:my-1 prose-li:my-0.5 prose-pre:my-2 prose-table:my-2">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          pre({ children }) {
            return (
              <pre className="rounded-md bg-zinc-900 text-zinc-100 p-3 overflow-x-auto text-xs">
                {children}
              </pre>
            );
          },
          code({ className, children, ...props }) {
            const isInline = !className;
            if (isInline) {
              return (
                <code className="bg-muted px-1 py-0.5 rounded text-xs font-mono" {...props}>
                  {children}
                </code>
              );
            }
            return (
              <code className={`${className} text-xs`} {...props}>
                {children}
              </code>
            );
          },
          table({ children }) {
            return (
              <Table className="my-2 text-xs">{children}</Table>
            );
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
            return <TableHead className="bg-muted font-medium text-left">{children}</TableHead>;
          },
          td({ children }) {
            return <TableCell>{children}</TableCell>;
          },
        }}
      >
        {content}
      </ReactMarkdown>
      {showCursor && <span className="inline-block w-0.5 h-4 bg-foreground/70 ml-0.5 align-text-bottom animate-pulse" />}
    </div>
  );
}
