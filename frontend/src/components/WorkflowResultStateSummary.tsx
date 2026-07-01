"use client";

import type {
  ExportPreflight,
  ExportReview,
  ResultState,
  StageContractCheck,
} from "@/lib/api";

const DELIVERY_LABELS: Record<string, string> = {
  ready: "允许正式导出",
  review_only: "仅可审稿",
  blocked: "已阻断导出",
  ready_for_export: "允许正式导出",
};

const PREFLIGHT_STATUS_LABELS: Record<string, string> = {
  passed: "检查通过",
  warning: "存在风险",
  blocked: "已阻断",
  failed: "检查失败",
};

const ERROR_CODE_LABELS: Record<string, string> = {
  export_preflight_blocked: "导出前检查阻断",
  export_preflight_review_only: "导出前检查要求人工审核",
};

const REASON_CODE_LABELS: Record<string, string> = {
  layout_schema_unavailable: "缺少可执行 layout schema",
  layout_validation_failed: "布局校验失败",
  asset_guard_blocked: "Asset Guard 阻断导出",
  image_generation_contract_failed: "图片生成 contract 未通过",
  copy_contract_failed: "文案 contract 未通过",
};

const WARNING_CODE_LABELS: Record<string, string> = {
  layout_validation_warning: "布局校验存在 warning",
  asset_guard_warning: "Asset Guard 存在 warning",
  image_generation_fallback_used: "图片生成使用回退结果",
  copy_fallback_used: "文案使用回退结果",
  image_generation_retried_before_passing: "图片生成重试后通过",
  copy_retried_before_passing: "文案重试后通过",
};

const STAGE_LABELS: Record<string, string> = {
  image_generation: "图片生成",
  copy: "文案",
};

function statusTone(status?: string | null) {
  const value = String(status || "").toLowerCase();
  if (["ready", "passed", "completed", "success", "ready_for_export"].includes(value)) return "success";
  if (["review_only", "warning", "fallback"].includes(value)) return "warning";
  if (["blocked", "failed", "cancelled"].includes(value)) return "failed";
  return "running";
}

function booleanTone(value?: boolean | null, falseTone: "success" | "warning" | "failed" = "failed") {
  if (value === true) return "success";
  if (value === false) return falseTone;
  return "running";
}

function deliveryLabel(status?: string | null) {
  return DELIVERY_LABELS[String(status || "")] ?? (status || "-");
}

function preflightStatusLabel(status?: string | null) {
  return PREFLIGHT_STATUS_LABELS[String(status || "")] ?? (status || "-");
}

function exportDecisionLabel(decision?: string | null) {
  return DELIVERY_LABELS[String(decision || "")] ?? (decision || "-");
}

function explainCode(
  code: string,
  catalog: Record<string, string>,
  fallbackType: "reason" | "warning",
) {
  if (catalog[code]) return catalog[code];
  for (const [stageId, stageLabel] of Object.entries(STAGE_LABELS)) {
    if (code === `${stageId}_contract_failed`) return `${stageLabel}阶段 contract 未通过`;
    if (code === `${stageId}_fallback_used`) return `${stageLabel}阶段使用了回退结果`;
    if (code === `${stageId}_retried_before_passing`) return `${stageLabel}阶段重试后通过`;
  }
  return fallbackType === "reason" ? "触发了导出降级原因" : "存在需要人工复核的提示";
}

function describeStageCheck(check?: StageContractCheck) {
  if (!check) return "暂无";
  if (check.reason_codes?.length) return "contract 未通过";
  if (check.warning_codes?.length) return "存在 warning";
  if (check.contract_status === "passed" && check.execution_status === "completed") return "通过";
  return `${check.execution_status || "unknown"} / ${check.contract_status || "unknown"}`;
}

function stageCheckTone(check?: StageContractCheck) {
  if (!check) return "running";
  if (check.reason_codes?.length) return "failed";
  if (check.warning_codes?.length) return "warning";
  if (check.contract_status === "passed" && check.execution_status === "completed") return "success";
  return statusTone(check.execution_status || check.contract_status);
}

function firstNote(values?: string[]) {
  return values?.find((item) => item.trim()) ?? "";
}

function schemaHitLabel(value?: boolean | null) {
  if (value === true) return "已命中 layout schema";
  if (value === false) return "未命中 layout schema";
  return "待确认";
}

function fallbackLabel(value?: boolean | null) {
  if (value === true) return "使用了回退结果";
  if (value === false) return "未使用回退";
  return "待确认";
}

function imageSlotLabel(count?: number | null) {
  if (typeof count !== "number") return "待确认";
  return `${count} 个图片槽位`;
}

function formatPercent(value?: number | null) {
  if (typeof value !== "number" || Number.isNaN(value)) return "";
  return `${Math.round(Number(value) * 100)}%`;
}

function stageOutcomeSummary(check?: StageContractCheck) {
  if (!check) return "暂无";
  if (check.reason_codes?.length) return "contract 未通过";
  if (check.warning_codes?.includes(`${check.stage_id}_retried_before_passing`)) return "重试后通过";
  if (check.warning_codes?.length) return "存在 warning";
  if (check.contract_status === "passed" && check.execution_status === "completed") return "直接通过";
  return `${check.execution_status || "unknown"} / ${check.contract_status || "unknown"}`;
}

function buildRetrySummary(
  imageCheck?: StageContractCheck,
  copyCheck?: StageContractCheck,
) {
  const parts: string[] = [];
  if (imageCheck) parts.push(`图片生成：${stageOutcomeSummary(imageCheck)}`);
  if (copyCheck) parts.push(`文案：${stageOutcomeSummary(copyCheck)}`);
  return parts.join("；") || "当前没有 contract / retry 摘要";
}

function buildDecisionExplanation({
  decision,
  layoutSchemaHit,
  imageSlotCount,
  fallbackUsed,
  layoutValidationStatus,
  assetGuardStatus,
  imageCheck,
  copyCheck,
}: {
  decision?: string | null;
  layoutSchemaHit?: boolean | null;
  imageSlotCount?: number | null;
  fallbackUsed?: boolean | null;
  layoutValidationStatus?: string | null;
  assetGuardStatus?: string | null;
  imageCheck?: StageContractCheck;
  copyCheck?: StageContractCheck;
}) {
  const facts: string[] = [];
  if (layoutSchemaHit === true) facts.push("已命中可执行 layout schema");
  if (layoutSchemaHit === false) facts.push("未命中可执行 layout schema");
  if (typeof imageSlotCount === "number") facts.push(`识别到 ${imageSlotCount} 个图片槽位`);
  if (fallbackUsed === true) facts.push("链路中发生过回退");
  if (layoutValidationStatus && ["warning", "failed", "blocked"].includes(layoutValidationStatus)) {
    facts.push(`布局校验为${preflightStatusLabel(layoutValidationStatus)}`);
  }
  if (assetGuardStatus && ["warning", "failed", "blocked"].includes(assetGuardStatus)) {
    facts.push(`Asset Guard 为${preflightStatusLabel(assetGuardStatus)}`);
  }
  if (imageCheck?.reason_codes?.length) facts.push("图片生成 contract 未通过");
  else if (imageCheck?.warning_codes?.length) facts.push("图片生成经历过重试或 warning");
  if (copyCheck?.reason_codes?.length) facts.push("文案 contract 未通过");
  else if (copyCheck?.warning_codes?.length) facts.push("文案经历过重试或 warning");

  const summary = facts.slice(0, 4).join("；");
  if (decision === "ready") {
    return summary
      ? `${summary}，因此当前结果允许正式导出。`
      : "导出前检查通过，当前结果允许正式导出。";
  }
  if (decision === "blocked") {
    return summary
      ? `${summary}，因此当前结果被阻断，只能输出诊断与审稿材料。`
      : "导出前检查存在阻断项，当前结果不能正式导出。";
  }
  return summary
    ? `${summary}，因此当前结果仅建议输出审稿包。`
    : "导出前检查存在风险，当前结果仅建议输出审稿包。";
}

interface ResolvedWorkflowResultStateData {
  resolvedResultState: ResultState | null;
  resolvedPreflight: ExportPreflight | null;
  checks: ExportPreflight["checks"] | ExportReview["checks"] | undefined;
  resolvedDecision: string;
  resolvedErrorCode: string;
  resolvedReasonCodes: string[];
  resolvedWarningCodes: string[];
  layoutSchemaHit: boolean | null;
  imageSlotCount: number | null;
  fallbackUsed: boolean | null;
  layoutValidationStatus: string | null;
  assetGuardStatus: string | null;
  imageStageCheck: StageContractCheck | undefined;
  copyStageCheck: StageContractCheck | undefined;
  slotMatchRate: string;
  reasonDescriptions: Record<string, string>;
  warningDescriptions: Record<string, string>;
}

function resolveWorkflowResultStateData({
  resultState,
  exportReview,
  exportPreflight,
}: {
  resultState?: ResultState | null;
  exportReview?: ExportReview | null;
  exportPreflight?: ExportPreflight | null;
}): ResolvedWorkflowResultStateData {
  const resolvedResultState = resultState ?? null;
  const resolvedPreflight = exportPreflight ?? resolvedResultState?.export_preflight ?? null;
  const checks = resolvedPreflight?.checks ?? exportReview?.checks;
  const resolvedDecision =
    resolvedPreflight?.decision ?? resolvedResultState?.delivery_status ?? exportReview?.status ?? "";
  const resolvedErrorCode =
    resolvedResultState?.error_code || resolvedPreflight?.error_code || exportReview?.error_code || "";
  const resolvedReasonCodes =
    resolvedResultState?.reason_codes ?? resolvedPreflight?.reason_codes ?? exportReview?.reason_codes ?? [];
  const resolvedWarningCodes =
    resolvedResultState?.warning_codes ??
    resolvedPreflight?.warning_codes ??
    exportReview?.warning_codes ??
    [];
  const layoutSchemaHit =
    resolvedResultState?.layout_schema_hit ?? checks?.layout_validation?.guard_can_execute ?? null;
  const imageSlotCount =
    typeof resolvedResultState?.image_slot_count === "number" ? resolvedResultState.image_slot_count : null;
  const fallbackUsed = resolvedResultState?.fallback_used ?? null;
  const layoutValidationStatus =
    resolvedResultState?.layout_validation_status ?? checks?.layout_validation?.status ?? null;
  const assetGuardStatus = resolvedResultState?.asset_guard_status ?? checks?.asset_guard?.status ?? null;
  const imageStageCheck = checks?.stage_contracts?.image_generation;
  const copyStageCheck = checks?.stage_contracts?.copy;
  const slotMatchRate = formatPercent(resolvedResultState?.slot_match_rate);
  const reasonDescriptions = Object.fromEntries(
    resolvedReasonCodes.map((code) => [code, explainCode(code, REASON_CODE_LABELS, "reason")]),
  );
  const warningDescriptions = Object.fromEntries(
    resolvedWarningCodes.map((code) => [code, explainCode(code, WARNING_CODE_LABELS, "warning")]),
  );

  return {
    resolvedResultState,
    resolvedPreflight,
    checks,
    resolvedDecision,
    resolvedErrorCode,
    resolvedReasonCodes,
    resolvedWarningCodes,
    layoutSchemaHit,
    imageSlotCount,
    fallbackUsed,
    layoutValidationStatus,
    assetGuardStatus,
    imageStageCheck,
    copyStageCheck,
    slotMatchRate,
    reasonDescriptions,
    warningDescriptions,
  };
}

function reviewRequirementLabel(decision?: string | null) {
  if (decision === "ready") return "无需 review";
  if (decision === "blocked") return "已阻断";
  if (decision === "review_only") return "需要 review";
  return "review 待确认";
}

function slotCountTone(value?: number | null) {
  if (typeof value !== "number") return "running";
  return value > 0 ? "success" : "failed";
}

function buildCompactSummaryNote(
  data: ResolvedWorkflowResultStateData,
  exportReview?: ExportReview | null,
) {
  const firstReasonCode = data.resolvedReasonCodes[0];
  if (firstReasonCode) return data.reasonDescriptions[firstReasonCode] || firstReasonCode;
  const firstWarningCode = data.resolvedWarningCodes[0];
  if (firstWarningCode) return data.warningDescriptions[firstWarningCode] || firstWarningCode;
  if (data.resolvedPreflight?.message) return data.resolvedPreflight.message;
  if (exportReview?.message) return exportReview.message;
  if (data.resolvedResultState?.reasons?.[0]) return data.resolvedResultState.reasons[0];
  if (data.resolvedResultState?.warnings?.[0]) return data.resolvedResultState.warnings[0];
  return buildDecisionExplanation({
    decision: data.resolvedDecision,
    layoutSchemaHit: data.layoutSchemaHit,
    imageSlotCount: data.imageSlotCount,
    fallbackUsed: data.fallbackUsed,
    layoutValidationStatus: data.layoutValidationStatus,
    assetGuardStatus: data.assetGuardStatus,
    imageCheck: data.imageStageCheck,
    copyCheck: data.copyStageCheck,
  });
}

function CodeGroup({
  label,
  codes,
  descriptions,
}: {
  label: string;
  codes?: string[];
  descriptions: Record<string, string>;
}) {
  if (!codes?.length) return null;
  return (
    <div className="status-code-group">
      <div className="card-label">{label}</div>
      <div className="chips">
        {codes.map((code) => (
          <span className="chip-static status-code-chip" key={code} title={descriptions[code] || code}>
            {code}
          </span>
        ))}
      </div>
      <div className="status-note-list compact">
        {codes.map((code) => (
          <div className="status-note-item" key={`${label}-${code}`}>
            <strong>{code}</strong>
            <span>{descriptions[code] || code}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function WorkflowResultStateSummary({
  resultState,
  exportReview,
  exportPreflight,
  title = "结构化结果状态",
  className = "",
}: {
  resultState?: ResultState | null;
  exportReview?: ExportReview | null;
  exportPreflight?: ExportPreflight | null;
  title?: string;
  className?: string;
}) {
  const {
    resolvedResultState,
    resolvedPreflight,
    checks,
    resolvedDecision,
    resolvedErrorCode,
    resolvedReasonCodes,
    resolvedWarningCodes,
    layoutSchemaHit,
    imageSlotCount,
    fallbackUsed,
    layoutValidationStatus,
    assetGuardStatus,
    imageStageCheck,
    copyStageCheck,
    slotMatchRate,
    reasonDescriptions,
    warningDescriptions,
  } = resolveWorkflowResultStateData({ resultState, exportReview, exportPreflight });

  if (!resolvedResultState && !exportReview && !resolvedPreflight) return null;

  return (
    <section className={`panel content-panel ${className}`.trim()}>
      <div className="card-label">{title}</div>
      <div className="result-state-header">
        <div className="result-state-topline">
          <span className={`status-pill ${statusTone(resolvedResultState?.delivery_status)}`}>
            {deliveryLabel(resolvedResultState?.delivery_status)}
          </span>
          {resolvedPreflight?.status ? (
            <span className={`status-pill ${statusTone(resolvedPreflight.status)}`}>
              {preflightStatusLabel(resolvedPreflight.status)}
            </span>
          ) : null}
          {resolvedResultState?.tier ? (
            <span className="chip-static">结果等级：{resolvedResultState.tier}</span>
          ) : null}
        </div>
        {resolvedPreflight?.message || exportReview?.message ? (
          <p className="hint">{resolvedPreflight?.message || exportReview?.message}</p>
        ) : null}
        <p className="hint">
          {buildDecisionExplanation({
            decision: resolvedDecision,
            layoutSchemaHit,
            imageSlotCount,
            fallbackUsed,
            layoutValidationStatus,
            assetGuardStatus,
            imageCheck: imageStageCheck,
            copyCheck: copyStageCheck,
          })}
        </p>
      </div>

      <div className="result-state-checks">
        <div className="result-state-check">
          <div className="card-label">最终判定</div>
          <span className={`status-pill ${statusTone(resolvedDecision)}`}>
            {exportDecisionLabel(resolvedDecision)}
          </span>
          <p className="hint">
            export_preflight：{resolvedPreflight ? preflightStatusLabel(resolvedPreflight.status) : "暂无"}
          </p>
        </div>
        <div className="result-state-check">
          <div className="card-label">结构命中</div>
          <span className={`status-pill ${booleanTone(layoutSchemaHit)}`}>{schemaHitLabel(layoutSchemaHit)}</span>
          <p className="hint">
            布局校验：{layoutValidationStatus ? preflightStatusLabel(layoutValidationStatus) : "暂无"}
          </p>
        </div>
        <div className="result-state-check">
          <div className="card-label">图片槽位</div>
          <span
            className={`status-pill ${
              typeof imageSlotCount !== "number"
                ? "running"
                : imageSlotCount > 0
                  ? "success"
                  : "failed"
            }`}
          >
            {imageSlotLabel(imageSlotCount)}
          </span>
          <p className="hint">
            {typeof imageSlotCount === "number"
              ? imageSlotCount > 0
                ? `已识别 ${imageSlotCount} 个图片槽位${slotMatchRate ? `，素材命中率 ${slotMatchRate}` : ""}`
                : "当前未识别到图片槽位，正式导出前需先补齐结构或素材映射"
              : "当前没有可用的图片槽位统计"}
          </p>
        </div>
        <div className="result-state-check">
          <div className="card-label">回退 / 重试</div>
          <span className={`status-pill ${booleanTone(fallbackUsed, "success")}`}>{fallbackLabel(fallbackUsed)}</span>
          <p className="hint">{buildRetrySummary(imageStageCheck, copyStageCheck)}</p>
        </div>
      </div>

      <div className="result-state-checks">
        <div className="result-state-check">
          <div className="card-label">布局校验</div>
          <span className={`status-pill ${statusTone(checks?.layout_validation?.status)}`}>
            {preflightStatusLabel(checks?.layout_validation?.status)}
          </span>
          <p className="hint">
            {checks?.layout_validation?.guard_can_execute ? "已命中可执行 schema" : "未命中可执行 schema"}
          </p>
        </div>
        <div className="result-state-check">
          <div className="card-label">Asset Guard</div>
          <span className={`status-pill ${statusTone(checks?.asset_guard?.status)}`}>
            {preflightStatusLabel(checks?.asset_guard?.status)}
          </span>
          <p className="hint">
            {checks?.asset_guard?.can_export ? "素材守门允许导出" : "素材守门要求人工复核"}
          </p>
        </div>
        <div className="result-state-check">
          <div className="card-label">图片生成</div>
          <span
            className={`status-pill ${stageCheckTone(checks?.stage_contracts?.image_generation)}`}
          >
            {describeStageCheck(checks?.stage_contracts?.image_generation)}
          </span>
          <p className="hint">
            {firstNote(
              checks?.stage_contracts?.image_generation?.reasons ||
                checks?.stage_contracts?.image_generation?.warnings,
            ) || "未发现额外风险"}
          </p>
        </div>
        <div className="result-state-check">
          <div className="card-label">文案</div>
          <span className={`status-pill ${stageCheckTone(checks?.stage_contracts?.copy)}`}>
            {describeStageCheck(checks?.stage_contracts?.copy)}
          </span>
          <p className="hint">
            {firstNote(checks?.stage_contracts?.copy?.reasons || checks?.stage_contracts?.copy?.warnings) ||
              "未发现额外风险"}
          </p>
        </div>
      </div>

      <div className="result-state-checks">
        <div className="result-state-check">
          <div className="card-label">错误码</div>
          {resolvedErrorCode ? (
            <>
              <div className="chips">
                <span className="chip-static status-code-chip" title={ERROR_CODE_LABELS[resolvedErrorCode]}>
                  {resolvedErrorCode}
                </span>
              </div>
              <p className="hint">
                {ERROR_CODE_LABELS[resolvedErrorCode] || "导出前检查给出的稳定错误码"}
              </p>
            </>
          ) : (
            <p className="hint">当前无稳定错误码</p>
          )}
        </div>
        <div className="result-state-check">
          <div className="card-label">原因码</div>
          {resolvedReasonCodes.length ? (
            <>
              <div className="chips">
                {resolvedReasonCodes.slice(0, 3).map((code) => (
                  <span className="chip-static status-code-chip" key={`summary-reason-${code}`}>
                    {code}
                  </span>
                ))}
              </div>
              <p className="hint">{reasonDescriptions[resolvedReasonCodes[0]] || resolvedReasonCodes[0]}</p>
            </>
          ) : (
            <p className="hint">当前无导出阻断/降级原因码</p>
          )}
        </div>
        <div className="result-state-check">
          <div className="card-label">提示码</div>
          {resolvedWarningCodes.length ? (
            <>
              <div className="chips">
                {resolvedWarningCodes.slice(0, 3).map((code) => (
                  <span className="chip-static status-code-chip" key={`summary-warning-${code}`}>
                    {code}
                  </span>
                ))}
              </div>
              <p className="hint">{warningDescriptions[resolvedWarningCodes[0]] || resolvedWarningCodes[0]}</p>
            </>
          ) : (
            <p className="hint">当前无人工复核提示码</p>
          )}
        </div>
        <div className="result-state-check">
          <div className="card-label">Guard 最终状态</div>
          <span className={`status-pill ${statusTone(assetGuardStatus)}`}>
            {assetGuardStatus ? preflightStatusLabel(assetGuardStatus) : "暂无"}
          </span>
          <p className="hint">
            {assetGuardStatus
              ? assetGuardStatus === "passed"
                ? "Asset Guard 已放行正式导出"
                : assetGuardStatus === "warning"
                  ? "Asset Guard 允许继续，但需要人工复核"
                  : "Asset Guard 当前阻断正式导出"
              : "当前没有 Asset Guard 汇总状态"}
          </p>
        </div>
      </div>

      <CodeGroup
        label="原因码"
        codes={resolvedReasonCodes}
        descriptions={reasonDescriptions}
      />
      <CodeGroup
        label="提示码"
        codes={resolvedWarningCodes}
        descriptions={warningDescriptions}
      />

      {(resolvedResultState?.reasons?.length ||
        resolvedResultState?.warnings?.length ||
        resolvedResultState?.recommended_actions?.length ||
        exportReview?.recommended_actions?.length) ? (
        <div className="result-state-notes">
          {resolvedResultState?.reasons?.length ? (
            <div className="status-note-list">
              <div className="card-label">阻断 / 降级原因</div>
              {resolvedResultState.reasons.map((item) => (
                <div className="status-note-item" key={`reason-${item}`}>
                  <strong>原因</strong>
                  <span>{item}</span>
                </div>
              ))}
            </div>
          ) : null}
          {resolvedResultState?.warnings?.length ? (
            <div className="status-note-list">
              <div className="card-label">人工复核提示</div>
              {resolvedResultState.warnings.map((item) => (
                <div className="status-note-item" key={`warning-${item}`}>
                  <strong>提示</strong>
                  <span>{item}</span>
                </div>
              ))}
            </div>
          ) : null}
          {(resolvedResultState?.recommended_actions?.length || exportReview?.recommended_actions?.length) ? (
            <div className="status-note-list">
              <div className="card-label">建议下一步</div>
              {(resolvedResultState?.recommended_actions ?? exportReview?.recommended_actions ?? []).map((item) => (
                <div className="status-note-item" key={`action-${item}`}>
                  <strong>动作</strong>
                  <span>{item}</span>
                </div>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

export function WorkflowResultStateCompactSummary({
  resultState,
  exportReview,
  exportPreflight,
  className = "",
}: {
  resultState?: ResultState | null;
  exportReview?: ExportReview | null;
  exportPreflight?: ExportPreflight | null;
  className?: string;
}) {
  const data = resolveWorkflowResultStateData({ resultState, exportReview, exportPreflight });

  if (!data.resolvedResultState && !exportReview && !data.resolvedPreflight) return null;

  const compactNote = buildCompactSummaryNote(data, exportReview);

  return (
    <div className={`result-state-compact ${className}`.trim()}>
      <div className="result-state-compact-row">
        <span className={`status-pill ${statusTone(data.resolvedDecision)}`}>
          {exportDecisionLabel(data.resolvedDecision)}
        </span>
        {data.resolvedResultState?.tier ? (
          <span className="chip-static">等级：{data.resolvedResultState.tier}</span>
        ) : null}
        <span className={`status-pill ${statusTone(data.resolvedDecision)}`}>
          {reviewRequirementLabel(data.resolvedDecision)}
        </span>
        {data.fallbackUsed !== null ? (
          <span className={`status-pill ${booleanTone(data.fallbackUsed, "success")}`}>
            {fallbackLabel(data.fallbackUsed)}
          </span>
        ) : null}
        {data.layoutSchemaHit !== null ? (
          <span className={`status-pill ${booleanTone(data.layoutSchemaHit)}`}>
            {schemaHitLabel(data.layoutSchemaHit)}
          </span>
        ) : null}
        {typeof data.imageSlotCount === "number" ? (
          <span className={`status-pill ${slotCountTone(data.imageSlotCount)}`}>
            {imageSlotLabel(data.imageSlotCount)}
          </span>
        ) : null}
      </div>
      {compactNote ? <p className="result-state-compact-note">{compactNote}</p> : null}
    </div>
  );
}
