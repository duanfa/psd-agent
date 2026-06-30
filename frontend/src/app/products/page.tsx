import { fetchProductsPage } from "@/lib/api";

function formatTime(value: string) {
  return new Date(value).toLocaleString("zh-CN", { hour12: false });
}

export default async function ProductsPage() {
  const data = await fetchProductsPage();
  const product = data.selectedProduct;

  return (
    <div className="data-page">
      <div className="topbar">
        <div className="topbar-left">
          <h1>{data.page.title}</h1>
          <div className="subtitle">{data.page.subtitle}</div>
        </div>
      </div>

      <div className="content-grid-2 content-grid-sidebar">
        <section className="panel content-panel">
          <div className="split-line">
            <h2 className="section-title">商品列表</h2>
            <button className="btn primary" type="button">
              新建商品
            </button>
          </div>
          <div className="table-wrap">
            <table className="simple-table">
              <thead>
                <tr>
                  <th>商品名称</th>
                  <th>分类</th>
                  <th>卖点数</th>
                  <th>素材数</th>
                  <th>最近更新时间</th>
                </tr>
              </thead>
              <tbody>
                {data.products.length ? (
                  data.products.map((item) => (
                    <tr key={item.id}>
                      <td>{item.name}</td>
                      <td>{item.category}</td>
                      <td>{item.sellingPointCount}</td>
                      <td>{item.assetCount}</td>
                      <td>{formatTime(item.updatedAt)}</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td className="table-empty" colSpan={5}>
                      {data.emptyState}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>

        <aside className="panel content-panel">
          <h2 className="section-title">商品信息</h2>
          {product ? (
            <>
              <div className="field">
                <span className="field-label">商品名称</span>
                <input readOnly value={product.name} />
              </div>
              <div className="field">
                <span className="field-label">商品分类</span>
                <input readOnly value={product.category} />
              </div>
              <div className="field">
                <span className="field-label">商品简介</span>
                <textarea readOnly value={product.summary} />
              </div>
            </>
          ) : (
            <div className="placeholder">
              <p>{data.emptyState}</p>
            </div>
          )}
        </aside>
      </div>

      <div className="content-grid-2">
        <section className="panel content-panel">
          <h2 className="section-title">商品素材</h2>
          {product ? (
            <div className="action-grid action-grid-3">
              {product.materials.map((item) => (
                <article className="info-card" key={item}>
                  <div className="placeholder-box">{item}</div>
                </article>
              ))}
            </div>
          ) : (
            <div className="placeholder">
              <p>暂无商品素材可展示。</p>
            </div>
          )}
        </section>

        <section className="panel content-panel">
          <h2 className="section-title">卖点与 Brief</h2>
          {product ? (
            <div className="record-list">
              <div className="record-item">
                <strong>核心卖点</strong>
                <div className="subtitle">{product.sellingPoints.join(" / ")}</div>
              </div>
              <div className="record-item">
                <strong>商品 Brief</strong>
                <div className="subtitle">{product.brief}</div>
              </div>
              <div className="record-item">
                <strong>设计方向</strong>
                <div className="subtitle">{product.designDirection}</div>
              </div>
            </div>
          ) : (
            <div className="placeholder">
              <p>暂无卖点和 Brief 信息。</p>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
