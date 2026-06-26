import Link from "next/link";
import { fetchDashboard } from "@/lib/api";

function statusClass(status: string) {
  if (status.includes("成功") || status.includes("稳定") || status.includes("completed")) {
    return "success";
  }
  if (status.includes("失败") || status.includes("failed")) {
    return "failed";
  }
  return "running";
}

function statusLabel(status: string) {
  const map: Record<string, string> = {
    completed: "生成成功",
    fallback_completed: "待审核",
    failed: "生成失败",
    running: "处理中",
    cancelling: "取消中",
    cancelled: "已取消",
  };
  return map[status] ?? status;
}

export default async function DashboardPage() {
  const data = await fetchDashboard();

  return (
    <div className="data-page">
      <div className="topbar">
        <div className="topbar-left">
          <h1>{data.page.title}</h1>
          <div className="subtitle">{data.page.subtitle}</div>
        </div>
      </div>

      <section className="panel hero-panel">
        <div className="hero-grid">
          <div>
            <div className="eyebrow">当前品牌</div>
            <h2 className="section-hero-title">{data.hero.brandName}</h2>
            <p className="subtitle">{data.hero.description}</p>
            <div className="tag-row">
              <span className="tag">品牌状态：{data.hero.status}</span>
              {data.hero.tags.map((tag) => (
                <span className="tag" key={tag}>
                  {tag}
                </span>
              ))}
            </div>
          </div>
          <div className="info-card soft-card">
            <div className="split-line">
              <div>
                <div className="muted-text">本周任务完成率</div>
                <div className="big-metric">{data.hero.weeklyCompletionRate}%</div>
              </div>
              <span className={`status-pill ${statusClass(data.hero.weeklyStatus)}`}>
                {data.hero.weeklyStatus}
              </span>
            </div>
            <div className="progress-bar">
              <span style={{ width: `${data.hero.weeklyCompletionRate}%` }} />
            </div>
            <p className="subtitle">{data.hero.weeklySummary}</p>
          </div>
        </div>
      </section>

      <section className="summary-grid">
        {data.stats.map((item) => (
          <article className="info-card" key={item.label}>
            <div className="eyebrow">{item.label}</div>
            <div className="big-metric">{item.value}</div>
            <div className="muted-text">{item.description}</div>
          </article>
        ))}
      </section>

      <div className="content-grid-2">
        <section className="panel content-panel">
          <div className="split-line">
            <h2 className="section-title">最近训练任务</h2>
            <Link className="text-link" href="/brand-rules">
              查看规则页
            </Link>
          </div>
          <div className="record-list">
            {data.trainingTasks.map((item) => (
              <div className="record-item" key={item.title}>
                <div className="split-line">
                  <strong>{item.title}</strong>
                  <span className={`status-pill ${statusClass(item.status)}`}>
                    {statusLabel(item.status)}
                  </span>
                </div>
                <div className="subtitle">{item.summary}</div>
              </div>
            ))}
          </div>
        </section>

        <section className="panel content-panel">
          <div className="split-line">
            <h2 className="section-title">最近设计任务</h2>
            <Link className="text-link" href="/design-tasks">
              查看全部任务
            </Link>
          </div>
          <div className="record-list">
            {data.designTasks.map((item) => (
              <div className="record-item" key={item.title}>
                <div className="split-line">
                  <strong>{item.title}</strong>
                  <span className={`status-pill ${statusClass(item.status)}`}>
                    {statusLabel(item.status)}
                  </span>
                </div>
                <div className="subtitle">{item.summary}</div>
              </div>
            ))}
          </div>
        </section>
      </div>

      <section className="panel content-panel">
        <h2 className="section-title">快捷操作</h2>
        <div className="action-grid">
          {data.quickActions.map((item) => (
            <Link className="info-card action-card" href={item.href} key={item.title}>
              <h3>{item.title}</h3>
              <p>{item.description}</p>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
