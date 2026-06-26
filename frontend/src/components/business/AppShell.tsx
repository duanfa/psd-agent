"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { ArrowRight, BarChart3, FolderKanban, GitBranch, ListTodo, WandSparkles } from "lucide-react";
import type { BrandRecord } from "@/lib/api";

const NAV_ITEMS = [
  { href: "/workspace", label: "工作台", icon: BarChart3 },
  { href: "/assets", label: "品牌资产", icon: FolderKanban },
  { href: "/rules", label: "品牌规则", icon: GitBranch },
  { href: "/tasks/new", label: "创建设计任务", icon: WandSparkles },
  { href: "/tasks", label: "设计任务", icon: ListTodo },
];

function isActive(pathname: string, href: string): boolean {
  if (href === "/tasks") {
    return pathname === "/tasks" || pathname.startsWith("/tasks/");
  }
  return pathname === href;
}

interface AppShellProps {
  title: string;
  subtitle: string;
  brands: BrandRecord[];
  selectedBrandId: string | null;
  selectedBrand?: BrandRecord | null;
  loadingBrands?: boolean;
  onBrandChange: (brandId: string) => void;
  buildHref: (href: string) => string;
  headerActions?: ReactNode;
  children: ReactNode;
}

export function AppShell({
  title,
  subtitle,
  brands,
  selectedBrandId,
  selectedBrand,
  loadingBrands = false,
  onBrandChange,
  buildHref,
  headerActions,
  children,
}: AppShellProps) {
  const pathname = usePathname();

  return (
    <main className="app-shell">
      <aside className="app-sidebar">
        <Link className="app-wordmark" href={buildHref("/workspace")}>
          brandos
        </Link>

        <nav className="app-nav app-nav-vertical">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const active = isActive(pathname, item.href);
            return (
              <Link
                className={`app-nav-link ${active ? "app-nav-link-active" : ""}`}
                href={buildHref(item.href)}
                key={item.href}
              >
                <Icon size={14} />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        <div className="app-site-actions app-site-actions-vertical">
          <label className="app-brand-picker">
            <span>所属品牌</span>
            <select
              value={selectedBrandId ?? ""}
              onChange={(event) => event.target.value && onBrandChange(event.target.value)}
              disabled={loadingBrands || !brands.length}
            >
              {brands.map((brand) => (
                <option key={brand.id} value={brand.id}>
                  {brand.name}
                </option>
              ))}
            </select>
          </label>
          {headerActions}
        </div>
      </aside>

      <section className="app-main">
        <section className="app-hero">
          <div className="app-hero-copy">
            <div className="app-hero-eyebrow">{selectedBrand?.code || "brand operating system"}</div>
            <h1>{title}</h1>
            <p>{subtitle}</p>
          </div>

          <div className="app-hero-panel">
            <div className="app-hero-panel-label">当前品牌空间</div>
            <div className="app-hero-panel-title">{selectedBrand?.name ?? "未选择品牌"}</div>
            <p>{selectedBrand?.description || "选择品牌后即可查看资产、规则和任务数据。"}</p>
            <Link className="text-link" href={buildHref("/tasks/new")}>
              发起设计任务 <ArrowRight size={14} />
            </Link>
          </div>
        </section>

        <section className="app-content">{children}</section>
      </section>
    </main>
  );
}
