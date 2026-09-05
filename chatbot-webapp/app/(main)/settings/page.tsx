"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useSettingsDialog } from "@/components/settings/settings-dialog-context";

export default function SettingsPage() {
  const router = useRouter();
  const { openSettings } = useSettingsDialog();

  useEffect(() => {
    openSettings();
    router.replace("/admin");
  }, [openSettings, router]);

  return null;
}
