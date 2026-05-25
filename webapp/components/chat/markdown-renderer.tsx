"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

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
              <div className="overflow-x-auto my-2">
                <table className="border-collapse border border-border text-xs">{children}</table>
              </div>
            );
          },
          th({ children }) {
            return <th className="border border-border px-2 py-1 bg-muted font-medium text-left">{children}</th>;
          },
          td({ children }) {
            return <td className="border border-border px-2 py-1">{children}</td>;
          },
        }}
      >
        {content}
      </ReactMarkdown>
      {showCursor && <span className="inline-block w-0.5 h-4 bg-foreground/70 ml-0.5 align-text-bottom animate-pulse" />}
    </div>
  );
}

