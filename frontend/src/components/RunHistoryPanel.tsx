"use client";

import { Clock3, ExternalLink } from "lucide-react";
import { API_BASE, type WorkflowRunRecord } from "@/lib/api";

interface RunHistoryPanelProps {
  runs: WorkflowRunRecord[];
  selectedRunId?: string | null;
  onSelectRun: (runId: string) => void;
}

export function RunHistoryPanel({ runs, selectedRunId, onSelectRun }: RunHistoryPanelProps) {
  const selectedRun = runs.find((item) => item.id === selectedRunId) ?? null;

  return (
    <section className="panel platform-panel">
      <div className="panel-header">
        <div className="panel-title">历史任务</div>
      </div>
      <div className="panel-scroll">
        {!runs.length ? <p className="hint">当前品牌还没有历史任务记录。</p> : null}
        <div className="platform-list">
          {runs.map((run) => (
            <button
              className={`platform-card platform-card-button ${
                selectedRunId === run.id ? "platform-card-active" : ""
              }`}
              key={run.id}
              type="button"
              onClick={() => onSelectRun(run.id)}
            >
              <div className="platform-card-head">
                <div>
                  <div className="platform-card-title">{run.project_name || run.product_name}</div>
                  <div className="platform-card-meta">
                    {run.product_name} · {run.status}
                  </div>
                </div>
                <span className="pill pill-ghost">
                  <Clock3 size={12} />
                  {run.run_started_at?.slice(0, 19).replace("T", " ") ?? "-"}
                </span>
              </div>
            </button>
          ))}
        </div>

        {selectedRun ? (
          <div className="platform-card">
            <div className="card-label">任务详情</div>
            <div className="kv-list">
              <div><strong>任务 ID：</strong>{selectedRun.id}</div>
              <div><strong>规则版本：</strong>{selectedRun.rule_version_id ?? "-"}</div>
              <div><strong>输入资产：</strong>{selectedRun.asset_names.join("、") || "-"}</div>
              <div><strong>开始时间：</strong>{selectedRun.run_started_at ?? "-"}</div>
              <div><strong>结束时间：</strong>{selectedRun.run_finished_at ?? "-"}</div>
            </div>
            <div className="toolbar-row">
              {selectedRun.artifacts.preview_svg ? (
                <a
                  className="download"
                  href={`${API_BASE}/api/runs/${selectedRun.id}/artifacts/preview.svg`}
                  target="_blank"
                  rel="noreferrer"
                >
                  <ExternalLink size={14} /> 预览 SVG
                </a>
              ) : null}
              {selectedRun.artifacts.design_spec ? (
                <a
                  className="download"
                  href={`${API_BASE}/api/runs/${selectedRun.id}/artifacts/design_spec.json`}
                  target="_blank"
                  rel="noreferrer"
                >
                  <ExternalLink size={14} /> 设计 JSON
                </a>
              ) : null}
            </div>
          </div>
        ) : null}
      </div>
    </section>
  );
}
