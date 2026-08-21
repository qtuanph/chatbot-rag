import { auth } from "@/lib/auth";
import { settingsApi } from "@/lib/api-client";
import { SettingsManager } from "@/components/settings/settings-manager";

export default async function SettingsPage() {
  const session = await auth();
  const isPlatformAdmin = session?.role === "platform_admin";
  const initialBilling = isPlatformAdmin
    ? await settingsApi.getBilling(session?.accessToken).catch(() => null)
    : null;

  return <SettingsManager initialBilling={initialBilling} />;
}
