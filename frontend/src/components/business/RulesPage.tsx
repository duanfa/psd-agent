"use client";

import { useEffect, useMemo, useState } from "react";
import { Download, Eye, GitBranch, RefreshCw, Trash2 } from "lucide-react";
import {
  deleteRuleVersion,
  fetchRuleVersionDiff,
  fetchRuleVersions,
  fetchRuns,
  publishRuleVersion,
  rollbackRuleVersion,
  trainRuleVersion,
  type BrandRuleVersionRecord,
  type RuleVersionDiffResponse,
  type WorkflowRunRecord,
} from "@/lib/api";
import { AppShell } from "./AppShell";
import { useBrandSelection } from "./useBrandSelection";
import { EmptyState, PageSection, StatusBadge } from "./ui";

export function RulesPage() {
  const {
    brands,
    selectedBrand,
    selectedBrandId,
    loading,
    error,
    setSelectedBrandId,
    buildHref,
  } = useBrandSelection();
  const [versions, setVersions] = useState<BrandRuleVersionRecord[]>([]);
  const [runs, setRuns] = useState<WorkflowRunRecord[]>([]);
  const [selectedVersionId, setSelectedVersionId] = useState<string | null>(null);
  const [diff, setDiff] = useState<RuleVersionDiffResponse | null>(null);
  const [pageLoading, setPageLoading] = useState(true);
  const [pageError, setPageError] = useState<string | null>(null);
  const [busyAction, setBusyAction] = useState<string | null>(null);

  const loadData = async (brandId: string, preferredVersionId?: string | null) => {
    setPageLoading(true);
    setPageError(null);
    try {
      const [versionItems, runItems] = await Promise.all([fetchRuleVersions(brandId), fetchRuns(brandId)]);
      setVersions(versionItems);
      setRuns(runItems);
      const resolvedVersionId =
        preferredVersionId && versionItems.some((item) => item.id === preferredVersionId)
          ? preferredVersionId
          : versionItems[0]?.id ?? null;
      setSelectedVersionId(resolvedVersionId);
      setDiff(null);
    } catch (err) {
      setPageError(err instanceof Error ? err.message : String(err));
    } finally {
      setPageLoading(false);
    }
  };

  useEffect(() => {
    if (!selectedBrandId) {
      setVersions([]);
      setRuns([]);
      setSelectedVersionId(null);
      setPageLoading(false);
      return;
    }
    void loadData(selectedBrandId, selectedVersionId);
  }, [selectedBrandId]);

  const selectedVersion = useMemo(
    () => versions.find((version) => version.id === selectedVersionId) ?? null,
    [selectedVersionId, versions],
  );
  const currentVersion = useMemo(
    () => versions.find((version) => version.status === "published") ?? null,
    [versions],
  );
  const referencedRunCount = useMemo(
    () => runs.filter((run) => run.rule_version_id === selectedVersionId).length,
    [runs, selectedVersionId],
  );
  const canDeleteSelected = Boolean(
    selectedVersion && selectedVersion.id !== currentVersion?.id && referencedRunCount === 0,
  );

  const runBusyAction = async (key: string, action: () => Promise<void>) => {
    setBusyAction(key);
    try {
      await action();
    } finally {
      setBusyAction(null);
    }
  };

  const handleTrain = async () => {
    if (!selectedBrandId) return;
    await runBusyAction("train", async () => {
      try {
        await trainRuleVersion({
          brandId: selectedBrandId,
          summary: "从品牌规则页重新训练生成候选版本。",
          changeReason: "查看规则后发起重新训练。",
        });
        await loadData(selectedBrandId);
      } catch (err) {
        setPageError(err instanceof Error ? err.message : String(err));
      }
    });
  };

  const handleViewDiff = async (versionId: string) => {
    setSelectedVersionId(versionId);
    try {
      setDiff(await fetchRuleVersionDiff(versionId));
    } catch (err) {
      setPageError(err instanceof Error ? err.message : String(err));
    }
  };

  const handlePublish = async (versionId: string) => {
    await runBusyAction(`publish-${versionId}`, async () => {
      try {
        await publishRuleVersion(versionId);
        if (selectedBrandId) await loadData(selectedBrandId, versionId);
      } catch (err) {
        setPageError(err instanceof Error ? err.message : String(err));
      }
    });
  };

  const handleRollback = async (versionId: string) => {
    await runBusyAction(`rollback-${versionId}`, async () => {
      try {
        await rollbackRuleVersion(versionId);
        if (selectedBrandId) await loadData(selectedBrandId, versionId);
      } catch (err) {
        setPageError(err instanceof Error ? err.message : String(err));
      }
    });
  };

  const handleDelete = async (versionId: string) => {
    if (!selectedBrandId) return;
    const version = versions.find((item) => item.id === versionId);
    if (!version) return;
    const confirmed = window.confirm(`删除后不可恢复，确认删除规则版本“${version.version_label}”吗？`);
    if (!confirmed) return;

    await runBusyAction(`delete-${versionId}`, async () => {
      try {
        await deleteRuleVersion(versionId);
        const nextSelectedId = selectedVersionId === versionId ? null : selectedVersionId;
        await loadData(selectedBrandId, nextSelectedId);
      } catch (err) {
        setPageError(err instanceof Error ? err.message : String(err));
      }
    });
  };

  return (
    <AppShell
      title="品牌规则"
      subtitle="查看 AI 提取出的品牌风格、结构和组件规则"
      brands={brands}
      selectedBrand={selectedBrand}
      selectedBrandId={selectedBrandId}
      loadingBrands={loading}
      onBrandChange={setSelectedBrandId}
      buildHref={buildHref}
      headerActions={
        <button className="btn ghost" type="button" onClick={() => void handleTrain()} disabled={busyAction === "train"}>
          <RefreshCw size={14} /> {busyAction === "train" ? "训练中" : "重新训练"}
        </button>
      }
    >
      {error || pageError ? <div className="error">{error ?? pageError}</div> : null}

      {!pageLoading && !versions.length ? (
        <EmptyState title="当前还没有规则结果" description="请先完成品牌训练。" />
      ) : null}

      <section className="biz-rule-hero">
        <div className="biz-split-copy">
          <div className="biz-section-kicker">规则版本</div>
          <h3>{currentVersion?.version_label ?? "尚未发布版本"}</h3>
          <p>
            当前页面聚焦品牌风格、结构和组件规则的版本管理。每次训练会生成候选版本，发布后才会进入正式生成链路。
          </p>
          <div className="biz-inline-actions">
            <StatusBadge value={currentVersion?.status ?? "draft"} />
            <span className="biz-inline-note">候选版本 {versions.length} 个</span>
            <span className="biz-inline-note">关联任务 {runs.length} 个</span>
          </div>
        </div>
        <div className="biz-rule-preview">
          <div className="app-hero-panel-label">当前发布版本</div>
          <div className="app-hero-panel-title">{currentVersion?.version_label ?? "未发布"}</div>
          <div className="biz-rule-summary">
            <div>品牌：{selectedBrand?.name ?? "-"}</div>
            <div>状态：{currentVersion ? "已发布" : "等待发布"}</div>
            <div>版本数：{versions.length}</div>
          </div>
        </div>
      </section>

      <div className="biz-rule-columns">
        <PageSection title="规则版本" subtitle="切换查看候选版本、发布版本与删除操作">
          {pageLoading ? <div className="biz-loading">正在加载规则版本...</div> : null}
          <div className="biz-list">
            {versions.map((version) => {
              const isCurrent = currentVersion?.id === version.id;
              const referencedCount = runs.filter((run) => run.rule_version_id === version.id).length;
              const deleting = busyAction === `delete-${version.id}`;
              const publishing = busyAction === `publish-${version.id}`;
              const rollingBack = busyAction === `rollback-${version.id}`;
              return (
                <article
                  className={`biz-list-card ${selectedVersionId === version.id ? "biz-list-card-active" : ""}`}
                  key={version.id}
                >
                  <div className="biz-list-card-head">
                    <div>
                      <div className="biz-list-title">{version.version_label}</div>
                      <div className="biz-list-meta">{version.summary || "暂无摘要"}</div>
                    </div>
                    <StatusBadge value={version.status} />
                  </div>

                  <div className="biz-rule-highlights">
                    <div>变更说明：{version.change_reason || "暂无变更说明"}</div>
                    <div>关联任务：{referencedCount}</div>
                    <div>漂移风险：{version.drift_risks.join("；") || "暂无"}</div>
                  </div>

                  <div className="biz-inline-actions">
                    <button className="btn ghost btn-small" type="button" onClick={() => setSelectedVersionId(version.id)}>
                      切换版本
                    </button>
                    <button className="btn ghost btn-small" type="button" onClick={() => void handleViewDiff(version.id)}>
                      <Eye size={14} /> 查看完整规则
                    </button>
                    <button className="btn primary btn-small" type="button" onClick={() => void handlePublish(version.id)} disabled={publishing || isCurrent}>
                      <GitBranch size={14} /> {publishing ? "发布中" : "发布"}
                    </button>
                    <button className="btn ghost btn-small" type="button" onClick={() => void handleRollback(version.id)} disabled={rollingBack || !isCurrent}>
                      {rollingBack ? "回滚中" : "回滚"}
                    </button>
                    <button
                      className="btn danger btn-small"
                      type="button"
                      onClick={() => void handleDelete(version.id)}
                      disabled={deleting || isCurrent || referencedCount > 0}
                      title={
                        isCurrent
                          ? "当前发布版本不可删除"
                          : referencedCount > 0
                            ? "已被历史任务引用的版本不可删除"
                            : undefined
                      }
                    >
                      <Trash2 size={14} /> {deleting ? "删除中" : "删除"}
                    </button>
                  </div>
                </article>
              );
            })}
          </div>
        </PageSection>

        <PageSection
          title="设计规则说明"
          subtitle="当前选中版本的品牌画像、布局摘要和 Prompt 预览"
          action={
            <button className="btn ghost btn-small" type="button" disabled>
              <Download size={14} /> 导出规则
            </button>
          }
        >
          {!selectedVersion ? (
            <EmptyState title="暂无规则详情" description="切换版本后即可查看设计规则说明。" />
          ) : (
            <>
              <div className="biz-detail-card">
                <h3>{selectedVersion.version_label}</h3>
                <div className="biz-detail-list">
                  <div>当前发布版本：{currentVersion?.version_label ?? "未发布"}</div>
                  <div>当前选中状态：{selectedVersion.status}</div>
                  <div>是否允许删除：{canDeleteSelected ? "可以" : "不可"}</div>
                </div>
              </div>

              <div className="biz-two-column">
                <div className="biz-code-block">
                  <pre>{JSON.stringify(selectedVersion.brand_profile, null, 2)}</pre>
                </div>
                <div className="biz-code-block">
                  <pre>{JSON.stringify(selectedVersion.prompt_overrides, null, 2)}</pre>
                </div>
              </div>

              <div className="biz-code-block">
                <pre>{JSON.stringify(selectedVersion.diff_summary, null, 2)}</pre>
              </div>
            </>
          )}
        </PageSection>
      </div>

      <PageSection title="规则版本关联任务" subtitle="帮助判断某个规则版本的实际使用情况">
        {!runs.length ? (
          <EmptyState title="暂无关联任务" description="当前品牌还没有使用该规则版本的设计任务记录。" />
        ) : (
          <div className="biz-list">
            {runs.slice(0, 4).map((run) => (
              <article className="biz-list-card" key={run.id}>
                <div className="biz-list-card-head">
                  <div>
                    <div className="biz-list-title">{run.project_name || run.product_name}</div>
                    <div className="biz-list-meta">规则版本：{run.rule_version_id ?? "-"}</div>
                  </div>
                  <StatusBadge value={run.status} />
                </div>
              </article>
            ))}
          </div>
        )}
        {diff ? (
          <div className="biz-code-block">
            <pre>{JSON.stringify(diff.diff, null, 2)}</pre>
          </div>
        ) : null}
      </PageSection>
    </AppShell>
  );
}
