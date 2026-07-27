import { ProviderPage } from "@/components/admin/provider-page";
import { Metadata } from "next";

export const metadata: Metadata = {
  title: "Parser Engines",
};

export default function ParserProvidersPage() {
  return <ProviderPage serviceType="parser" />;
}
