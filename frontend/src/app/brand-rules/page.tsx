import { BrandRulesPageClient } from "@/components/BrandRulesPageClient";
import { fetchBrandRulesPage } from "@/lib/api";

export default async function BrandRulesPage() {
  const data = await fetchBrandRulesPage();
  return <BrandRulesPageClient initialData={data} />;
}
