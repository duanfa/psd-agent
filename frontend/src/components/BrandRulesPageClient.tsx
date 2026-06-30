"use client";

import { Eye, GitCompareArrows, Loader2, PencilLine, Rocket, RotateCcw, Sparkles, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  fetchBrandRuleDiff,
  deleteBrandRuleVersion,
  fetchBrandRuleTrainLogs,
  fetchBrandRulesPageWithFilters,
  publishBrandRule,
  rollbackBrandRule,
  trainBrandRules,
  type BrandRuleTarget,
  type BrandRuleDiffResponse,
  type BrandRulesPageResponse,
  updateBrandRuleMarkdown,
} from "@/lib/api";

function createClientRunId() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `brand-rule-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function formatTime(value?: string | null) {
  if (!value) return "未记录";
  return new Date(value).toLocaleString("zh-CN", { hour12: false });
}

function getStatusTone(status?: string | null) {
  const normalized = (status ?? "").toLowerCase();
  if (normalized === "active") return "success";
  if (normalized === "failed" || normalized === "error") return "failed";
  if (normalized === "running" || normalized === "training") return "running";
  return "warning";
}

type BrandRuleVersion = BrandRulesPageResponse["versions"][number];
const TARGET_LABELS: Record<BrandRuleTarget, string> = {
  brand_core: "品牌设计规范",
  detail_page_layout: "详情页布局规范",
};

function defaultPromptByTarget(target: BrandRuleTarget) {
  if (target === "detail_page_layout") {
    return "请从该品牌的详情页素材中提取清晰的页面布局、文字排版层级和图片放置位置区域，形成可复用的商品详情页规则。";
  }
  return "请从官网素材和品牌资产中提取品牌视觉规范、字体色彩、品牌语气和禁用项，形成稳定的品牌设计规范。";
}

function defaultAssetIds(
  assets: Array<{ id: number; includeInTraining?: boolean }>,
) {
  const included = assets.filter((item) => item.includeInTraining).map((item) => item.id);
  return included.length ? included : assets.map((item) => item.id);
}

type RuleDialogMode = "preview" | "edit";
type RuleDialogState = {
  mode: RuleDialogMode;
  versionId: number;
  version: string;
  status: string;
  createdAt?: string | null;
  baseVersion?: string | null;
  markdown: string;
} | null;

export function BrandRulesPageClient({ initialData }: { initialData: BrandRulesPageResponse }) {
  const [data, setData] = useState(initialData);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [trainOpen, setTrainOpen] = useState(false);
  const [training, setTraining] = useState(false);
  const [trainingLogs, setTrainingLogs] = useState<string[]>([]);
  const [trainingStatus, setTrainingStatus] = useState("idle");
  const [trainingStage, setTrainingStage] = useState<string | null>(null);
  const [savingMarkdown, setSavingMarkdown] = useState(false);
  const [versionActionLoading, setVersionActionLoading] = useState(false);
  const [diffLoading, setDiffLoading] = useState(false);
  const [versionDiff, setVersionDiff] = useState<BrandRuleDiffResponse | null>(null);
  const [deletingVersionId, setDeletingVersionId] = useState<number | null>(null);
  const [previewLoadingId, setPreviewLoadingId] = useState<number | null>(null);
  const [ruleDialog, setRuleDialog] = useState<RuleDialogState>(null);
  const [markdown, setMarkdown] = useState(initialData.markdown);
  const [trainForm, setTrainForm] = useState({
    trainingTarget: initialData.selectedTargetKey ?? ("brand_core" as BrandRuleTarget),
    assetIds: defaultAssetIds(initialData.sourceAssets),
    prompt: initialData.trainingPrompt,
    websiteUrls: initialData.websiteUrls.join("\n"),
    baseVersionId: initialData.selectedVersionId ?? null,
    useBaseVersion: Boolean(initialData.selectedVersionId),
  });
  const selectedVersion = data.versions.find((version) => version.id === data.selectedVersionId);
  const activeVersion =
    data.versions.find(
      (version) => version.status === "active" && version.targetKey === (selectedVersion?.targetKey ?? data.selectedTargetKey),
    ) ?? null;
  const filteredTrainVersions = useMemo(
    () => data.versions.filter((version) => version.targetKey === trainForm.trainingTarget),
    [data.versions, trainForm.trainingTarget],
  );
  const selectedVersionStatusTone = getStatusTone(selectedVersion?.status);
  const currentTargetLabel = TARGET_LABELS[trainForm.trainingTarget];

  const loadData = async (brandId: number, versionId?: number | null) => {
    setLoading(true);
    setError(null);
    try {
      const next = await fetchBrandRulesPageWithFilters({
        brandId,
        versionId: versionId ?? undefined,
      });
      setData(next);
      setVersionDiff(null);
      setMarkdown(next.markdown);
      setTrainForm({
        trainingTarget: next.selectedTargetKey ?? "brand_core",
        assetIds: defaultAssetIds(next.sourceAssets),
        prompt: next.trainingPrompt,
        websiteUrls: next.websiteUrls.join("\n"),
        baseVersionId: next.selectedVersionId ?? null,
        useBaseVersion: Boolean(next.selectedVersionId),
      });
      return next;
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      return null;
    } finally {
      setLoading(false);
    }
  };

  const handleBrandChange = async (brandId: number) => {
    if (brandId === data.selectedBrand.id) return;
    setRuleDialog(null);
    await loadData(brandId);
  };

  const handleVersionChange = async (value: string) => {
    const versionId = value ? Number(value) : null;
    await loadData(data.selectedBrand.id, versionId);
  };

  const toggleAsset = (assetId: number) => {
    setTrainForm((current) => {
      const exists = current.assetIds.includes(assetId);
      return {
        ...current,
        assetIds: exists
          ? current.assetIds.filter((item) => item !== assetId)
          : [...current.assetIds, assetId],
      };
    });
  };

  const handleTrain = async () => {
    const runId = createClientRunId();
    setTraining(true);
    setError(null);
    setTrainingLogs([]);
    setTrainingStatus("running");
    setTrainingStage("准备训练输入");
    let stopped = false;
    const pollLogs = async () => {
      try {
        const snapshot = await fetchBrandRuleTrainLogs(runId);
        if (stopped) return;
        setTrainingLogs(snapshot.logs);
        setTrainingStatus(snapshot.status);
        setTrainingStage(snapshot.current_stage ?? null);
      } catch {
        // 训练接口可能还没写入第一条日志，下一轮继续轮询。
      }
    };
    const timer = window.setInterval(pollLogs, 900);
    void pollLogs();
    try {
      const urls = trainForm.websiteUrls
        .split("\n")
        .map((item) => item.trim())
        .filter(Boolean);
      const result = await trainBrandRules({
        brandId: data.selectedBrand.id,
        assetIds: trainForm.assetIds,
        prompt: trainForm.prompt,
        websiteUrls: urls,
        trainingTarget: trainForm.trainingTarget,
        baseVersionId: trainForm.useBaseVersion ? trainForm.baseVersionId : null,
        clientRunId: runId,
      });
      await pollLogs();
      setTrainOpen(false);
      await loadData(data.selectedBrand.id, result.id);
    } catch (err) {
      await pollLogs();
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      stopped = true;
      window.clearInterval(timer);
      setTraining(false);
    }
  };

  const handleSaveMarkdown = async () => {
    if (!data.selectedVersionId) return;
    setSavingMarkdown(true);
    setError(null);
    try {
      await updateBrandRuleMarkdown(data.selectedVersionId, markdown);
      const next = await loadData(data.selectedBrand.id, data.selectedVersionId);
      if (next?.selectedVersionId) {
        const nextVersion = next.versions.find((item) => item.id === next.selectedVersionId);
        setRuleDialog((current) =>
          current && current.versionId === next.selectedVersionId
            ? {
                ...current,
                mode: "edit",
                version: nextVersion?.version ?? current.version,
                status: nextVersion?.status ?? current.status,
                createdAt: nextVersion?.createdAt ?? current.createdAt,
                baseVersion: nextVersion?.baseVersion ?? current.baseVersion,
                markdown: next.markdown,
              }
            : current,
        );
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSavingMarkdown(false);
    }
  };

  const handleDeleteVersion = async (ruleId: number, version: string) => {
    if (!window.confirm(`确认删除规则版本“${version}”吗？`)) return;
    setDeletingVersionId(ruleId);
    setError(null);
    try {
      await deleteBrandRuleVersion(ruleId);
      setRuleDialog((current) => (current?.versionId === ruleId ? null : current));
      await loadData(data.selectedBrand.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setDeletingVersionId(null);
    }
  };

  const handleOpenRuleDialog = async (version: BrandRuleVersion, mode: RuleDialogMode) => {
    setPreviewLoadingId(version.id);
    setError(null);
    try {
      if (mode === "edit") {
        const next = version.id === data.selectedVersionId ? data : await loadData(data.selectedBrand.id, version.id);
        if (!next) return;
        const editableVersion = next.versions.find((item) => item.id === next.selectedVersionId);
        if (!editableVersion) return;
        setRuleDialog({
          mode: "edit",
          versionId: editableVersion.id,
          version: editableVersion.version,
          status: editableVersion.status,
          createdAt: editableVersion.createdAt,
          baseVersion: editableVersion.baseVersion,
          markdown: next.markdown,
        });
        return;
      }
      if (version.id === data.selectedVersionId) {
        setRuleDialog({
          mode: "preview",
          versionId: version.id,
          version: version.version,
          status: version.status,
          createdAt: version.createdAt,
          baseVersion: version.baseVersion,
          markdown,
        });
        return;
      }
      const next = await fetchBrandRulesPageWithFilters({ brandId: data.selectedBrand.id, versionId: version.id });
      const previewVersion = next.versions.find((item) => item.id === version.id) ?? version;
      setRuleDialog({
        mode: "preview",
        versionId: previewVersion.id,
        version: previewVersion.version,
        status: previewVersion.status,
        createdAt: previewVersion.createdAt,
        baseVersion: previewVersion.baseVersion,
        markdown: next.markdown,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setPreviewLoadingId(null);
    }
  };

  const handleDialogMarkdownChange = (value: string) => {
    setMarkdown(value);
    setRuleDialog((current) =>
      current && current.mode === "edit"
        ? {
            ...current,
            markdown: value,
          }
        : current,
    );
  };

  const handlePublish = async () => {
    if (!data.selectedVersionId) return;
    setVersionActionLoading(true);
    setError(null);
    try {
      await publishBrandRule(data.selectedVersionId);
      await loadData(data.selectedBrand.id, data.selectedVersionId);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setVersionActionLoading(false);
    }
  };

  const handleRollback = async () => {
    if (!data.selectedVersionId) return;
    setVersionActionLoading(true);
    setError(null);
    try {
      await rollbackBrandRule(data.selectedVersionId);
      await loadData(data.selectedBrand.id, data.selectedVersionId);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setVersionActionLoading(false);
    }
  };

  const handleLoadDiff = async () => {
    if (!data.selectedVersionId || !activeVersion || data.selectedVersionId === activeVersion.id) return;
    setDiffLoading(true);
    setError(null);
    try {
      const diff = await fetchBrandRuleDiff(activeVersion.id, data.selectedVersionId);
      setVersionDiff(diff);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setDiffLoading(false);
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
          <button className="btn primary" type="button" onClick={() => setTrainOpen(true)}>
            <Sparkles size={16} />
            训练规则
          </button>
        </div>
      </div>

      <div className="rules-layout">
        <aside className="assets-brand-panel brand-rule-brand-panel">
          <div className="brand-rule-brand-panel-head">
            <div className="eyebrow">品牌工作区</div>
            <div className="assets-panel-title">品牌规则列表</div>
            <div className="subtitle">先选择品牌，再查看该品牌的规则版本、摘要和 Markdown 明细。</div>
          </div>

          <div className="brand-rule-brand-highlight">
            <div className="brand-rule-brand-highlight-head">
              <div>
                <strong>{data.selectedBrand.name}</strong>
                <span>
                  Core：{data.activeVersions?.brand_core?.version || "无"} / 详情页：
                  {data.activeVersions?.detail_page_layout?.version || "无"}
                </span>
              </div>
              <span className={`status-pill ${selectedVersionStatusTone}`}>
                {selectedVersion?.status ?? "未选择"}
              </span>
            </div>
            <div className="brand-rule-brand-highlight-grid">
              <div>
                <span>规则版本</span>
                <strong>{data.versions.length}</strong>
              </div>
              <div>
                <span>Core Rule</span>
                <strong>{data.targetSummaries?.find((item) => item.targetKey === "brand_core")?.count ?? 0}</strong>
              </div>
              <div>
                <span>详情页规则</span>
                <strong>{data.targetSummaries?.find((item) => item.targetKey === "detail_page_layout")?.count ?? 0}</strong>
              </div>
              <div>
                <span>当前规则类型</span>
                <strong>
                  {selectedVersion?.targetLabel ??
                    (data.selectedTargetKey
                      ? TARGET_LABELS[(data.selectedTargetKey ?? "brand_core") as BrandRuleTarget]
                      : "未选择")}
                </strong>
              </div>
            </div>
          </div>

          <div className="assets-brand-list brand-rule-brand-list">
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
                    {brand.status} / Core {brand.coreVersion || "无"} / 详情页 {brand.detailPageVersion || "无"}
                  </small>
                </span>
                <em>{brand.totalVersions ?? brand.ruleCount}</em>
              </button>
            ))}
          </div>

          <div className="brand-rule-brand-footnote">
            左侧用于切换品牌空间，右侧用于管理当前品牌的规则版本与内容操作。
          </div>
        </aside>

        <div className="rules-main">
          <section className="summary-grid">
            {data.overview.map((item, index) => (
              <article className="info-card" key={item.label}>
                <div className="eyebrow">{item.label}</div>
                {index === 0 ? (
                  <select
                    className="version-select"
                    value={data.selectedVersionId ?? ""}
                    onChange={(event) => handleVersionChange(event.target.value)}
                  >
                    {data.versions.length ? (
                      data.versions.map((version) => (
                        <option key={version.id} value={version.id}>
                          {version.targetLabel} / {version.version} {version.status === "active" ? "（当前）" : ""}
                        </option>
                      ))
                    ) : (
                      <option value="">未训练</option>
                    )}
                  </select>
                ) : (
                  <div className="big-metric">{item.value}</div>
                )}
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
              <div className="content-grid-sidebar brand-rule-workspace-grid">
                {data.targetSummaries?.length ? (
                  <section className="panel content-panel">
                    <div className="split-line">
                      <div>
                        <h2 className="section-title">规则类型分组</h2>
                        <div className="subtitle">同一品牌下分别管理品牌设计规范与详情页 Derived Rule。</div>
                      </div>
                    </div>
                    <div className="action-grid action-grid-2">
                      {data.targetSummaries.map((item) => (
                        <article className="info-card" key={item.targetKey}>
                          <div className="eyebrow">{item.label}</div>
                          <div className="big-metric">{item.count}</div>
                          <p>{item.summary}</p>
                          <div className="muted-text">当前生效：{item.activeVersion || "无"}</div>
                        </article>
                      ))}
                    </div>
                  </section>
                ) : null}
                <section className="panel content-panel">
                  <div className="split-line">
                    <div>
                      <h2 className="section-title">规则版本列表</h2>
                      <div className="subtitle">支持弹窗预览 Markdown、切换编辑版本，以及快速清理历史版本。</div>
                    </div>
                    <span className="tag">当前品牌：{data.selectedBrand.name}</span>
                  </div>
                  <div className="table-wrap">
                    <table className="simple-table rule-table brand-rule-table">
                      <thead>
                        <tr>
                          <th>版本</th>
                          <th>规则类型</th>
                          <th>状态</th>
                          <th>叠加版本</th>
                          <th>规则概览</th>
                          <th>创建时间</th>
                          <th>操作</th>
                        </tr>
                      </thead>
                      <tbody>
                        {data.versions.length ? (
                          data.versions.map((version) => {
                            const isEditing = version.id === data.selectedVersionId;
                            const actionDisabled = loading || deletingVersionId === version.id;
                            return (
                              <tr key={version.id}>
                                <td className="brand-rule-version-cell">
                                  <strong>{version.version}</strong>
                                  <span className="subtitle">
                                    {isEditing ? "当前选中版本" : "支持弹窗查看"}
                                  </span>
                                </td>
                                <td>
                                  <span className="tag">{version.targetLabel}</span>
                                </td>
                                <td>
                                  <span className={`status-pill ${getStatusTone(version.status)}`}>
                                    {version.status}
                                  </span>
                                </td>
                                <td>{version.baseVersion || "无"}</td>
                                <td className="brand-rule-counts-cell">
                                  <span>设计 {version.ruleCount}</span>
                                  <span>布局 {version.layoutCount}</span>
                                  <span>Prompt {version.promptCount}</span>
                                </td>
                                <td>{formatTime(version.createdAt)}</td>
                                <td className="rule-action-cell">
                                  <div className="rule-action-group">
                                    <button
                                      className="btn ghost rule-action-btn"
                                      disabled={actionDisabled || previewLoadingId === version.id}
                                      type="button"
                                      onClick={() => handleOpenRuleDialog(version, "preview")}
                                    >
                                      {previewLoadingId === version.id ? (
                                        <Loader2 className="spin" size={14} />
                                      ) : (
                                        <Eye size={14} />
                                      )}
                                      查看
                                    </button>
                                    <button
                                      className="btn danger rule-action-btn"
                                      disabled={actionDisabled}
                                      type="button"
                                      onClick={() => handleDeleteVersion(version.id, version.version)}
                                    >
                                      {deletingVersionId === version.id ? (
                                        <Loader2 className="spin" size={14} />
                                      ) : (
                                        <Trash2 size={14} />
                                      )}
                                      {deletingVersionId === version.id ? "删除中" : "删除"}
                                    </button>
                                  </div>
                                </td>
                              </tr>
                            );
                          })
                        ) : (
                          <tr>
                            <td className="table-empty" colSpan={7}>
                              当前品牌还没有规则版本。
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </section>

                <aside className="panel content-panel brand-rule-side-panel">
                  <div className="brand-rule-side-header">
                    <div>
                      <div className="eyebrow">当前版本操作台</div>
                      <h2 className="section-title">{selectedVersion?.version ?? "暂无版本"}</h2>
                      <div className="subtitle">
                        {selectedVersion ? selectedVersion.targetLabel : "当前没有生效版本"}
                      </div>
                    </div>
                    <span className={`status-pill ${selectedVersionStatusTone}`}>
                      {selectedVersion?.status ?? "未选择"}
                    </span>
                  </div>

                  <div className="brand-rule-meta-grid">
                    <div className="brand-rule-meta-card">
                      <span>规则类型</span>
                      <strong>{selectedVersion?.targetLabel ?? "无"}</strong>
                    </div>
                    <div className="brand-rule-meta-card">
                      <span>叠加版本</span>
                      <strong>{selectedVersion?.baseVersion || "无"}</strong>
                    </div>
                    <div className="brand-rule-meta-card">
                      <span>关联 Core Rule</span>
                      <strong>{selectedVersion?.parentVersion || "无"}</strong>
                    </div>
                    <div className="brand-rule-meta-card">
                      <span>创建时间</span>
                      <strong>{formatTime(selectedVersion?.createdAt)}</strong>
                    </div>
                    <div className="brand-rule-meta-card">
                      <span>设计规则</span>
                      <strong>{selectedVersion?.ruleCount ?? 0}</strong>
                    </div>
                    <div className="brand-rule-meta-card">
                      <span>布局规则</span>
                      <strong>{selectedVersion?.layoutCount ?? 0}</strong>
                    </div>
                  </div>

                  <div className="brand-rule-action-list">
                    <button
                      className="btn primary brand-rule-action-wide"
                      disabled={!selectedVersion || previewLoadingId === selectedVersion.id}
                      type="button"
                      onClick={() => (selectedVersion ? handleOpenRuleDialog(selectedVersion, "preview") : null)}
                    >
                      {previewLoadingId === selectedVersion?.id ? (
                        <Loader2 className="spin" size={16} />
                      ) : (
                        <PencilLine size={16} />
                      )}
                      打开预览弹窗
                    </button>
                    <button
                      className="btn ghost brand-rule-action-wide"
                      disabled={!selectedVersion || previewLoadingId === selectedVersion.id}
                      type="button"
                      onClick={() => (selectedVersion ? handleOpenRuleDialog(selectedVersion, "preview") : null)}
                    >
                      {previewLoadingId === selectedVersion?.id ? (
                        <Loader2 className="spin" size={16} />
                      ) : (
                        <Eye size={16} />
                      )}
                    仅预览 Markdown
                    </button>
                    <button
                      className="btn ghost brand-rule-action-wide"
                      disabled={!data.selectedVersionId || selectedVersion?.status === "active" || versionActionLoading}
                      type="button"
                      onClick={handleLoadDiff}
                    >
                      {diffLoading ? <Loader2 className="spin" size={16} /> : <GitCompareArrows size={16} />}
                      {diffLoading ? "对比中..." : "对比当前生效版"}
                    </button>
                    <button
                      className="btn ghost brand-rule-action-wide"
                      disabled={!data.selectedVersionId || selectedVersion?.status === "active" || versionActionLoading}
                      type="button"
                      onClick={handlePublish}
                    >
                      <Rocket size={16} />
                      发布为当前版本
                    </button>
                    <button
                      className="btn ghost brand-rule-action-wide"
                      disabled={!data.selectedVersionId || selectedVersion?.status === "active" || versionActionLoading}
                      type="button"
                      onClick={handleRollback}
                    >
                      <RotateCcw size={16} />
                      回滚到此版本
                    </button>
                  </div>

                  <div className="brand-rule-side-note">
                    Markdown 查看和编辑都已收敛到弹窗内，页面主体专注于版本切换、规则摘要和结构化信息浏览。
                  </div>
                </aside>
              </div>

              {versionDiff ? (
                <section className="panel content-panel brand-rule-diff-panel">
                  <div className="split-line">
                    <div>
                      <h2 className="section-title">版本差异摘要</h2>
                      <div className="subtitle">
                        {versionDiff.base.version} → {versionDiff.compare.version}
                      </div>
                    </div>
                    <button className="btn ghost" type="button" onClick={() => setVersionDiff(null)}>
                      清空差异
                    </button>
                  </div>
                  <div className="diff-panel brand-rule-inline-diff">
                    {Object.entries(versionDiff.diff).map(([section, diff]) => (
                      <div className="diff-section" key={section}>
                        <span className="tag">{section}</span>
                        <div className="subtitle">
                          新增 {diff.added.length} / 删除 {diff.removed.length} / 修改 {diff.changed.length}
                        </div>
                        {[...diff.added, ...diff.removed].slice(0, 4).map((item) => (
                          <div className="diff-item" key={`${section}-${item.title}`}>
                            {item.title}：{item.description}
                          </div>
                        ))}
                        {diff.changed.slice(0, 3).map((item) => (
                          <div className="diff-item" key={`${section}-${item.title}`}>
                            {item.title}：{item.from} → {item.to}
                          </div>
                        ))}
                      </div>
                    ))}
                  </div>
                </section>
              ) : null}

              <div className="content-grid-2">
                <section className="panel content-panel">
                  <div className="split-line">
                    <h2 className="section-title">
                      {selectedVersion?.targetKey === "detail_page_layout" ? "详情页规则说明" : "品牌级规则说明"}
                    </h2>
                    <span className="tag">
                      {selectedVersion?.targetLabel ?? `当前品牌：${data.selectedBrand.name}`}
                    </span>
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
                  <h2 className="section-title">
                    {selectedVersion?.targetKey === "detail_page_layout" ? "页面布局 / 图片区域" : "品牌级布局倾向"}
                  </h2>
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

      {trainOpen ? (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="rules-train-modal">
            <div className="split-line">
              <div>
                <h2 className="section-title">训练规则</h2>
                <div className="subtitle">先选择训练目标，再决定是否叠加同类型历史版本，并生成新的规则版本。</div>
              </div>
              <button className="btn ghost" type="button" onClick={() => setTrainOpen(false)}>
                关闭
              </button>
            </div>

            <div className="rules-train-grid">
              <section className="record-item">
                <strong>当前品牌数字资产</strong>
                <div className="rules-asset-checklist">
                  {data.sourceAssets.length ? (
                    data.sourceAssets.map((asset) => (
                      <label className="rules-check-row" key={asset.id}>
                        <input
                          checked={trainForm.assetIds.includes(asset.id)}
                          type="checkbox"
                          onChange={() => toggleAsset(asset.id)}
                        />
                        <span>
                          <b>{asset.name}</b>
                          <small>
                            {asset.folder} / {asset.status} / {asset.trainingRole} /{" "}
                            {asset.includeInTraining ? "已纳入训练池" : "未纳入训练池"} / {asset.qualityLevel}
                          </small>
                        </span>
                      </label>
                    ))
                  ) : (
                    <div className="hint">当前品牌还没有可用数字资产。</div>
                  )}
                </div>
              </section>

              <section className="record-item">
                <strong>训练设置</strong>
                <label className="field">
                  <span className="field-label">训练目标</span>
                  <select
                    value={trainForm.trainingTarget}
                    onChange={(event) =>
                      setTrainForm((current) => ({
                        ...current,
                        trainingTarget: event.target.value as BrandRuleTarget,
                        prompt: defaultPromptByTarget(event.target.value as BrandRuleTarget),
                        baseVersionId: null,
                        useBaseVersion: false,
                        websiteUrls:
                          event.target.value === "brand_core" ? current.websiteUrls : "",
                      }))
                    }
                  >
                    <option value="brand_core">品牌设计规范</option>
                    <option value="detail_page_layout">详情页布局规范</option>
                  </select>
                </label>
                <label className="switch rules-train-switch">
                  <input
                    checked={trainForm.useBaseVersion}
                    type="checkbox"
                    onChange={(event) =>
                      setTrainForm((current) => ({
                        ...current,
                        useBaseVersion: event.target.checked,
                        baseVersionId: event.target.checked
                          ? current.baseVersionId ?? filteredTrainVersions[0]?.id ?? null
                          : current.baseVersionId,
                      }))
                    }
                  />
                  <span className="switch-track" />
                  叠加之前训练版本
                </label>
                <label className="field">
                  <span className="field-label">选择叠加版本</span>
                  <select
                    disabled={!trainForm.useBaseVersion}
                    value={trainForm.baseVersionId ?? ""}
                    onChange={(event) =>
                      setTrainForm((current) => ({
                        ...current,
                        baseVersionId: event.target.value ? Number(event.target.value) : null,
                      }))
                    }
                  >
                    <option value="">不叠加，创建全新规则</option>
                    {filteredTrainVersions.map((version) => (
                      <option key={version.id} value={version.id}>
                        {version.targetLabel} / {version.version} {version.status === "active" ? "（当前）" : ""}
                      </option>
                    ))}
                  </select>
                </label>
                {trainForm.trainingTarget === "brand_core" ? (
                  <label className="field">
                    <span className="field-label">官网 URL（每行一个）</span>
                    <textarea
                      value={trainForm.websiteUrls}
                      onChange={(event) =>
                        setTrainForm((current) => ({
                          ...current,
                          websiteUrls: event.target.value,
                        }))
                      }
                    />
                  </label>
                ) : (
                  <div className="hint">详情页布局规范主要从详情页素材中提取，不强依赖官网 URL。</div>
                )}
              </section>
            </div>

            <label className="field">
              <span className="field-label">{currentTargetLabel}提示词</span>
              <textarea
                className="prompt"
                value={trainForm.prompt}
                onChange={(event) =>
                  setTrainForm((current) => ({ ...current, prompt: event.target.value }))
                }
              />
            </label>

            <div className="split-line">
              <div className="hint">
                本次将基于 {trainForm.assetIds.length} 个素材训练{currentTargetLabel}
                {trainForm.useBaseVersion ? "，并叠加所选同类型历史版本" : "，创建全新规则"}。
              </div>
              <button className="btn primary" disabled={training} type="button" onClick={handleTrain}>
                {training ? "训练中..." : "开始训练"}
              </button>
            </div>

            {(training || trainingLogs.length > 0) ? (
              <section className="rules-train-progress">
                <div className="split-line">
                  <strong>训练进度</strong>
                  <span className="tag">
                    {trainingStatus}
                    {trainingStage ? ` / ${trainingStage}` : ""}
                  </span>
                </div>
                <pre className="workflow-log">
                  {trainingLogs.length ? trainingLogs.join("\n\n") : "等待训练日志写入..."}
                </pre>
              </section>
            ) : null}
          </div>
        </div>
      ) : null}

      {ruleDialog ? (
        <div
          className="modal-backdrop"
          role="dialog"
          aria-modal="true"
          onClick={(event) => {
            if (event.target === event.currentTarget) {
              setRuleDialog(null);
            }
          }}
        >
          <dialog
            open
            className="brand-rule-dialog"
            onClick={(event) => event.stopPropagation()}
            onCancel={(event) => {
              event.preventDefault();
              setRuleDialog(null);
            }}
          >
            <div className="brand-rule-dialog-header">
              <div>
                <h2 className="section-title">
                  {ruleDialog.mode === "edit" ? "规则 Markdown 编辑" : "规则 Markdown 预览"}
                </h2>
                <div className="subtitle">
                  {data.selectedBrand.name} / {ruleDialog.version}
                </div>
              </div>

              <div className="button-row brand-rule-dialog-actions">
                {ruleDialog.mode === "preview" ? (
                  <button
                    className="btn ghost"
                    disabled={previewLoadingId === ruleDialog.versionId}
                    type="button"
                    onClick={() =>
                      handleOpenRuleDialog(
                        {
                          id: ruleDialog.versionId,
                          version: ruleDialog.version,
                          status: ruleDialog.status,
                          createdAt: ruleDialog.createdAt,
                          baseVersion: ruleDialog.baseVersion ?? "",
                          ruleCount: 0,
                          layoutCount: 0,
                          promptCount: 0,
                          ruleType: selectedVersion?.ruleType ?? "core",
                          pageType: selectedVersion?.pageType ?? "brand_identity",
                          sourceKind: selectedVersion?.sourceKind ?? "asset_batch",
                          parentRuleId: selectedVersion?.parentRuleId ?? null,
                          parentVersion: selectedVersion?.parentVersion ?? "",
                          targetKey: selectedVersion?.targetKey ?? (data.selectedTargetKey ?? "brand_core"),
                          targetLabel:
                            selectedVersion?.targetLabel ??
                            TARGET_LABELS[(data.selectedTargetKey ?? "brand_core") as BrandRuleTarget],
                        },
                        "edit",
                      )
                    }
                  >
                    <PencilLine size={16} />
                    切换到编辑
                  </button>
                ) : (
                  <button
                    className="btn primary"
                    disabled={!data.selectedVersionId || savingMarkdown}
                    type="button"
                    onClick={handleSaveMarkdown}
                  >
                    {savingMarkdown ? <Loader2 className="spin" size={16} /> : <PencilLine size={16} />}
                    {savingMarkdown ? "保存中..." : "保存修改"}
                  </button>
                )}
                <button className="btn ghost" type="button" onClick={() => setRuleDialog(null)}>
                  关闭
                </button>
              </div>
            </div>

            <div className="brand-rule-dialog-meta">
              <span className={`status-pill ${getStatusTone(ruleDialog.status)}`}>
                {ruleDialog.status}
              </span>
              <span>叠加版本：{ruleDialog.baseVersion || "无"}</span>
              <span>创建时间：{formatTime(ruleDialog.createdAt)}</span>
              <span>{ruleDialog.mode === "edit" ? "实时预览已开启" : "只读查看模式"}</span>
            </div>

            <div className={`brand-rule-dialog-body ${ruleDialog.mode === "edit" ? "edit-mode" : ""}`}>
              {ruleDialog.mode === "edit" ? (
                <>
                  <section className="brand-rule-dialog-pane">
                    <div className="brand-rule-dialog-pane-head">
                      <strong>Markdown 源内容</strong>
                      <span className="subtitle">左侧编辑，右侧实时预览</span>
                    </div>
                    <textarea
                      className="markdown-editor brand-rule-editor-dialog"
                      value={ruleDialog.markdown}
                      onChange={(event) => handleDialogMarkdownChange(event.target.value)}
                    />
                  </section>

                  <section className="brand-rule-dialog-pane brand-rule-dialog-preview-pane">
                    <div className="brand-rule-dialog-pane-head">
                      <strong>预览效果</strong>
                      <span className="subtitle">支持标题、表格、列表、代码块</span>
                    </div>
                    <div className="brand-rule-markdown-preview">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {ruleDialog.markdown || "暂无 Markdown 内容。"}
                      </ReactMarkdown>
                    </div>
                  </section>
                </>
              ) : (
                <div className="brand-rule-markdown-preview brand-rule-markdown-preview-single">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {ruleDialog.markdown || "暂无 Markdown 内容。"}
                  </ReactMarkdown>
                </div>
              )}
            </div>
          </dialog>
        </div>
      ) : null}
    </div>
  );
}
