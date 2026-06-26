interface EmptyPageProps {
  title: string;
  subtitle: string;
}

export function EmptyPage({ title, subtitle }: EmptyPageProps) {
  return (
    <div className="empty-page">
      <div className="topbar">
        <div className="topbar-left">
          <h1>{title}</h1>
          <div className="subtitle">{subtitle}</div>
        </div>
      </div>

      <section className="empty-panel">
        <div className="empty-card">
          <div className="empty-icon">{title.slice(0, 1)}</div>
          <h2>{title}</h2>
          <p>页面已创建，后续可以在这里补充业务内容和交互。</p>
        </div>
      </section>
    </div>
  );
}
