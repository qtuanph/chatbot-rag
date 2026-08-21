import { auth } from "@/lib/auth";
import { settingsApi } from "@/lib/api-client";
import { ProviderPage } from "@/components/admin/provider-page";

export default async function EmbeddingPage() {
  const session = await auth();
  const initialProviders = await settingsApi.listProviders("embedding", session?.accessToken).catch(() => []);

  return <ProviderPage serviceType="embedding" initialProviders={initialProviders} />;
}
