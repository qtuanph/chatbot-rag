import { auth } from "@/lib/auth";
import { settingsApi } from "@/lib/api-client";
import { ProviderPage } from "@/components/admin/provider-page";

export default async function ParserPage() {
  const session = await auth();
  const initialProviders = await settingsApi.listProviders("parser", session?.accessToken).catch(() => []);

  return <ProviderPage serviceType="parser" initialProviders={initialProviders} />;
}
