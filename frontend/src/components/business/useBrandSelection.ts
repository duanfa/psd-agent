"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchBrands, type BrandRecord } from "@/lib/api";

function buildUrl(pathname: string, searchParams: URLSearchParams): string {
  const query = searchParams.toString();
  return query ? `${pathname}?${query}` : pathname;
}

function mergeHrefWithBrand(href: string, brandId: string): string {
  const [pathname, rawQuery = ""] = href.split("?");
  const next = new URLSearchParams(rawQuery);
  next.set("brand", brandId);
  return buildUrl(pathname, next);
}

export function useBrandSelection() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [brands, setBrands] = useState<BrandRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refreshBrands = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const items = await fetchBrands();
      setBrands(items);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshBrands();
  }, [refreshBrands]);

  const selectedBrandId = useMemo(() => {
    const fromQuery = searchParams.get("brand");
    if (fromQuery && brands.some((brand) => brand.id === fromQuery)) {
      return fromQuery;
    }
    return brands[0]?.id ?? null;
  }, [brands, searchParams]);

  const selectedBrand = useMemo(
    () => brands.find((brand) => brand.id === selectedBrandId) ?? null,
    [brands, selectedBrandId],
  );

  useEffect(() => {
    if (loading || !selectedBrandId) return;
    if (searchParams.get("brand") === selectedBrandId) return;
    const next = new URLSearchParams(searchParams.toString());
    next.set("brand", selectedBrandId);
    router.replace(buildUrl(pathname, next));
  }, [loading, pathname, router, searchParams, selectedBrandId]);

  const setSelectedBrandId = useCallback(
    (brandId: string) => {
      const next = new URLSearchParams(searchParams.toString());
      next.set("brand", brandId);
      router.push(buildUrl(pathname, next));
    },
    [pathname, router, searchParams],
  );

  const buildHref = useCallback(
    (href: string) => {
      if (!selectedBrandId) return href;
      return mergeHrefWithBrand(href, selectedBrandId);
    },
    [selectedBrandId],
  );

  return {
    brands,
    selectedBrand,
    selectedBrandId,
    loading,
    error,
    refreshBrands,
    setSelectedBrandId,
    buildHref,
  };
}
