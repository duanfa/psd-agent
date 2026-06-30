"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import {
  fetchDesignTasksPageWithFilters,
  type DesignTasksPageResponse,
} from "@/lib/api";

function statusClass(status: string) {
  if (status.includes("completed") || status.includes("成功")) return "success";
  if (status.includes("failed") || status.includes("失败") || status.includes("cancelled")) {
    return "failed";
  }
  if (status.includes("fallback")) return "warning";
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

function formatTime(value?: string | null) {
  if (!value) return "-";
  return new Date(value).toLocaleString("zh-CN", { hour12: false });
}

interface FiltersState {
  brand: string;
  status: string;
  taskType: string;
  search: string;
}

export function DesignTasksPageClient({ initialData }: { initialData: DesignTasksPageResponse }) {
  const [data, setData] = useState(initialData);
  const [filters, setFilters] = useState<FiltersState>({
    brand: initialData.filters.brand,
    status: initialData.filters.status,
    taskType: initialData.filters.taskType,
    search: initialData.filters.search,
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const searchTimer = useRef<number | null>(null);

  const loadData = async (nextFilters: FiltersState) => {
    setLoading(true);
    setError(null);
    try {
      const next = await fetchDesignTasksPageWithFilters(nextFilters);
      setData(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  const updateFilters = (patch: Partial<FiltersState>) => {
    const next = { ...filters, ...patch };
    setFilters(next);
    if ("search" in patch) {
      if (searchTimer.current) window.clearTimeout(searchTimer.current);
      searchTimer.current = window.setTimeout(() => {
        void loadData(next);
      }, 250);
      return;
    }
    void loadData(next);
  };

  useEffect(() => {
    return () => {
      if (searchTimer.current) window.clearTimeout(searchTimer.current);
    };
  }, []);

  return (
    <div className="data-page">
      <div className="topbar">
        <div className="topbar-left">
          <h1>{data.page.title}</h1>
          <div className="subtitle">{data.page.subtitle}</div>
        </div>
      </div>

      <section className="toolbar-row toolbar-row-4">
        <select value={filters.brand} onChange={(e) => updateFilters({ brand: e.target.value })}>
          <option value="">全部品牌</option>
          {data.brands.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
        <select value={filters.status} onChange={(e) => updateFilters({ status: e.target.value })}>
          <option value="">全部状态</option>
          {data.statuses.map((item) => (
            <option key={item} value={item}>
              {statusLabel(item)}
            </option>
          ))}
        </select>
        <select
          value={filters.taskType}
          onChange={(e) => updateFilters({ taskType: e.target.value })}
        >
          <option value="">全部任务类型</option>
          {data.taskTypes.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
        <input
          placeholder="搜索任务 ID、商品名称或品牌"
          value={filters.search}
          onChange={(e) => updateFilters({ search: e.target.value })}
        />
      </section>

      <section className="summary-grid">
        <article className="info-card">
          <div className="eyebrow">全部任务</div>
          <div className="big-metric">{data.metrics.total}</div>
          <div className="muted-text">当前筛选结果</div>
        </article>
        <article className="info-card">
          <div className="eyebrow">处理中</div>
          <div className="big-metric">{data.metrics.running}</div>
          <div className="muted-text">异步执行中</div>
        </article>
        <article className="info-card">
          <div className="eyebrow">生成成功</div>
          <div className="big-metric">{data.metrics.success}</div>
          <div className="muted-text">可进入预览</div>
        </article>
        <article className="info-card">
          <div className="eyebrow">生成失败</div>
          <div className="big-metric">{data.metrics.failed}</div>
          <div className="muted-text">待排查</div>
        </article>
      </section>

      <section className="panel content-panel">
        {error ? <div className="error">{error}</div> : null}
        <div className="table-wrap">
          <table className="simple-table">
            <thead>
              <tr>
                <th>任务 ID</th>
                <th>品牌</th>
                <th>商品</th>
                <th>任务类型</th>
                <th>状态</th>
                <th>创建时间</th>
                <th>完成时间</th>
              </tr>
            </thead>
            <tbody>
              {data.tasks.length ? (
                data.tasks.map((item) => (
                  <tr key={item.taskId}>
                    <td>
                      <Link className="table-link" href={`/design-tasks/${item.runId}`}>
                        {item.taskId}
                      </Link>
                    </td>
                    <td>{item.brand}</td>
                    <td>{item.product}</td>
                    <td>{item.taskType}</td>
                    <td>
                      <span className={`status-pill ${statusClass(item.status)}`}>
                        {statusLabel(item.status)}
                      </span>
                    </td>
                    <td>{formatTime(item.createdAt)}</td>
                    <td>{formatTime(item.completedAt)}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td className="table-empty" colSpan={7}>
                    {loading ? "正在加载任务..." : "没有匹配的任务结果。"}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
