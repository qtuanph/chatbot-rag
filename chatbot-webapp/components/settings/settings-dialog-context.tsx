"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

export type SettingsTab = "general" | "account" | "system" | "security";

interface SettingsDialogContextType {
  open: boolean;
  setOpen: (open: boolean) => void;
  activeTab: SettingsTab;
  setActiveTab: (tab: SettingsTab) => void;
  openSettings: (tab?: SettingsTab) => void;
}

const SettingsDialogContext = createContext<SettingsDialogContextType | undefined>(undefined);

export function SettingsDialogProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<SettingsTab>("general");

  const openSettings = (tab?: SettingsTab) => {
    if (tab) setActiveTab(tab);
    setOpen(true);
  };

  // Keyboard shortcut: Cmd+S / Ctrl+S or Cmd+, / Ctrl+,
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && (e.key === "s" || e.key === ",")) {
        e.preventDefault();
        setOpen((prev) => !prev);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  return (
    <SettingsDialogContext.Provider value={{ open, setOpen, activeTab, setActiveTab, openSettings }}>
      {children}
    </SettingsDialogContext.Provider>
  );
}

export function useSettingsDialog() {
  const context = useContext(SettingsDialogContext);
  if (!context) {
    return {
      open: false,
      setOpen: () => {},
      activeTab: "general" as SettingsTab,
      setActiveTab: () => {},
      openSettings: () => {},
    };
  }
  return context;
}
