import { auth } from "@/lib/auth";
import { settingsApi } from "@/lib/api-client";
import { ProviderPage } from "@/components/admin/provider-page";

export default async function RerankerPage() {
  const session = await auth();
  const initialProviders = await settingsApi.listProviders("reranker", session?.accessToken).catch(() => []);

  return <ProviderPage serviceType="reranker" initialProviders={initialProviders} />;
}
