import { ReactNode } from "react";

export default function GuidesLayout({ children }: { children: ReactNode }) {
  return (
    <div className="mx-auto max-w-7xl space-y-6 p-6">
      {children}
    </div>
  );
}
