"use client";

import { Eye, GitBranch, RotateCcw, Sparkles, UploadCloud } from "lucide-react";
import type { BrandRuleVersionRecord, RuleVersionDiffResponse } from "@/lib/api";

interface RuleVersionPanelProps {
  versions: BrandRuleVersionRecord[];
  currentRuleVersionId?: string | null;
  selectedRuleVersionId?: string | null;
  diff?: RuleVersionDiffResponse | null;
  loading?: boolean;
  onSelectVersion: (versionId: string) => void;
  onTrain: () => Promise<void>;
  onViewDiff: (versionId: string) => Promise<void>;
  onPublish: (versionId: string) => Promise<void>;
  onRollback: (versionId: string) => Promise<void>;
}

export function RuleVersionPanel({
  versions,
  currentRuleVersionId,
  selectedRuleVersionId,
  diff,
  loading = false,
  onSelectVersion,
  onTrain,
  onViewDiff,
  onPublish,
  onRollback,
}: RuleVersionPanelProps) {
  const selectedVersion = versions.find((item) => item.id === selectedRuleVersionId) ?? null;

  return (
    <section className="panel platform-panel">
      <div className="panel-header">
        <div className="panel-title">规则版本</div>
        <button className="btn primary btn-small" type="button" onClick={() => void onTrain()} disabled={loading}>
          <Sparkles size={14} /> 发起品牌训练
        </button>
      </div>
      <div className="panel-scroll">
        {versions.length ? (
          <div className="platform-inline-stats">
            <span className="mini-stat">版本数 {versions.length}</span>
            <span className="mini-stat">
              当前发布 {versions.find((item) => item.id === currentRuleVersionId)?.version_label ?? "未发布"}
            </span>
          </div>
        ) : null}
        {!versions.length ? <p className="hint">当前品牌还没有规则版本。</p> : null}
        <div className="platform-list">
          {versions.map((version) => {
            const isCurrent = currentRuleVersionId === version.id;
            const isSelected = selectedRuleVersionId === version.id;
            return (
              <div className={`platform-card ${isSelected ? "platform-card-active" : ""}`} key={version.id}>
                <div className="platform-card-head">
                  <div>
                    <div className="platform-card-title">{version.version_label}</div>
                    <div className="platform-card-meta">
                      {version.status} · {version.summary || "暂无摘要"}
                    </div>
                  </div>
                  <span className={`pill ${isCurrent ? "pill-on" : "pill-ghost"}`}>
                    {isCurrent ? "当前生效" : "候选版本"}
                  </span>
                </div>
                <div className="toolbar-row">
                  <button className="btn ghost btn-small" type="button" onClick={() => onSelectVersion(version.id)}>
                    <UploadCloud size={14} /> 用于生成
                  </button>
                  <button className="btn ghost btn-small" type="button" onClick={() => void onViewDiff(version.id)}>
                    <Eye size={14} /> 查看 Diff
                  </button>
                  <button className="btn ghost btn-small" type="button" onClick={() => void onPublish(version.id)}>
                    <GitBranch size={14} /> 发布
                  </button>
                  <button className="btn ghost btn-small" type="button" onClick={() => void onRollback(version.id)}>
                    <RotateCcw size={14} /> 回滚
                  </button>
                </div>
                {version.drift_risks.length ? (
                  <div className="hint">漂移风险：{version.drift_risks.join("；")}</div>
                ) : null}
              </div>
            );
          })}
        </div>

        {selectedVersion ? (
          <div className="platform-card">
            <div className="card-label">选中版本</div>
            <pre className="platform-json">{JSON.stringify(selectedVersion.brand_profile, null, 2)}</pre>
          </div>
        ) : null}

        {diff ? (
          <div className="platform-card">
            <div className="card-label">规则 Diff</div>
            <pre className="platform-json">{JSON.stringify(diff.diff, null, 2)}</pre>
          </div>
        ) : null}
      </div>
    </section>
  );
}
