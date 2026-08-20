import { ReactNode } from "react";

export default function GuidesLayout({ children }: { children: ReactNode }) {
  return (
    <div className="mx-auto max-w-7xl space-y-6 p-6 md:p-8 animate-in fade-in-50 duration-300">
      {children}
    </div>
  );
}
