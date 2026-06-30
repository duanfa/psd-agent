"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_ITEMS = [
  { href: "/dashboard", label: "工作台" },
  { href: "/brand-assets", label: "品牌资产" },
  { href: "/brand-rules", label: "品牌规则" },
  { href: "/products", label: "商品管理" },
  { href: "/create-task", label: "创建设计任务", aliases: ["/"] },
  { href: "/design-tasks", label: "设计任务" },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Link className="brand-block" href="/create-task">
          <div className="brand-logo">B</div>
          <div>
            <div className="brand-name">BrandOS AI</div>
            <div className="brand-subtitle">电商设计平台</div>
          </div>
        </Link>

        <div className="nav-section-title">业务端</div>
        <nav className="nav-list" aria-label="业务端导航">
          {NAV_ITEMS.map((item) => {
            const active =
              pathname === item.href ||
              item.aliases?.includes(pathname) ||
              (item.href !== "/" && pathname.startsWith(`${item.href}/`));
            return (
              <Link
                className={`nav-link ${active ? "active" : ""}`}
                href={item.href}
                key={item.href}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
      </aside>

      <div className="main">{children}</div>
    </div>
  );
}
