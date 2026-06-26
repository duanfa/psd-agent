"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Search } from "lucide-react";
import { fetchRuns, type WorkflowRunRecord } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { AppShell } from "./AppShell";
import { useBrandSelection } from "./useBrandSelection";
import { EmptyState, PageSection, StatusBadge } from "./ui";

export function TasksPage() {
  const {
    brands,
    selectedBrand,
    selectedBrandId,
    loading,
    error,
    setSelectedBrandId,
    buildHref,
  } = useBrandSelection();
  const [runs, setRuns] = useState<WorkflowRunRecord[]>([]);
  const [keyword, setKeyword] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [pageLoading, setPageLoading] = useState(true);
  const [pageError, setPageError] = useState<string | null>(null);

  useEffect(() => {
    if (!selectedBrandId) {
      setRuns([]);
      setPageLoading(false);
      return;
    }
    let cancelled = false;
    const load = async () => {
      setPageLoading(true);
      setPageError(null);
      try {
        const items = await fetchRuns(selectedBrandId);
        if (!cancelled) setRuns(items);
      } catch (err) {
        if (!cancelled) setPageError(err instanceof Error ? err.message : String(err));
      } finally {
        if (!cancelled) setPageLoading(false);
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [selectedBrandId]);

  const filteredRuns = useMemo(
    () =>
      runs.filter((run) => {
        const hitKeyword =
          !keyword ||
          run.id.toLowerCase().includes(keyword.toLowerCase()) ||
          run.product_name.toLowerCase().includes(keyword.toLowerCase()) ||
          run.project_name.toLowerCase().includes(keyword.toLowerCase());
        const hitStatus = statusFilter === "all" || run.status === statusFilter;
        return hitKeyword && hitStatus;
      }),
    [keyword, runs, statusFilter],
  );

  return (
    <AppShell
      title="设计任务"
      subtitle="查看所有设计任务的状态、进度和结果入口"
      brands={brands}
      selectedBrand={selectedBrand}
      selectedBrandId={selectedBrandId}
      loadingBrands={loading}
      onBrandChange={setSelectedBrandId}
      buildHref={buildHref}
    >
      {error || pageError ? <div className="error">{error ?? pageError}</div> : null}

      <PageSection title="任务列表" subtitle="可按状态和关键字快速筛选">
        <div className="biz-filter-row">
          <label className="biz-input-wrap">
            <Search size={14} />
            <input
              value={keyword}
              onChange={(event) => setKeyword(event.target.value)}
              placeholder="搜索任务 ID、商品名称或品牌"
            />
          </label>
          <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
            <option value="all">全部状态</option>
            <option value="queued">排队中</option>
            <option value="running">处理中</option>
            <option value="completed">生成成功</option>
            <option value="fallback_completed">生成成功</option>
            <option value="failed">生成失败</option>
          </select>
          <Link className="btn primary" href={buildHref("/tasks/new")}>
            创建任务
          </Link>
        </div>

        {pageLoading ? <div className="biz-loading">正在加载任务列表...</div> : null}
        {!pageLoading && !filteredRuns.length ? (
          <EmptyState title="当前还没有设计任务" description="去创建第一个任务。" />
        ) : null}

        <div className="biz-table-wrap">
          <table className="biz-table">
            <thead>
              <tr>
                <th>任务 ID</th>
                <th>品牌</th>
                <th>商品</th>
                <th>任务类型</th>
                <th>状态</th>
                <th>创建时间</th>
                <th>完成时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {filteredRuns.map((run) => (
                <tr key={run.id}>
                  <td>{run.id}</td>
                  <td>{selectedBrand?.name ?? "-"}</td>
                  <td>{run.product_name}</td>
                  <td>{run.workflow_mode ?? "-"}</td>
                  <td>
                    <StatusBadge value={run.status} />
                  </td>
                  <td>{formatDateTime(run.run_started_at)}</td>
                  <td>{formatDateTime(run.run_finished_at)}</td>
                  <td>
                    <div className="biz-inline-actions">
                      <Link className="btn ghost btn-small" href={buildHref(`/tasks/detail?run=${run.id}`)}>
                        查看详情
                      </Link>
                      <Link className="btn ghost btn-small" href={buildHref("/tasks/new")}>
                        重新执行
                      </Link>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </PageSection>
    </AppShell>
  );
}
