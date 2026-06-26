import { BrandAssetsPageClient } from "@/components/BrandAssetsPageClient";
import { fetchBrandAssetsPage } from "@/lib/api";

export default async function BrandAssetsPage() {
  const data = await fetchBrandAssetsPage();
  return <BrandAssetsPageClient initialData={data} />;
}
