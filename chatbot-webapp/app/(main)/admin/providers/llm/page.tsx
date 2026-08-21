import { auth } from "@/lib/auth";
import { settingsApi } from "@/lib/api-client";
import { ProviderPage } from "@/components/admin/provider-page";

export default async function LlmPage() {
  const session = await auth();
  const initialProviders = await settingsApi.listProviders("llm", session?.accessToken).catch(() => []);

  return <ProviderPage serviceType="llm" initialProviders={initialProviders} />;
}
