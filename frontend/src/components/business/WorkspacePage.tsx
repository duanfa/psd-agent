"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowRight, RefreshCw } from "lucide-react";
import {
  fetchAssets,
  fetchBrandAuditEvents,
  fetchBrandDetails,
  fetchRuleVersions,
  fetchRuns,
  type AuditEventRecord,
  type BrandAssetRecord,
  type BrandRecord,
  type BrandRuleVersionRecord,
  type WorkflowRunRecord,
} from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { AppShell } from "./AppShell";
import { useBrandSelection } from "./useBrandSelection";
import { EmptyState, PageSection, StatCard, StatusBadge } from "./ui";

export function WorkspacePage() {
  const {
    brands,
    selectedBrand,
    selectedBrandId,
    loading,
    error,
    setSelectedBrandId,
    buildHref,
    refreshBrands,
  } = useBrandSelection();
  const [brandDetails, setBrandDetails] = useState<BrandRecord | null>(null);
  const [assets, setAssets] = useState<BrandAssetRecord[]>([]);
  const [ruleVersions, setRuleVersions] = useState<BrandRuleVersionRecord[]>([]);
  const [runs, setRuns] = useState<WorkflowRunRecord[]>([]);
  const [events, setEvents] = useState<AuditEventRecord[]>([]);
  const [pageLoading, setPageLoading] = useState(true);
  const [pageError, setPageError] = useState<string | null>(null);

  useEffect(() => {
    if (!selectedBrandId) {
      setPageLoading(false);
      setBrandDetails(null);
      setAssets([]);
      setRuleVersions([]);
      setRuns([]);
      setEvents([]);
      return;
    }
    let cancelled = false;
    const load = async () => {
      setPageLoading(true);
      setPageError(null);
      try {
        const [detail, assetItems, versionItems, runItems, eventItems] = await Promise.all([
          fetchBrandDetails(selectedBrandId),
          fetchAssets(selectedBrandId),
          fetchRuleVersions(selectedBrandId),
          fetchRuns(selectedBrandId),
          fetchBrandAuditEvents(selectedBrandId),
        ]);
        if (cancelled) return;
        setBrandDetails(detail.item);
        setAssets(assetItems);
        setRuleVersions(versionItems);
        setRuns(runItems);
        setEvents(eventItems.slice(0, 5));
      } catch (err) {
        if (!cancelled) {
          setPageError(err instanceof Error ? err.message : String(err));
        }
      } finally {
        if (!cancelled) setPageLoading(false);
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [selectedBrandId]);

  const approvedAssets = assets.filter(
    (asset) => asset.training_status === "approved_for_training" && asset.enabled,
  ).length;
  const recentTrainingTasks = ruleVersions.slice(0, 3);
  const recentDesignTasks = runs.slice(0, 5);
  const currentVersion = ruleVersions.find((item) => item.status === "published");

  return (
    <AppShell
      title="工作台"
      subtitle="查看当前品牌的训练进度、设计任务和常用操作入口"
      brands={brands}
      selectedBrand={selectedBrand}
      selectedBrandId={selectedBrandId}
      loadingBrands={loading}
      onBrandChange={setSelectedBrandId}
      buildHref={buildHref}
      headerActions={
        <button className="btn ghost" type="button" onClick={() => void refreshBrands()}>
          <RefreshCw size={14} /> 刷新品牌
        </button>
      }
    >
      {error || pageError ? <div className="error">{error ?? pageError}</div> : null}

      {!selectedBrandId && !loading ? (
        <EmptyState
          title="当前还没有品牌"
          description="请先创建品牌空间，再开始管理品牌资产和设计任务。"
        />
      ) : null}

      <section className="biz-stat-grid">
        <StatCard
          label="品牌概览"
          value={brandDetails?.name ?? "未初始化"}
          description={brandDetails?.description || "当前还没有品牌，请先创建品牌空间。"}
        />
        <StatCard
          label="资产统计"
          value={assets.length}
          description={`已批准训练 ${approvedAssets} 份，可直接进入品牌训练。`}
        />
        <StatCard
          label="最近训练任务"
          value={ruleVersions.length}
          description={
            currentVersion
              ? `当前发布版本 ${currentVersion.version_label}`
              : "暂无训练任务，上传品牌资产后即可开始训练。"
          }
        />
        <StatCard
          label="最近设计任务"
          value={runs.length}
          description={
            runs.length
              ? "可从任务列表继续查看结果和日志。"
              : "暂无设计任务，完成商品录入后即可发起生成。"
          }
        />
      </section>

      <section className="biz-quick-actions">
        <Link className="btn primary" href={buildHref("/assets")}>
          上传品牌资产
        </Link>
        <button className="btn ghost" type="button" disabled title="本轮先提供页面承接">
          新建商品
        </button>
        <Link className="btn ghost" href={buildHref("/tasks/new")}>
          发起设计任务
        </Link>
        <Link className="btn ghost" href={buildHref("/tasks")}>
          查看全部任务
        </Link>
      </section>

      <div className="biz-two-column">
        <PageSection title="最近训练任务" subtitle="规则版本与训练结果概览">
          {pageLoading ? <div className="biz-loading">正在加载训练任务...</div> : null}
          {!pageLoading && !recentTrainingTasks.length ? (
            <EmptyState
              title="暂无训练任务"
              description="上传品牌资产后即可开始训练。"
              action={
                <Link className="btn ghost btn-small" href={buildHref("/assets")}>
                  去上传资产
                </Link>
              }
            />
          ) : null}
          <div className="biz-list">
            {recentTrainingTasks.map((version) => (
              <article className="biz-list-card" key={version.id}>
                <div className="biz-list-card-head">
                  <div>
                    <div className="biz-list-title">{version.version_label}</div>
                    <div className="biz-list-meta">{version.summary || "暂无摘要"}</div>
                  </div>
                  <StatusBadge value={version.status} />
                </div>
                <p className="biz-card-text">{version.change_reason || "暂无变更说明"}</p>
                <Link className="text-link" href={buildHref("/rules")}>
                  查看完整规则 <ArrowRight size={14} />
                </Link>
              </article>
            ))}
          </div>
        </PageSection>

        <PageSection title="最近设计任务" subtitle="最近生成任务与结果入口">
          {pageLoading ? <div className="biz-loading">正在加载设计任务...</div> : null}
          {!pageLoading && !recentDesignTasks.length ? (
            <EmptyState
              title="暂无设计任务"
              description="完成商品录入后即可发起生成。"
              action={
                <Link className="btn ghost btn-small" href={buildHref("/tasks/new")}>
                  去创建任务
                </Link>
              }
            />
          ) : null}
          <div className="biz-list">
            {recentDesignTasks.map((run) => (
              <article className="biz-list-card" key={run.id}>
                <div className="biz-list-card-head">
                  <div>
                    <div className="biz-list-title">{run.project_name || run.product_name}</div>
                    <div className="biz-list-meta">
                      {run.product_name} · {formatDateTime(run.run_started_at)}
                    </div>
                  </div>
                  <StatusBadge value={run.status} />
                </div>
                <p className="biz-card-text">当前阶段：{run.current_stage_title ?? "已结束"}</p>
                <Link className="text-link" href={buildHref(`/tasks/detail?run=${run.id}`)}>
                  查看详情 <ArrowRight size={14} />
                </Link>
              </article>
            ))}
          </div>
        </PageSection>
      </div>

      <PageSection title="快捷操作" subtitle="围绕当前品牌的常用入口">
        <div className="biz-action-grid">
          <Link className="biz-action-card" href={buildHref("/assets")}>
            <strong>上传品牌资产</strong>
            <span>统一管理品牌官网、规范、历史案例和设计素材</span>
          </Link>
          <Link className="biz-action-card" href={buildHref("/rules")}>
            <strong>切换规则版本</strong>
            <span>查看 AI 提取出的品牌风格、结构和组件规则</span>
          </Link>
          <Link className="biz-action-card" href={buildHref("/tasks/new")}>
            <strong>创建设计任务</strong>
            <span>选择品牌和商品，配置生成参数后开始生成详情页</span>
          </Link>
        </div>
      </PageSection>

      <PageSection title="品牌近期动态" subtitle="审计事件与关键动作记录">
        {!events.length ? (
          <EmptyState title="暂无品牌动态" description="当前品牌暂无可展示的关键动作记录。" />
        ) : (
          <div className="biz-audit-list">
            {events.map((event) => (
              <article className="biz-audit-item" key={event.id}>
                <div className="biz-audit-title">{event.message}</div>
                <div className="biz-list-meta">
                  {event.entity_type} · {formatDateTime(event.created_at)}
                </div>
              </article>
            ))}
          </div>
        )}
      </PageSection>
    </AppShell>
  );
}
