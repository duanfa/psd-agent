"use client";

import type { ReactNode } from "react";

export function StatCard({
  label,
  value,
  description,
}: {
  label: string;
  value: string | number;
  description: string;
}) {
  return (
    <article className="biz-stat-card">
      <div className="biz-stat-label">{label}</div>
      <div className="biz-stat-value">{value}</div>
      <p>{description}</p>
    </article>
  );
}

export function PageSection({
  title,
  subtitle,
  action,
  children,
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="biz-section">
      <div className="biz-section-head">
        <div>
          <h2>{title}</h2>
          {subtitle ? <p>{subtitle}</p> : null}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="biz-empty">
      <div className="biz-empty-title">{title}</div>
      <p>{description}</p>
      {action ? <div className="biz-empty-action">{action}</div> : null}
    </div>
  );
}

const STATUS_CLASS: Record<string, string> = {
  active: "status-success",
  archived: "status-muted",
  published: "status-success",
  pending_publish: "status-warning",
  draft: "status-muted",
  rolled_back: "status-fail",
  completed: "status-success",
  fallback_completed: "status-warning",
  failed: "status-fail",
  queued: "status-muted",
  running: "status-info",
  cancelling: "status-warning",
  cancelled: "status-muted",
};

const STATUS_LABEL: Record<string, string> = {
  active: "启用中",
  archived: "已归档",
  published: "已发布",
  pending_publish: "待发布",
  draft: "草稿",
  rolled_back: "已回滚",
  completed: "生成成功",
  fallback_completed: "规则完成",
  failed: "生成失败",
  queued: "排队中",
  running: "处理中",
  cancelling: "取消中",
  cancelled: "已取消",
};

export function StatusBadge({ value }: { value: string }) {
  return (
    <span className={`status-badge ${STATUS_CLASS[value] ?? "status-muted"}`}>
      {STATUS_LABEL[value] ?? value}
    </span>
  );
}
