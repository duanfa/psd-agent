"use client";

import { useState } from "react";
import {
  fetchBrandRulesPageWithFilters,
  type BrandRulesPageResponse,
} from "@/lib/api";

export function BrandRulesPageClient({ initialData }: { initialData: BrandRulesPageResponse }) {
  const [data, setData] = useState(initialData);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleBrandChange = async (brandId: number) => {
    if (brandId === data.selectedBrand.id) return;
    setLoading(true);
    setError(null);
    try {
      const next = await fetchBrandRulesPageWithFilters({ brandId });
      setData(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="data-page">
      <div className="topbar">
        <div className="topbar-left">
          <h1>{data.page.title}</h1>
          <div className="subtitle">{data.page.subtitle}</div>
        </div>
        <div className="topbar-right">
          <button className="btn ghost" type="button">
            切换版本
          </button>
          <button className="btn primary" type="button">
            重新训练
          </button>
        </div>
      </div>

      <div className="rules-layout">
        <aside className="assets-brand-panel">
          <div className="assets-panel-title">品牌规则列表</div>
          <div className="assets-brand-list">
            {data.brands.map((brand) => (
              <button
                className={`assets-brand-item ${
                  brand.id === data.selectedBrand.id ? "active" : ""
                }`}
                key={brand.id}
                type="button"
                onClick={() => handleBrandChange(brand.id)}
              >
                <span>
                  <strong>{brand.name}</strong>
                  <small>
                    {brand.status} / {brand.version}
                  </small>
                </span>
                <em>{brand.ruleCount}</em>
              </button>
            ))}
          </div>
        </aside>

        <div className="rules-main">
          <section className="summary-grid">
            {data.overview.map((item) => (
              <article className="info-card" key={item.label}>
                <div className="eyebrow">{item.label}</div>
                <div className="big-metric">{item.value}</div>
                <div className="muted-text">{item.description}</div>
              </article>
            ))}
          </section>

          {error ? <div className="error">{error}</div> : null}
          {loading ? <div className="hint">正在加载品牌规则...</div> : null}
          {data.emptyState ? (
            <section className="panel content-panel">
              <div className="placeholder">
                <p>{data.emptyState}</p>
              </div>
            </section>
          ) : (
            <>
              <div className="content-grid-2">
                <section className="panel content-panel">
                  <div className="split-line">
                    <h2 className="section-title">设计规则说明</h2>
                    <span className="tag">当前品牌：{data.selectedBrand.name}</span>
                  </div>
                  <div className="record-list">
                    {data.designRules.map((item) => (
                      <div className="record-item" key={item.title}>
                        <strong>{item.title}</strong>
                        <div className="subtitle">{item.description}</div>
                      </div>
                    ))}
                  </div>
                </section>

                <section className="panel content-panel">
                  <h2 className="section-title">布局规则摘要</h2>
                  <div className="record-list">
                    {data.layoutRules.map((item) => (
                      <div className="record-item" key={item.title}>
                        <strong>{item.title}</strong>
                        <div className="subtitle">{item.description}</div>
                      </div>
                    ))}
                  </div>
                </section>
              </div>

              <div className="content-grid-2">
                <section className="panel content-panel">
                  <h2 className="section-title">组件库摘要</h2>
                  <div className="action-grid action-grid-3">
                    {data.components.map((item) => (
                      <article className="info-card" key={item.title}>
                        <div className="placeholder-box">{item.title}</div>
                        <p>{item.description}</p>
                      </article>
                    ))}
                  </div>
                </section>

                <section className="panel content-panel">
                  <h2 className="section-title">Prompt 模板摘要</h2>
                  <div className="record-list">
                    {data.promptTemplates.map((item) => (
                      <div className="record-item" key={item.title}>
                        <strong>{item.title}</strong>
                        <div className="subtitle">{item.description}</div>
                      </div>
                    ))}
                  </div>
                </section>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
