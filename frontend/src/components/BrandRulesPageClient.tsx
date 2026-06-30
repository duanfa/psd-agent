"use client";

import { useState } from "react";
import {
  fetchBrandRuleDiff,
  fetchBrandRuleTrainLogs,
  fetchBrandRulesPageWithFilters,
  publishBrandRule,
  rollbackBrandRule,
  trainBrandRules,
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
  const [markdown, setMarkdown] = useState(initialData.markdown);
  const [trainForm, setTrainForm] = useState({
    assetIds: initialData.sourceAssets.map((item) => item.id),
    prompt: initialData.trainingPrompt,
    websiteUrls: initialData.websiteUrls.join("\n"),
    baseVersionId: initialData.selectedVersionId ?? null,
    useBaseVersion: Boolean(initialData.selectedVersionId),
  });

  const loadData = async (brandId: number, versionId?: number | null) => {
    setLoading(true);
    setError(null);
    try {
      const next = await fetchBrandRulesPageWithFilters({
        brandId,
        versionId: versionId ?? undefined,
      });
      setData(next);
      setMarkdown(next.markdown);
      setTrainForm({
        assetIds: next.sourceAssets.map((item) => item.id),
        prompt: next.trainingPrompt,
        websiteUrls: next.websiteUrls.join("\n"),
        baseVersionId: next.selectedVersionId ?? null,
        useBaseVersion: Boolean(next.selectedVersionId),
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  const handleBrandChange = async (brandId: number) => {
    if (brandId === data.selectedBrand.id) return;
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
      await loadData(data.selectedBrand.id, data.selectedVersionId);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSavingMarkdown(false);
    }
  };

  const selectedVersion = data.versions.find((version) => version.id === data.selectedVersionId);
  const activeVersion = data.versions.find((version) => version.status === "active");

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
            训练规则
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
                          {version.version} {version.status === "active" ? "（当前）" : ""}
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
              <section className="panel content-panel">
                <div className="split-line">
                  <div>
                    <h2 className="section-title">规则 Markdown</h2>
                    <div className="subtitle">
                      当前状态：{selectedVersion?.status ?? "未选择"}
                      {activeVersion ? ` / 生效版本：${activeVersion.version}` : ""}
                    </div>
                  </div>
                  <div className="button-row">
                    <button
                      className="btn ghost"
                      disabled={!data.selectedVersionId || savingMarkdown}
                      type="button"
                      onClick={handleSaveMarkdown}
                    >
                      {savingMarkdown ? "保存中..." : "保存修改"}
                    </button>
                    <button
                      className="btn ghost"
                      disabled={!data.selectedVersionId || selectedVersion?.status === "active" || versionActionLoading}
                      type="button"
                      onClick={handleLoadDiff}
                    >
                      {diffLoading ? "对比中..." : "对比当前"}
                    </button>
                    <button
                      className="btn ghost"
                      disabled={!data.selectedVersionId || selectedVersion?.status === "active" || versionActionLoading}
                      type="button"
                      onClick={handlePublish}
                    >
                      发布为当前
                    </button>
                    <button
                      className="btn ghost"
                      disabled={!data.selectedVersionId || selectedVersion?.status === "active" || versionActionLoading}
                      type="button"
                      onClick={handleRollback}
                    >
                      回滚到此版
                    </button>
                  </div>
                </div>
                {versionDiff ? (
                  <div className="diff-panel">
                    <strong>
                      版本差异：{versionDiff.base.version} → {versionDiff.compare.version}
                    </strong>
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
                ) : null}
                <textarea
                  className="markdown-editor"
                  value={markdown}
                  onChange={(event) => setMarkdown(event.target.value)}
                />
              </section>

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

      {trainOpen ? (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="rules-train-modal">
            <div className="split-line">
              <div>
                <h2 className="section-title">训练规则</h2>
                <div className="subtitle">选择素材，决定是否叠加历史版本，再根据提示词生成新的品牌规则。</div>
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
                          <small>{asset.folder} / {asset.status}</small>
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
                <label className="switch rules-train-switch">
                  <input
                    checked={trainForm.useBaseVersion}
                    type="checkbox"
                    onChange={(event) =>
                      setTrainForm((current) => ({
                        ...current,
                        useBaseVersion: event.target.checked,
                        baseVersionId: event.target.checked
                          ? current.baseVersionId ?? data.selectedVersionId ?? data.versions[0]?.id ?? null
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
                    {data.versions.map((version) => (
                      <option key={version.id} value={version.id}>
                        {version.version} {version.status === "active" ? "（当前）" : ""}
                      </option>
                    ))}
                  </select>
                </label>
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
              </section>
            </div>

            <label className="field">
              <span className="field-label">训练规则提示词</span>
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
                本次将基于 {trainForm.assetIds.length} 个素材
                {trainForm.useBaseVersion ? "叠加所选历史版本" : "创建全新规则"}，生成后可继续手动修改。
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
    </div>
  );
}
