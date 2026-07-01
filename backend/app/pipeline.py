from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from . import database
from .input_layers import build_input_layers, render_input_prompt, semantic_brief_text
from .llm import LLMClient, LLMUnavailable
from .models import (
    StageResult,
    StagePayloadValidationError,
    UploadedAsset,
    WorkflowRequest,
    get_stage_contract_error_info,
    normalize_layout_schema_payload,
    validate_layout_schema_payload,
    validate_stage_contract_payload,
)
from .retry_settings import RetryPolicy, resolve_stage_retry_policy
from .runtime import append_log, append_stage_result, reset_run, set_run_state


class WorkflowCancelled(Exception):
    """用户主动中断工作流。"""


# ----------------------------- 素材归类 -----------------------------

IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp")
FONT_EXT = (".ttf", ".otf", ".woff", ".woff2")
VIDEO_EXT = (".mp4", ".mov", ".avi", ".mkv")
BRIEF_EXT = (".xlsx", ".xls", ".csv")


def classify_asset(name: str, content_type: str | None) -> str:
    lower = name.lower()
    ctype = (content_type or "").lower()
    if ctype.startswith("image/") or lower.endswith(IMAGE_EXT):
        return "image"
    if lower.endswith(BRIEF_EXT):
        return "brief"
    if lower.endswith(FONT_EXT):
        return "font"
    if ctype.startswith("video/") or lower.endswith(VIDEO_EXT):
        return "video"
    return "reference"


def summarize_assets(assets: list[UploadedAsset]) -> dict[str, list[str]]:
    buckets: dict[str, list[str]] = {
        "image": [],
        "brief": [],
        "reference_image": [],
        "font": [],
        "video": [],
        "reference": [],
    }
    for asset in assets:
        buckets.setdefault(asset.bucket, []).append(asset.name)
    return buckets


# ----------------------------- 流水线上下文 -----------------------------


@dataclass
class PipelineContext:
    request: WorkflowRequest
    assets: list[UploadedAsset]
    llm: LLMClient
    run_id: str = ""
    cancel_checker: Callable[[], bool] = lambda: False
    warnings: list[str] = field(default_factory=list)
    product_info: dict[str, Any] = field(default_factory=dict)
    structured_info: dict[str, Any] = field(default_factory=dict)
    brand_profile: dict[str, Any] = field(default_factory=dict)
    design_direction: dict[str, Any] = field(default_factory=dict)
    generated_images: list[dict[str, Any]] = field(default_factory=list)
    modules: list[dict[str, Any]] = field(default_factory=list)
    psd_layers: list[dict[str, Any]] = field(default_factory=list)
    design_score: dict[str, Any] = field(default_factory=dict)
    feedback_plan: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)
    report_parts: list[str] = field(default_factory=list)
    core_rule: dict[str, Any] = field(default_factory=dict)
    detail_page_rule: dict[str, Any] = field(default_factory=dict)
    layout_blueprint: list[dict[str, Any]] = field(default_factory=list)
    requirement_constraints: dict[str, Any] = field(default_factory=dict)
    feedback_constraints: dict[str, Any] = field(default_factory=dict)
    effective_constraints: dict[str, Any] = field(default_factory=dict)
    layout_validation: dict[str, Any] = field(default_factory=dict)
    asset_match_report: dict[str, Any] = field(default_factory=dict)
    asset_guard: dict[str, Any] = field(default_factory=dict)
    result_state: dict[str, Any] = field(default_factory=dict)
    intermediate_preview: dict[str, Any] = field(default_factory=dict)
    stage_contracts: dict[str, Any] = field(default_factory=dict)
    stage_execution: dict[str, Any] = field(default_factory=dict)
    input_layers: dict[str, Any] = field(default_factory=dict)

    @property
    def images(self) -> list[str]:
        return [a.name for a in self.assets if a.bucket == "image"]

    @property
    def reference_images(self) -> list[str]:
        return [a.name for a in self.assets if a.bucket == "reference_image"]

    @property
    def reference_image_paths(self) -> list[str]:
        return [
            a.saved_path
            for a in self.assets
            if a.bucket == "reference_image" and a.saved_path
        ]

    @property
    def generated_image_names(self) -> list[str]:
        return [str(item.get("name") or "") for item in self.generated_images if item.get("name")]

    @property
    def image_paths(self) -> list[str]:
        return [
            a.saved_path
            for a in self.assets
            if a.bucket == "image" and a.saved_path
        ]

    @property
    def fonts(self) -> list[str]:
        return [a.name for a in self.assets if a.bucket == "font"]

    @property
    def strict_mode(self) -> bool:
        return self.request.workflow_mode.value == "strict_brand"

    def check_cancelled(self, checkpoint: str) -> None:
        if self.cancel_checker():
            append_log(self.run_id, "Workflow", f"用户已请求中断，停止于：{checkpoint}")
            set_run_state(self.run_id, "cancelled", None)
            raise WorkflowCancelled(f"用户已中断生成任务（{checkpoint}）")


def _workflow_log(run_id: str, message: str, payload: Any | None = None) -> None:
    append_log(run_id, "Workflow", message, payload)


class StageContractError(Exception):
    """阶段输出未通过结构校验，且重试后仍失败。"""

    def __init__(
        self,
        message: str,
        *,
        stage_id: str = "",
        error_code: str = "stage_contract_validation_failed",
        reason_codes: list[str] | None = None,
        issues: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.stage_id = stage_id
        self.error_code = error_code
        self.reason_codes = list(reason_codes or [])
        self.issues = list(issues or [])


def _split_validation_issues(exc: Exception) -> list[str]:
    text = str(exc).strip() or exc.__class__.__name__
    issues = [item.strip() for item in text.split("；") if item.strip()]
    return issues or [text]


def _resolve_retry_policy(stage_id: str) -> RetryPolicy:
    return resolve_stage_retry_policy(stage_id)


def _retry_policy_payload(policy: RetryPolicy) -> dict[str, Any]:
    return {
        "enabled": bool(policy.enabled),
        "max_attempts": max(1, int(policy.max_attempts or 1)),
        "retryable_error_codes": list(policy.retryable_error_codes),
        "non_retryable_error_codes": list(policy.non_retryable_error_codes),
    }


_CRITICAL_STAGE_IDS = ("image_generation", "layout_engine", "copy", "figma_psd")


def _stage_retry_exhausted_code(stage_id: str) -> str:
    return f"{stage_id}_retry_exhausted"


def _guard_error_code(guard_name: str, status: str) -> str:
    normalized = str(status or "").strip().lower()
    if normalized in {"failed", "blocked"}:
        return f"{guard_name}_blocked"
    if normalized == "warning":
        return f"{guard_name}_warning"
    return ""


def _retry_summary_payload(stage_id: str, contract: Any) -> dict[str, Any]:
    if not isinstance(contract, dict):
        return {}
    attempt_count = max(0, int(contract.get("attempt_count") or 0))
    retries_used = max(0, int(contract.get("retries_used") or 0))
    max_attempts = max(1, int(contract.get("max_attempts") or attempt_count or 1))
    final_status = str(contract.get("final_status") or contract.get("status") or "")
    stop_reason = str(contract.get("stop_reason") or "")
    if final_status == "passed" and retries_used > 0:
        retry_status = "passed_after_retry"
    elif final_status == "passed":
        retry_status = "not_needed"
    elif stop_reason == "max_attempts_reached":
        retry_status = "retry_exhausted"
    elif stop_reason == "non_retryable_error":
        retry_status = "not_retryable"
    elif stop_reason == "retry_disabled":
        retry_status = "retry_disabled"
    elif retries_used > 0:
        retry_status = "failed_after_retry"
    else:
        retry_status = "failed_without_retry"
    return {
        "status": retry_status,
        "attempt_count": attempt_count,
        "retries_used": retries_used,
        "max_attempts": max_attempts,
        "did_retry": bool(contract.get("did_retry")) if "did_retry" in contract else retries_used > 0,
        "error_code": (
            _stage_retry_exhausted_code(stage_id)
            if retry_status == "retry_exhausted"
            else ""
        ),
        "final_error_code": str(contract.get("final_error_code") or ""),
    }


def _stage_telemetry_payload(execution: Any) -> dict[str, Any] | None:
    if not isinstance(execution, dict):
        return None
    return {
        "status": str(execution.get("status") or ""),
        "started_at": str(execution.get("started_at") or ""),
        "completed_at": str(execution.get("completed_at") or ""),
        "duration_ms": int(execution.get("duration_ms") or execution.get("elapsed_ms") or 0),
        "error_code": str(execution.get("error_code") or ""),
        "retry": dict(execution.get("retry") or {}),
    }


def _critical_stage_payloads(ctx: PipelineContext) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for stage_id in _CRITICAL_STAGE_IDS:
        execution = ctx.stage_execution.get(stage_id)
        if telemetry := _stage_telemetry_payload(execution):
            payload[stage_id] = telemetry
    return payload


def _critical_check_payloads(
    ctx: PipelineContext,
    export_preflight: dict[str, Any],
) -> dict[str, Any]:
    return {
        "layout_guard": {
            "status": str(ctx.layout_validation.get("status") or ""),
            "error_code": str(ctx.layout_validation.get("error_code") or ""),
        },
        "asset_guard": {
            "status": str(ctx.asset_guard.get("status") or ""),
            "error_code": str(ctx.asset_guard.get("error_code") or ""),
        },
        "export_preflight": {
            "status": str(export_preflight.get("status") or ""),
            "error_code": str(export_preflight.get("error_code") or ""),
        },
    }


def _extract_validation_failure(exc: Exception) -> tuple[str, str, str, list[str]]:
    if isinstance(exc, StagePayloadValidationError):
        issues = list(exc.issues) or _split_validation_issues(exc)
        info = get_stage_contract_error_info(exc.error_code)
        return (
            info["error_code"],
            str(exc.error_category or info["error_category"]),
            str(exc.error_family or info["error_family"]),
            issues[:8],
        )
    info = get_stage_contract_error_info("contract_violation")
    return (
        info["error_code"],
        info["error_category"],
        info["error_family"],
        _split_validation_issues(exc)[:8],
    )


def _is_retryable_contract_error(policy: RetryPolicy, error_code: str) -> bool:
    if not policy.enabled:
        return False
    if error_code in policy.non_retryable_error_codes:
        return False
    return error_code in policy.retryable_error_codes


def _build_contract_retry_metadata(
    *,
    stage_id: str,
    policy: RetryPolicy,
    history: list[dict[str, Any]],
    final_status: str,
    final_error_code: str,
    final_error_category: str,
    final_error_family: str,
    issues: list[str],
    stop_reason: str,
) -> dict[str, Any]:
    attempt_count = len(history)
    retries_used = max(0, attempt_count - 1)
    metadata = {
        "status": final_status,
        "final_status": final_status,
        "stage_id": stage_id,
        "attempt_count": attempt_count,
        "retries_used": retries_used,
        "did_retry": retries_used > 0,
        "max_attempts": max(1, int(policy.max_attempts or 1)),
        "stop_reason": stop_reason,
        "error_code": _stage_contract_failure_code(stage_id) if final_status == "failed" else "",
        "final_error_code": final_error_code,
        "error_category": final_error_category if final_status == "failed" else "",
        "error_family": final_error_family if final_status == "failed" else "",
        "final_error_category": final_error_category,
        "final_error_family": final_error_family,
        "reason_codes": [_stage_contract_reason_code(stage_id)] if final_status == "failed" else [],
        "issues": list(issues[:8]),
        "policy": _retry_policy_payload(policy),
        "history": history,
    }
    metadata["retry"] = _retry_summary_payload(stage_id, metadata)
    return metadata


def _dedupe_text_items(values: list[str]) -> list[str]:
    items: list[str] = []
    for raw in values:
        text = str(raw or "").strip()
        if text and text not in items:
            items.append(text)
    return items


def _summarize_missing_targets(issues: list[str]) -> str:
    targets: list[str] = []
    for issue in issues:
        match = re.search(r"缺少\s+(.+)$", issue)
        if match:
            targets.append(match.group(1).strip())
            continue
        match = re.search(r"必填字段：(.+)$", issue)
        if match:
            targets.extend(
                item.strip()
                for item in re.split(r"[、,，/]", match.group(1))
                if item.strip()
            )
            continue
        match = re.search(r"至少需要\s+(.+)$", issue)
        if match:
            targets.append(match.group(1).strip())
    return "；".join(_dedupe_text_items(targets)[:6])


def _summarize_reference_targets(issues: list[str]) -> str:
    targets: list[str] = []
    for issue in issues:
        if "：" not in issue:
            continue
        targets.extend(
            item.strip()
            for item in re.split(r"[、,，]", issue.split("：", 1)[1])
            if item.strip()
        )
    return "、".join(_dedupe_text_items(targets)[:8])


def _summarize_count_targets(issues: list[str]) -> str:
    matched = [issue for issue in issues if ("期望" in issue) or ("数量" in issue)]
    return "；".join(_dedupe_text_items(matched)[:3])


def _build_repair_guidance(
    *,
    stage_id: str,
    error_code: str,
    error_category: str,
    error_family: str,
    issues: list[str],
) -> list[str]:
    if error_code in {"missing_required_fields", "missing_required_array"}:
        missing_summary = _summarize_missing_targets(issues)
        lines = [
            "补齐缺失字段或数组，保留原有已正确的字段和值，不要省略其他必需字段。",
        ]
        if missing_summary:
            lines.append(f"优先补齐这些缺口：{missing_summary}。")
        return lines
    if error_code == "count_mismatch":
        count_summary = _summarize_count_targets(issues)
        lines = [
            "让数组条目数量与模块数、slot 计划或 contract 要求严格对齐，不多不少。",
        ]
        if count_summary:
            lines.append(f"本次需要对齐的数量约束：{count_summary}。")
        return lines
    if error_code == "invalid_reference":
        reference_summary = _summarize_reference_targets(issues)
        lines = [
            "所有 section_id、slot_id 和 required_image_slots 引用都必须来自当前 JSON 中已声明的 id。",
            "不要引用不存在的 id，也不要把一个 section 的槽位绑定到另一个 section。",
        ]
        if reference_summary:
            lines.append(f"优先修正这些引用：{reference_summary}。")
        return lines
    if error_code in {"invalid_payload_type", "invalid_field_type"}:
        return [
            "严格输出正确 JSON 类型：对象必须是对象，数组必须是数组，字符串字段不要返回对象、数组或 null。",
            f"{stage_id} 阶段中的列表项也必须保持预期结构，不要混入非对象条目。",
        ]
    if error_code == "duplicate_identifier":
        return [
            "确保所有需要唯一的 id 或 name 保持唯一且稳定，不要生成重复标识。",
        ]
    return [
        "按校验问题逐项修复结构，并重新输出完整 JSON。",
        f"本次问题属于 {error_category}/{error_family} 类 contract 错误，请优先修复结构一致性。",
    ]


def _build_retry_prompt(
    *,
    stage_id: str,
    base_prompt: str,
    error_code: str,
    error_category: str,
    error_family: str,
    issues: list[str],
    last_payload: dict[str, Any],
) -> str:
    issue_lines = "\n".join(f"- {item}" for item in issues[:8])
    guidance_lines = "\n".join(
        f"- {item}"
        for item in _build_repair_guidance(
            stage_id=stage_id,
            error_code=error_code,
            error_category=error_category,
            error_family=error_family,
            issues=issues,
        )
    )
    payload_text = json.dumps(last_payload, ensure_ascii=False, indent=2)
    if len(payload_text) > 4000:
        payload_text = payload_text[:4000] + "\n...（截断）"
    return (
        f"{base_prompt}\n\n"
        "上一次输出未通过结构校验。请根据下面的定向修复要求，重新输出完整 JSON，"
        "不要附加解释或 Markdown：\n"
        f"错误类型：{error_code}\n"
        f"错误类别：{error_category}\n"
        f"错误族：{error_family}\n"
        "定向修复要求：\n"
        f"{guidance_lines}\n"
        "校验问题：\n"
        f"{issue_lines}\n\n"
        "上一次输出如下：\n"
        f"{payload_text}"
    )


def _stage_contract_failure_code(stage_id: str) -> str:
    return f"{stage_id}_schema_contract_failed"


def _stage_contract_reason_code(stage_id: str) -> str:
    return f"{stage_id}_contract_failed"


def _stage_error_payload(
    stage_id: str,
    error_code: str,
    reason: str,
    *,
    reason_codes: list[str] | None = None,
    issues: list[str] | None = None,
    source: str = "stage",
    retry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "stage_id": stage_id,
        "error_code": error_code,
        "reason_codes": list(reason_codes or []),
        "reason": reason,
        "issues": list(issues or []),
        "source": source,
        "retry": dict(retry or {}),
    }


def _invoke_stage_json_with_retry(
    *,
    ctx: PipelineContext,
    stage_id: str,
    invoke_model: Callable[[str], dict[str, Any]],
    base_prompt: str,
) -> dict[str, Any]:
    if not hasattr(ctx, "stage_contracts") or not isinstance(
        getattr(ctx, "stage_contracts", None), dict
    ):
        setattr(ctx, "stage_contracts", {})
    policy = _resolve_retry_policy(stage_id)
    max_attempts = max(1, int(policy.max_attempts or 1)) if policy.enabled else 1
    prompt = base_prompt
    last_payload: dict[str, Any] = {}
    last_issues: list[str] = []
    last_error_code = ""
    last_error_category = ""
    last_error_family = ""
    stop_reason = "not_started"
    history: list[dict[str, Any]] = []

    for attempt in range(1, max_attempts + 1):
        ctx.check_cancelled(f"{stage_id}:attempt_{attempt}")
        data = invoke_model(prompt)
        last_payload = data if isinstance(data, dict) else {"raw_payload": data}
        try:
            validated = validate_stage_contract_payload(stage_id, data)
            history.append(
                {
                    "attempt": attempt,
                    "status": "passed",
                    "error_code": "",
                    "error_category": "",
                    "error_family": "",
                    "issues": [],
                    "retryable": False,
                    "retry_scheduled": False,
                }
            )
            validated["_contract_validation"] = _build_contract_retry_metadata(
                stage_id=stage_id,
                policy=policy,
                history=history,
                final_status="passed",
                final_error_code="",
                final_error_category="",
                final_error_family="",
                issues=[],
                stop_reason="passed",
            )
            ctx.stage_contracts[stage_id] = dict(validated["_contract_validation"])
            if attempt > 1:
                _workflow_log(
                    ctx.run_id,
                    f"阶段结构重试成功：{stage_id}",
                    validated["_contract_validation"],
                )
            return validated
        except ValueError as exc:
            (
                last_error_code,
                last_error_category,
                last_error_family,
                last_issues,
            ) = _extract_validation_failure(exc)
            retryable = _is_retryable_contract_error(policy, last_error_code)
            retry_scheduled = retryable and attempt < max_attempts
            history.append(
                {
                    "attempt": attempt,
                    "status": "failed",
                    "error_code": last_error_code,
                    "error_category": last_error_category,
                    "error_family": last_error_family,
                    "issues": list(last_issues[:4]),
                    "retryable": retryable,
                    "retry_scheduled": retry_scheduled,
                }
            )
            _workflow_log(
                ctx.run_id,
                f"阶段结构校验失败：{stage_id}（attempt {attempt}/{max_attempts}）",
                {
                    "error_code": last_error_code,
                    "error_category": last_error_category,
                    "error_family": last_error_family,
                    "retryable": retryable,
                    "retry_scheduled": retry_scheduled,
                    "issues": last_issues,
                    "payload_preview": last_payload,
                },
            )
            if retry_scheduled:
                prompt = _build_retry_prompt(
                    stage_id=stage_id,
                    base_prompt=base_prompt,
                    error_code=last_error_code,
                    error_category=last_error_category,
                    error_family=last_error_family,
                    issues=last_issues,
                    last_payload=last_payload,
                )
                continue
            if last_error_code in policy.non_retryable_error_codes:
                stop_reason = "non_retryable_error"
            elif policy.enabled and attempt >= max_attempts:
                stop_reason = "max_attempts_reached"
            elif not policy.enabled:
                stop_reason = "retry_disabled"
            else:
                stop_reason = "policy_filtered_error"
            break

    ctx.stage_contracts[stage_id] = _build_contract_retry_metadata(
        stage_id=stage_id,
        policy=policy,
        history=history,
        final_status="failed",
        final_error_code=last_error_code,
        final_error_category=last_error_category,
        final_error_family=last_error_family,
        issues=last_issues,
        stop_reason=stop_reason,
    )
    retries_used = max(0, len(history) - 1)
    raise StageContractError(
        f"结构校验失败，已重试 {retries_used} 次："
        + "；".join(last_issues[:8] or ["模型输出结构不合法"]),
        stage_id=stage_id,
        error_code=_stage_contract_failure_code(stage_id),
        reason_codes=[_stage_contract_reason_code(stage_id)],
        issues=last_issues[:8],
    )


_SKIP_LABELS = ("商品类型", "商品名称", "品牌", "品牌名称", "使用场景", "页面", "标题字体", "段落字体", "英文字体", "要求")


def _selling_points(ctx: PipelineContext) -> list[str]:
    brief = semantic_brief_text(ctx.input_layers)
    product = ctx.request.product_name.strip()
    points: list[str] = []
    if brief:
        for raw in brief.splitlines():
            line = raw.strip(" -·•\t")
            if not line or line.startswith("[Sheet]"):
                continue
            # 跳过明显的标签行（商品类型/使用场景/字体要求等）
            label = line.split("：")[0].split(":")[0].strip()
            if any(label.startswith(skip) for skip in _SKIP_LABELS):
                continue
            # "核心卖点：a、b、c" → 取冒号后并按顿号/逗号拆分
            if "：" in line or ":" in line:
                value = line.split("：")[-1].split(":")[-1].strip()
            else:
                value = line
            for part in value.replace(",", "、").replace("|", "、").split("、"):
                part = part.strip()
                if 2 <= len(part) <= 18 and part != product:
                    points.append(part)
    # 去重保序
    seen: set[str] = set()
    unique = [p for p in points if not (p in seen or seen.add(p))]
    if unique:
        return unique[:6]
    return ["轻量通勤", "多分区收纳", "防泼水面料", "简洁商务风格"]


def _input_prompt_block(
    ctx: PipelineContext,
    *,
    include_layout_reference: bool = False,
    include_raw_wireframe_dump: bool = False,
) -> str:
    prompt = render_input_prompt(
        ctx.input_layers,
        include_layout_reference=include_layout_reference,
        include_raw_wireframe_dump=include_raw_wireframe_dump,
    )
    return f"{prompt}\n\n" if prompt else ""


def _normalize_text_items(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for item in value:
        if isinstance(item, str):
            text = item.strip()
        elif isinstance(item, dict):
            text = str(
                item.get("title")
                or item.get("name")
                or item.get("point")
                or item.get("label")
                or item.get("description")
                or item
            ).strip()
        else:
            text = str(item).strip()
        if text:
            items.append(text)
    return items


def _clean_constraint_items(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for raw in value:
        text = str(raw).strip()
        if text and text not in items:
            items.append(text)
    return items


def _merge_effective_constraints(
    requirement_constraints: dict[str, Any],
    feedback_constraints: dict[str, Any],
) -> dict[str, Any]:
    merged = {
        "preferred_module_order": _clean_constraint_items(
            requirement_constraints.get("preferred_module_order")
        ),
        "required_modules": _clean_constraint_items(
            requirement_constraints.get("required_modules")
        ),
        "forbidden_modules": _clean_constraint_items(
            requirement_constraints.get("forbidden_modules")
        ),
        "layout_constraints": _clean_constraint_items(
            requirement_constraints.get("layout_constraints")
        ),
        "visual_constraints": _clean_constraint_items(
            requirement_constraints.get("visual_constraints")
        ),
        "copy_constraints": _clean_constraint_items(
            requirement_constraints.get("copy_constraints")
        ),
        "asset_constraints": _clean_constraint_items(
            requirement_constraints.get("asset_constraints")
        ),
        "negative_constraints": _clean_constraint_items(
            requirement_constraints.get("negative_constraints")
        ),
        "reference_alignment": str(requirement_constraints.get("reference_alignment") or "").strip(),
        "feedback_constraints_applied": False,
        "feedback_source_run_ids": [],
    }
    if not requirement_constraints.get("apply_feedback_constraints", True):
        return merged
    for key in (
        "layout_constraints",
        "visual_constraints",
        "copy_constraints",
        "asset_constraints",
        "negative_constraints",
    ):
        for item in _clean_constraint_items(feedback_constraints.get(key)):
            if item not in merged[key]:
                merged[key].append(item)
    for item in _clean_constraint_items(feedback_constraints.get("general_notes")):
        if item not in merged["layout_constraints"]:
            merged["layout_constraints"].append(item)
    merged["feedback_constraints_applied"] = bool(feedback_constraints.get("applied"))
    merged["feedback_source_run_ids"] = _clean_constraint_items(
        feedback_constraints.get("source_run_ids")
    )
    return merged


def _constraint_prompt_payload(ctx: PipelineContext) -> dict[str, Any]:
    return {
        key: value
        for key, value in ctx.effective_constraints.items()
        if value not in (None, "", [], {})
    }


def _constraint_prompt_block(ctx: PipelineContext) -> str:
    payload = _constraint_prompt_payload(ctx)
    if not payload and not ctx.strict_mode:
        return ""
    lines: list[str] = []
    if payload:
        lines.append(f"结构化需求约束：{json.dumps(payload, ensure_ascii=False)}")
    if ctx.strict_mode:
        lines.append(
            "当前为 strict_brand 模式：优先满足命中的品牌规则、详情页规则和结构化需求约束，"
            "不要退回通用模板，不要擅自改写模块顺序。"
        )
    return "\n".join(lines) + "\n"


def _rule_list(rule: dict[str, Any], snake_key: str, camel_key: str) -> list[dict[str, Any]]:
    value = rule.get(snake_key)
    if value is None:
        value = rule.get(camel_key)
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _infer_module_role(text: str, index: int) -> str:
    normalized = text.lower()
    checks = [
        ("hero", ("hero", "首屏", "头图", "主视觉", "kv", "banner")),
        ("technology", ("technology", "工艺", "技术", "结构", "细节", "放大", "局部")),
        ("scenario", ("scenario", "场景", "通勤", "使用", "出行", "office", "scene")),
        ("parameter", ("parameter", "参数", "规格", "对比", "尺寸", "容量", "数据")),
        ("brand_story", ("brand", "品牌", "故事", "about", "理念")),
        ("cta", ("cta", "购买", "行动", "咨询", "下单", "转化")),
        ("feature", ("feature", "卖点", "亮点", "优势", "特点", "功能")),
    ]
    for role, keywords in checks:
        if any(keyword in normalized for keyword in keywords):
            return role
    return "hero" if index == 0 else "feature"


def _infer_layout_type(text: str, role: str) -> str:
    normalized = text.lower()
    if "右文左图" in text or "text right" in normalized:
        return "right_text_left_image"
    if "左文右图" in text or "text left" in normalized:
        return "left_text_right_image"
    if any(keyword in normalized for keyword in ("三列", "卡片", "cards", "grid")):
        return "three_column_cards"
    if any(keyword in normalized for keyword in ("全屏", "全宽", "大场景", "full", "bleed")):
        return "full_bleed_scene"
    if any(keyword in normalized for keyword in ("表格", "参数", "规格", "对比", "table")):
        return "spec_table"
    if any(keyword in normalized for keyword in ("细节", "局部", "放大", "zoom")):
        return "detail_zoom"
    if role == "hero":
        return "centered_hero" if any(keyword in normalized for keyword in ("居中", "center")) else "hero_split"
    if role == "scenario":
        return "full_bleed_scene"
    if role == "parameter":
        return "spec_table"
    if role == "technology":
        return "detail_zoom"
    return "left_text_right_image"


def _role_display_name(role: str) -> str:
    return {
        "hero": "首屏主视觉",
        "feature": "卖点模块",
        "technology": "工艺细节",
        "scenario": "场景展示",
        "parameter": "参数对比",
        "brand_story": "品牌故事",
        "cta": "行动转化",
    }.get(role, "内容模块")


def _normalize_module_token(value: str) -> str:
    text = value.strip()
    lowered = text.lower().replace("-", "_").replace(" ", "_")
    aliases = [
        ("hero", ("hero", "首屏", "头图", "主视觉", "banner", "kv")),
        ("feature", ("feature", "卖点", "亮点", "优势", "功能")),
        ("technology", ("technology", "工艺", "技术", "结构", "细节")),
        ("scenario", ("scenario", "场景", "使用场景", "scene")),
        ("parameter", ("parameter", "参数", "规格", "对比", "数据")),
        ("brand_story", ("brand_story", "brandstory", "品牌故事", "品牌")),
        ("cta", ("cta", "行动", "购买", "转化", "下单")),
    ]
    for role, keywords in aliases:
        if any(keyword in lowered or keyword in text for keyword in keywords):
            return role
    return lowered


def _default_layout_blueprint(count: int) -> list[dict[str, Any]]:
    templates = _FALLBACK_MODULE_TEMPLATES[:count]
    return [
        {
            "name": title,
            "layer_group": group,
            "layout": layout,
            "role": role,
            "image_role": "主视觉图" if role == "hero" else f"{title}用图",
        }
        for group, title, layout, role in templates
    ]


def _fallback_blueprint_item(role: str, index: int) -> dict[str, Any]:
    for _, title, layout, template_role in _FALLBACK_MODULE_TEMPLATES:
        if template_role == role:
            return {
                "name": title,
                "layer_group": f"{index:02d}_{role.title().replace('_', '')}",
                "layout": layout,
                "role": role,
                "image_role": "主视觉图" if role == "hero" else f"{title}参考图",
            }
    return {
        "name": _role_display_name(role),
        "layer_group": f"{index:02d}_{role.title().replace('_', '')}",
        "layout": "left_text_right_image",
        "role": role,
        "image_role": f"{_role_display_name(role)}参考图",
    }


def _renumber_blueprint(blueprint: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(blueprint, start=1):
        role = str(item.get("role") or _infer_module_role(str(item.get("name") or ""), index - 1))
        normalized.append(
            {
                **item,
                "role": role,
                "layer_group": f"{index:02d}_{role.title().replace('_', '')}",
                "name": str(item.get("name") or _role_display_name(role)),
                "image_role": str(
                    item.get("image_role") or ("主视觉图" if role == "hero" else f"{_role_display_name(role)}参考图")
                ),
            }
        )
    return normalized


def _apply_requirement_constraints_to_blueprint(
    blueprint: list[dict[str, Any]],
    count: int,
    constraints: dict[str, Any],
    strict_mode: bool,
) -> list[dict[str, Any]]:
    if not constraints:
        return _renumber_blueprint(blueprint[:count])

    preferred = [_normalize_module_token(item) for item in constraints.get("preferred_module_order") or []]
    required = [_normalize_module_token(item) for item in constraints.get("required_modules") or []]
    forbidden = {
        _normalize_module_token(item) for item in constraints.get("forbidden_modules") or []
    }
    remaining = [dict(item) for item in blueprint]
    selected: list[dict[str, Any]] = []

    def take_item(token: str) -> dict[str, Any] | None:
        for index, item in enumerate(remaining):
            role = _normalize_module_token(str(item.get("role") or item.get("name") or ""))
            name = _normalize_module_token(str(item.get("name") or ""))
            if token in {role, name}:
                return remaining.pop(index)
        if token in {"hero", "feature", "technology", "scenario", "parameter", "brand_story", "cta"}:
            return _fallback_blueprint_item(token, len(selected) + 1)
        return None

    for token in preferred:
        if token in forbidden:
            continue
        item = take_item(token)
        if item:
            selected.append(item)

    for token in required:
        if token in forbidden:
            continue
        if any(_normalize_module_token(str(item.get("role") or item.get("name") or "")) == token for item in selected):
            continue
        item = take_item(token)
        if item:
            selected.append(item)

    for item in list(remaining):
        role = _normalize_module_token(str(item.get("role") or item.get("name") or ""))
        if role in forbidden:
            continue
        selected.append(item)

    if strict_mode and preferred:
        missing_preferred = [
            token
            for token in preferred
            if token not in {
                _normalize_module_token(str(item.get("role") or item.get("name") or ""))
                for item in selected
            }
        ]
        if missing_preferred:
            raise ValueError(
                "strict_brand 模式下，当前规则无法命中需求指定的模块顺序："
                + "、".join(missing_preferred)
            )

    if strict_mode and len(selected) < count:
        raise ValueError(
            f"strict_brand 模式下，当前规则与需求约束仅能生成 {len(selected)} 个模块，"
            f"少于要求的 {count} 个，请调整规则版本或需求约束"
        )

    if not strict_mode and len(selected) < count:
        defaults = _default_layout_blueprint(count)
        for item in defaults:
            role = _normalize_module_token(str(item.get("role") or item.get("name") or ""))
            if role in forbidden:
                continue
            selected.append(item)
            if len(selected) >= count:
                break

    selected = selected[:count]
    if strict_mode and not any(str(item.get("role") or "") == "hero" for item in selected):
        raise ValueError("strict_brand 模式下必须保留首屏 Hero 模块，当前需求约束移除了该模块")
    return _renumber_blueprint(selected)


def _build_layout_blueprint(
    detail_page_rule: dict[str, Any],
    count: int,
    constraints: dict[str, Any] | None = None,
    strict_mode: bool = False,
) -> list[dict[str, Any]]:
    layout_schema = _extract_layout_schema(detail_page_rule)
    if layout_schema:
        sections = layout_schema.get("sections")
        if isinstance(sections, list) and sections:
            blueprint = []
            for index, section in enumerate(sections[:count]):
                if not isinstance(section, dict):
                    continue
                role = _normalize_module_token(str(section.get("component_type") or section.get("id") or section.get("name") or ""))
                blueprint.append(
                    {
                        "name": str(section.get("name") or _role_display_name(role)),
                        "layer_group": f"{index + 1:02d}_{role.title().replace('_', '')}",
                        "layout": "schema_absolute",
                        "role": role if role else ("hero" if index == 0 else "feature"),
                        "image_role": f"{section.get('name') or _role_display_name(role)}用图",
                    }
                )
            if blueprint:
                return _renumber_blueprint(blueprint)

    if not detail_page_rule:
        if strict_mode:
            raise ValueError("strict_brand 模式要求命中详情页 Derived Rule，不能回退到默认模板")
        return _apply_requirement_constraints_to_blueprint(
            _default_layout_blueprint(count), count, constraints or {}, strict_mode
        )

    items = _rule_list(detail_page_rule, "layout_rules", "layoutRules") or _rule_list(
        detail_page_rule, "components", "components"
    )
    blueprint: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        title = str(item.get("title") or "").strip()
        description = str(item.get("description") or "").strip()
        text = " ".join(part for part in [title, description] if part)
        if not text:
            continue
        role = _infer_module_role(text, index)
        layout = _infer_layout_type(text, role)
        layer_group = f"{index + 1:02d}_{role.title().replace('_', '')}"
        blueprint.append(
            {
                "name": title or _role_display_name(role),
                "layer_group": layer_group,
                "layout": layout,
                "role": role,
                "image_role": "主视觉图" if role == "hero" else f"{title or _role_display_name(role)}参考图",
            }
        )

    if not blueprint:
        if strict_mode:
            raise ValueError("strict_brand 模式下，命中的详情页规则未提取出可执行的布局蓝图")
        blueprint = _default_layout_blueprint(count)

    hero_index = next((i for i, item in enumerate(blueprint) if item["role"] == "hero"), None)
    if hero_index is None:
        blueprint.insert(
            0,
            {
                "name": "首屏主视觉",
                "layer_group": "01_Hero",
                "layout": "hero_split",
                "role": "hero",
                "image_role": "主视觉图",
            },
        )
    elif hero_index != 0:
        blueprint.insert(0, blueprint.pop(hero_index))

    if len(blueprint) < count:
        defaults = _default_layout_blueprint(count)
        for item in defaults:
            if len(blueprint) >= count:
                break
            blueprint.append(item)

    return _apply_requirement_constraints_to_blueprint(
        blueprint[:count], count, constraints or {}, strict_mode
    )


def _rule_items(rule: dict[str, Any], snake_key: str, camel_key: str) -> list[dict[str, Any]]:
    value = rule.get(snake_key)
    if value is None:
        value = rule.get(camel_key)
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _special_rule_payload(rule: dict[str, Any], marker: str, payload_key: str) -> Any:
    for collection_key in (("design_rules", "designRules"), ("layout_rules", "layoutRules"), ("components", "components")):
        for item in _rule_items(rule, collection_key[0], collection_key[1]):
            if str(item.get("title") or "") == marker and payload_key in item:
                return item.get(payload_key)
    return None


def _raw_extract_layout_schema(rule: dict[str, Any]) -> dict[str, Any]:
    direct = rule.get("layout_schema") or rule.get("layoutSchema")
    if isinstance(direct, dict):
        return direct
    schema = _special_rule_payload(rule, "__layout_schema__", "schema")
    return schema if isinstance(schema, dict) else {}


def _raw_extract_image_slots(rule: dict[str, Any]) -> list[dict[str, Any]]:
    direct = rule.get("image_slots") or rule.get("imageSlots")
    if isinstance(direct, list):
        return [item for item in direct if isinstance(item, dict)]
    slots = _special_rule_payload(rule, "__image_slots__", "slots")
    return [item for item in slots if isinstance(item, dict)] if isinstance(slots, list) else []


def _extract_layout_schema(rule: dict[str, Any]) -> dict[str, Any]:
    return normalize_layout_schema_payload(
        _raw_extract_layout_schema(rule),
        detached_image_slots=_raw_extract_image_slots(rule),
    )


def _extract_image_slots(rule: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in _extract_layout_schema(rule).get("image_slots", []) if isinstance(item, dict)]


def _slot_role_for_module(role: str) -> str:
    mapping = {
        "hero": "hero",
        "feature": "detail",
        "technology": "detail",
        "scenario": "lifestyle",
        "parameter": "size",
        "brand_story": "brand_story",
        "cta": "detail",
    }
    return mapping.get(role, "detail")


def _required_text_fields_for_role(role: str) -> list[str]:
    if role == "hero":
        return ["headline", "subtitle"]
    if role in {"feature", "technology", "scenario", "brand_story"}:
        return ["headline", "body"]
    if role == "parameter":
        return ["headline", "points"]
    if role == "cta":
        return ["headline"]
    return ["headline"]


def _section_layout_plan(role: str, layout: str, canvas_width: int, height: int) -> tuple[dict[str, int | str], dict[str, int | str]]:
    full_width = max(120, canvas_width - 80)
    if role == "hero" or layout in {"hero_split", "centered_hero"}:
        return (
            {"x": 40, "y": 120, "w": full_width, "h": max(320, height - 240), "fit": "cover", "crop": "center"},
            {"x": 40, "y": 48, "w": full_width, "h": 120, "align": "left"},
        )
    if role == "scenario" or layout == "full_bleed_scene":
        return (
            {"x": 0, "y": 0, "w": canvas_width, "h": height, "fit": "cover", "crop": "center"},
            {"x": 40, "y": 56, "w": min(320, full_width), "h": 120, "align": "left"},
        )
    if role == "parameter" or layout == "spec_table":
        return (
            {"x": canvas_width - 280, "y": 150, "w": 220, "h": max(220, height - 260), "fit": "contain", "crop": "center"},
            {"x": 40, "y": 56, "w": max(220, canvas_width - 360), "h": max(180, height - 120), "align": "left"},
        )
    if layout == "right_text_left_image":
        return (
            {"x": 40, "y": 120, "w": max(220, int(canvas_width * 0.48)), "h": max(240, height - 200), "fit": "cover", "crop": "center"},
            {"x": int(canvas_width * 0.56), "y": 64, "w": max(180, canvas_width - int(canvas_width * 0.56) - 40), "h": max(180, height - 120), "align": "left"},
        )
    return (
        {"x": max(240, int(canvas_width * 0.46)), "y": 120, "w": max(220, int(canvas_width * 0.44)), "h": max(240, height - 200), "fit": "cover", "crop": "center"},
        {"x": 40, "y": 64, "w": max(180, int(canvas_width * 0.42)), "h": max(180, height - 120), "align": "left"},
    )


def _layout_compiler_inputs(ctx: PipelineContext) -> list[dict[str, Any]]:
    info_arch = ctx.design_direction.get("information_architecture")
    blueprint = ctx.layout_blueprint
    inputs: list[dict[str, Any]] = []
    if isinstance(info_arch, list):
        for index, item in enumerate(info_arch, start=1):
            if not isinstance(item, dict):
                continue
            blueprint_item = blueprint[index - 1] if index - 1 < len(blueprint) else {}
            text = " ".join(
                str(item.get(key) or "").strip()
                for key in ("module_name", "layout", "content", "image_requirement")
            )
            role = str(blueprint_item.get("role") or _infer_module_role(text, index - 1))
            inputs.append(
                {
                    "index": index,
                    "name": str(item.get("module_name") or blueprint_item.get("name") or _role_display_name(role)),
                    "role": role,
                    "layout": str(item.get("layout") or blueprint_item.get("layout") or _infer_layout_type(text, role)),
                    "content": str(item.get("content") or ""),
                    "image_requirement": str(item.get("image_requirement") or ""),
                }
            )
    if inputs:
        return inputs[: ctx.request.layout.module_count]

    for index, item in enumerate(blueprint, start=1):
        role = str(item.get("role") or _infer_module_role(str(item.get("name") or ""), index - 1))
        inputs.append(
            {
                "index": index,
                "name": str(item.get("name") or _role_display_name(role)),
                "role": role,
                "layout": str(item.get("layout") or _infer_layout_type(str(item.get("name") or ""), role)),
                "content": "",
                "image_requirement": str(item.get("image_role") or ""),
            }
        )
    return inputs[: ctx.request.layout.module_count]


def _compile_layout_schema(ctx: PipelineContext, base_schema: dict[str, Any]) -> dict[str, Any]:
    compiler_inputs = _layout_compiler_inputs(ctx)
    if not compiler_inputs:
        return normalize_layout_schema_payload(base_schema)

    canvas_width = ctx.request.layout.canvas_width
    y = 0
    sections: list[dict[str, Any]] = []
    slots: list[dict[str, Any]] = []
    text_layers: list[dict[str, Any]] = []
    component_templates: list[dict[str, Any]] = []

    for item in compiler_inputs:
        index = int(item.get("index") or len(sections) + 1)
        role = _normalize_module_token(str(item.get("role") or "feature"))
        name = str(item.get("name") or _role_display_name(role))
        layout = str(item.get("layout") or _infer_layout_type(name, role))
        height = ctx.request.layout.hero_height if role == "hero" or index == 1 else ctx.request.layout.module_height
        section_id = f"compiled_{index:02d}_{role}"
        slot_id = f"{section_id}_image"
        image_role = _slot_role_for_module(role)
        image_plan, text_plan = _section_layout_plan(role, layout, canvas_width, height)
        semantic_tags = [
            tag
            for tag in {
                role,
                image_role,
                str(item.get("image_requirement") or "").strip(),
                str(item.get("content") or "").strip(),
                name,
            }
            if tag
        ]

        sections.append(
            {
                "id": section_id,
                "name": name,
                "role": role,
                "component_type": role,
                "layout": layout,
                "order": index,
                "x": 0,
                "y": y,
                "w": canvas_width,
                "h": height,
                "background": {"type": "solid", "color": "#ffffff" if index % 2 else "#f7f7f4"},
                "required_text_fields": _required_text_fields_for_role(role),
                "optional_text_fields": ["points", "subtitle"] if role != "cta" else ["subtitle"],
                "required_image_slots": [] if role == "cta" else [slot_id],
                "optional_image_slots": [slot_id] if role == "cta" else [],
            }
        )
        slots.append(
            {
                "id": slot_id,
                "section_id": section_id,
                "role": image_role,
                "asset_type": image_role,
                "x": image_plan["x"],
                "y": image_plan["y"],
                "w": image_plan["w"],
                "h": image_plan["h"],
                "fit": image_plan["fit"],
                "crop": image_plan["crop"],
                "priority": "high" if role in {"hero", "scenario"} else ("low" if role == "cta" else "medium"),
                "required": role != "cta",
                "semantic_tags": semantic_tags[:6],
            }
        )
        text_layers.append(
            {
                "id": f"{section_id}_text",
                "section_id": section_id,
                "role": "headline",
                "text": name,
                "x": text_plan["x"],
                "y": text_plan["y"],
                "w": text_plan["w"],
                "h": text_plan["h"],
                "font": ctx.request.typography.title_font,
                "font_size": ctx.request.typography.title_size,
                "align": text_plan["align"],
            }
        )
        component_templates.append(
            {
                "id": section_id,
                "name": name,
                "component_type": role,
                "layout": layout,
                "image_slot_count": 0 if role == "cta" else 1,
                "text_layer_count": 1,
                "source": "layout_compiler",
            }
        )
        y += height

    compiled = {
        **base_schema,
        "schema_version": str(base_schema.get("schema_version") or "brandos_layout_schema.v1"),
        "page_type": str(base_schema.get("page_type") or "detail_page"),
        "canvas": base_schema.get("canvas") if isinstance(base_schema.get("canvas"), dict) else {"width": canvas_width, "height_mode": "auto"},
        "sections": sections,
        "image_slots": slots,
        "text_layers": text_layers,
        "component_templates": component_templates,
        "global_constraints": _constraint_prompt_payload(ctx),
        "source_rule_id": ctx.detail_page_rule.get("id"),
        "source_version": ctx.detail_page_rule.get("version"),
        "compiled_from": {
            "detail_rule_id": ctx.detail_page_rule.get("id"),
            "page_planner": bool(ctx.design_direction),
            "layout_blueprint_count": len(ctx.layout_blueprint),
        },
    }
    return normalize_layout_schema_payload(compiled)


def _resolve_layout_schema(ctx: PipelineContext) -> dict[str, Any]:
    base_schema = _extract_layout_schema(ctx.detail_page_rule)
    if base_schema.get("sections"):
        return base_schema
    return _compile_layout_schema(ctx, base_schema)


def _merge_modules_with_blueprint(
    modules: list[dict[str, Any]], blueprint: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    if not blueprint:
        return modules
    merged: list[dict[str, Any]] = []
    total = max(len(modules), len(blueprint))
    for index in range(total):
        raw = modules[index] if index < len(modules) else {}
        hint = blueprint[index] if index < len(blueprint) else {}
        merged.append(
            {
                **hint,
                **raw,
                "name": hint.get("name") or raw.get("name"),
                "layer_group": hint.get("layer_group") or raw.get("layer_group"),
                "layout": hint.get("layout") or raw.get("layout"),
                "role": hint.get("role") or raw.get("role"),
                "image_role": hint.get("image_role") or raw.get("image_role"),
            }
        )
    return merged


# ----------------------------- 各阶段实现 -----------------------------


def _run_stage(
    stage_id: str,
    title: str,
    icon: str,
    ctx: PipelineContext,
    model_fn: Callable[[], dict[str, Any]],
    fallback_fn: Callable[[], dict[str, Any]],
    summarize: Callable[[dict[str, Any], bool], str],
) -> StageResult:
    ctx.check_cancelled(f"{stage_id}:before")
    started = time.perf_counter()
    started_at = datetime.utcnow()
    used_model = False
    status = "completed"
    stage_error: dict[str, Any] | None = None
    set_run_state(ctx.run_id, "running", stage_id, title, icon)
    _workflow_log(ctx.run_id, f"开始阶段：{title} ({stage_id})")
    try:
        data = model_fn()
        used_model = True
        _workflow_log(ctx.run_id, f"模型阶段完成：{title} ({stage_id})", data)
    except StageContractError as exc:
        used_model = True
        ctx.warnings.append(f"[{stage_id}] 结构校验失败，阶段内重试后仍降级：{exc}")
        _workflow_log(ctx.run_id, f"阶段结构降级：{title} ({stage_id})，原因：{exc}")
        data = fallback_fn()
        contract_validation = dict(ctx.stage_contracts.get(stage_id) or {})
        stage_error = _stage_error_payload(
            stage_id,
            str(contract_validation.get("error_code") or exc.error_code),
            str(exc),
            reason_codes=exc.reason_codes,
            issues=exc.issues,
            source="contract_validation",
            retry=_retry_summary_payload(stage_id, contract_validation),
        )
        status = "fallback"
    except LLMUnavailable as exc:
        ctx.warnings.append(f"[{stage_id}] {exc}")
        _workflow_log(ctx.run_id, f"阶段降级：{title} ({stage_id})，原因：{exc}")
        data = fallback_fn()
        stage_error = _stage_error_payload(
            stage_id,
            f"{stage_id}_llm_unavailable",
            str(exc),
            reason_codes=[f"{stage_id}_fallback_used"],
            source="llm",
        )
        status = "fallback"
    except Exception as exc:  # pragma: no cover - 阶段级兜底
        ctx.warnings.append(f"[{stage_id}] 未知异常已降级：{exc}")
        _workflow_log(ctx.run_id, f"阶段异常降级：{title} ({stage_id})，原因：{exc}")
        data = fallback_fn()
        stage_error = _stage_error_payload(
            stage_id,
            f"{stage_id}_unexpected_fallback",
            str(exc),
            reason_codes=[f"{stage_id}_fallback_used"],
            source="unexpected",
        )
        status = "fallback"

    if isinstance(data, dict) and stage_error and "_stage_error" not in data:
        data["_stage_error"] = stage_error
    summary = summarize(data, used_model)
    ctx.report_parts.append(f"## {title}\n{summary}")
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    completed_at = datetime.utcnow()
    contract_validation = dict(ctx.stage_contracts.get(stage_id) or {})
    retry_summary = _retry_summary_payload(stage_id, contract_validation)
    error_code = str((stage_error or {}).get("error_code") or "")
    _workflow_log(
        ctx.run_id,
        f"结束阶段：{title} ({stage_id})，status={status}，used_model={used_model}，elapsed_ms={elapsed_ms}，summary={summary}",
    )
    ctx.stage_execution[stage_id] = {
        "status": status,
        "used_model": used_model,
        "summary": summary,
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "duration_ms": elapsed_ms,
        "error_code": error_code,
        "retry": retry_summary,
        "error": dict(stage_error or {}),
        "contract_validation": contract_validation,
    }
    result = StageResult(
        id=stage_id,
        title=title,
        icon=icon,
        status=status,  # type: ignore[arg-type]
        summary=summary,
        detail=json.dumps(data, ensure_ascii=False, indent=2),
        data=data,
        used_model=used_model,
        elapsed_ms=elapsed_ms,
        started_at=started_at.isoformat(),
        completed_at=completed_at.isoformat(),
        duration_ms=elapsed_ms,
        error_code=error_code,
        retry=retry_summary,
    )
    append_stage_result(ctx.run_id, result)
    ctx.check_cancelled(f"{stage_id}:after")
    return result


def stage_vision(ctx: PipelineContext) -> StageResult:
    req = ctx.request

    settings = req.model_settings

    def model_fn() -> dict[str, Any]:
        image_names = ctx.images
        prompt = (
            f"商品名称：{req.product_name}\n"
            f"品牌：{req.brand_name}\n"
            f"商品图文件名：{image_names}\n"
            f"{_input_prompt_block(ctx)}"
            f"{_constraint_prompt_block(ctx)}"
            "请输出 Product Brief 基础信息，字段："
            "product_type, target_audience, main_color, material, key_features(数组), "
            "scenarios(数组), usable_images(对象，含 hero_image、detail_images 数组、scene_images 数组)。"
        )
        image_paths = ctx.image_paths[: settings.max_vision_images]
        if image_paths and settings.enable_vision:
            try:
                data = ctx.llm.invoke_vision_json(
                    req.prompts.vision_agent_prompt, prompt, image_paths
                )
                data["_vision"] = {
                    "mode": "multimodal",
                    "model": settings.vision_model,
                    "images": [Path(p).name for p in image_paths],
                }
                data["key_features"] = _normalize_text_items(data.get("key_features")) or _selling_points(ctx)
                ctx.product_info = data
                return data
            except LLMUnavailable as exc:
                ctx.warnings.append(f"[product_understanding] 多模态识别不可用，转文本推断：{exc}")

        data = ctx.llm.invoke_json(req.prompts.vision_agent_prompt, prompt)
        data["_vision"] = {"mode": "text", "model": settings.model}
        data["key_features"] = _normalize_text_items(data.get("key_features")) or _selling_points(ctx)
        ctx.product_info = data
        return data

    def fallback_fn() -> dict[str, Any]:
        images = ctx.images
        data = {
            "product_type": req.product_name,
            "target_audience": "注重品质、效率与品牌一致性的电商消费者（待人工确认）",
            "main_color": "以参考图为准（浅蓝 / 低饱和）",
            "material": "尼龙 / 防泼水面料（待人工确认）",
            "key_features": _selling_points(ctx),
            "scenarios": ["办公", "通勤", "短途旅行"],
            "usable_images": {
                "hero_image": images[0] if images else "（待上传主视觉图）",
                "detail_images": images[1:4],
                "scene_images": images[4:7],
            },
        }
        ctx.product_info = data
        return data

    def summarize(data: dict[str, Any], used: bool) -> str:
        feats = "、".join(_normalize_text_items(data.get("key_features"))[:4])
        mode = (data.get("_vision") or {}).get("mode")
        if not used:
            prefix = "按文件名/brief 规则推断"
        elif mode == "multimodal":
            count = len((data.get("_vision") or {}).get("images", []))
            prefix = f"多模态识别（读取 {count} 张图片）"
        else:
            prefix = "文本模型推断"
        return f"{prefix}：{data.get('product_type', req.product_name)}，主色 {data.get('main_color', '-')}，关键特征：{feats}。"

    return _run_stage(
        "product_understanding",
        "商品理解 Agent",
        "eye",
        ctx,
        model_fn,
        fallback_fn,
        summarize,
    )


def stage_structured(ctx: PipelineContext) -> StageResult:
    req = ctx.request

    def model_fn() -> dict[str, Any]:
        base_prompt = (
            f"商品视觉信息：{json.dumps(ctx.product_info, ensure_ascii=False)}\n"
            f"{_input_prompt_block(ctx)}"
            f"{_constraint_prompt_block(ctx)}"
            "请合并视觉信息与 brief，输出 Product Brief："
            "brand, product, audience, selling_points(数组), specifications(对象), scenarios(数组), design_focus。"
        )
        data = _invoke_stage_json_with_retry(
            ctx=ctx,
            stage_id="product_brief",
            base_prompt=base_prompt,
            invoke_model=lambda attempt_prompt: ctx.llm.invoke_json(
                req.prompts.structured_agent_prompt, attempt_prompt
            ),
        )
        data["selling_points"] = _normalize_text_items(data.get("selling_points")) or _selling_points(ctx)
        ctx.structured_info = data
        return data

    def fallback_fn() -> dict[str, Any]:
        data = {
            "brand": req.brand_name,
            "product": req.product_name,
            "audience": ctx.product_info.get("target_audience", "品牌目标消费者"),
            "selling_points": _selling_points(ctx),
            "specifications": {
                "size": "根据 brief 提取",
                "weight": "根据 brief 提取",
                "material": ctx.product_info.get("material", "根据 brief 提取"),
            },
            "scenarios": ctx.product_info.get("scenarios", ["办公", "通勤", "短途旅行"]),
            "design_focus": "将商品卖点转译为标准详情页模块，保持品牌一致性与可编辑性。",
        }
        ctx.structured_info = data
        return data

    def summarize(data: dict[str, Any], used: bool) -> str:
        points = "、".join(_normalize_text_items(data.get("selling_points"))[:4])
        return f"统一商品结构已生成，核心卖点：{points}。"

    return _run_stage(
        "product_brief",
        "Product Brief",
        "layers",
        ctx,
        model_fn,
        fallback_fn,
        summarize,
    )


def stage_brand_rag(ctx: PipelineContext) -> StageResult:
    req = ctx.request
    settings = req.model_settings
    selected_core_rule = ctx.core_rule or {}
    selected_detail_rule = ctx.detail_page_rule or {}

    def model_fn() -> dict[str, Any]:
        base_prompt = (
            f"品牌：{req.brand_name}\n"
            f"品牌规范：\n{req.brand_guidelines}\n"
            f"参考图说明：\n{req.reference_notes}\n"
            f"参考案例图片：{ctx.reference_images}\n"
            f"可用字体文件：{ctx.fonts}\n"
            f"选中的 Core Rule：{json.dumps(selected_core_rule, ensure_ascii=False)}\n"
            f"选中的详情页 Derived Rule：{json.dumps(selected_detail_rule, ensure_ascii=False)}\n"
            f"强布局蓝图：{json.dumps(ctx.layout_blueprint, ensure_ascii=False)}\n"
            f"界面字体配置：{req.typography.model_dump_json()}\n\n"
            f"{_constraint_prompt_block(ctx)}"
            "请生成 Brand Design System 摘要，输出："
            "version, rule_status, core_rule(对象), derived_rule(对象), asset_memory(对象), "
            "rule_weights(对象), drift_risks(数组), brand_style, primary_color, secondary_colors(数组), "
            "fonts(对象，含 title、body、english), layout_rules(数组), component_patterns(数组), prompt_templates(数组), module_order(数组)。"
        )
        reference_image_paths = ctx.reference_image_paths[: settings.max_vision_images]

        def invoke_model(attempt_prompt: str) -> dict[str, Any]:
            if reference_image_paths and settings.enable_vision:
                payload = ctx.llm.invoke_vision_json(
                    req.prompts.brand_rag_agent_prompt,
                    attempt_prompt,
                    reference_image_paths,
                )
                payload["_reference_vision"] = {
                    "mode": "multimodal",
                    "model": settings.vision_model,
                    "images": [Path(path).name for path in reference_image_paths],
                }
                return payload
            payload = ctx.llm.invoke_json(req.prompts.brand_rag_agent_prompt, attempt_prompt)
            payload["_reference_vision"] = {
                "mode": "text",
                "images": ctx.reference_images,
            }
            return payload

        data = _invoke_stage_json_with_retry(
            ctx=ctx,
            stage_id="brand_knowledge",
            base_prompt=base_prompt,
            invoke_model=invoke_model,
        )
        if ctx.layout_blueprint:
            data["module_order"] = [item["name"] for item in ctx.layout_blueprint]
            data["selected_core_rule"] = selected_core_rule
            data["selected_detail_page_rule"] = selected_detail_rule
        ctx.brand_profile = data
        return data

    def fallback_fn() -> dict[str, Any]:
        data = {
            "version": "Brand Rule V1.1",
            "rule_status": "draft_pending_approval",
            "core_rule": {
                "brand_name": req.brand_name,
                "positioning": "企业级品牌设计操作系统中的当前品牌空间",
                "tone": req.layout.visual_style,
                "primary_color": req.layout.accent_color,
                "typography_locked": req.typography.lock_brand_typography,
            },
            "derived_rule": {
                "page_type": "商品详情页",
                "module_template": [item["name"] for item in ctx.layout_blueprint],
                "editable_scope": "允许页面层模块、文案和图片策略随任务调整，但受 Core Rule 约束。",
                "requirement_constraints": ctx.effective_constraints,
            },
            "asset_memory": {
                "role": "仅作为参考案例，不直接修改核心品牌规则",
                "reference_notes": req.reference_notes,
                "reference_images": ctx.reference_images,
                "asset_names": [asset.name for asset in ctx.assets],
            },
            "selected_core_rule": selected_core_rule,
            "selected_detail_page_rule": selected_detail_rule,
            "rule_weights": {"core_rule": 0.55, "derived_rule": 0.35, "asset_memory": 0.1},
            "drift_risks": ["新上传资产默认进入训练池，不自动覆盖当前生效规则"],
            "brand_style": req.layout.visual_style,
            "primary_color": req.layout.accent_color,
            "secondary_colors": [req.layout.background_color, "#ffffff"],
            "fonts": {
                "title": req.typography.title_font,
                "body": req.typography.body_font,
                "english": req.typography.english_font,
            },
            "layout_rules": [
                f"页面宽度 {req.layout.canvas_width}px，高度不限",
                f"标题 {req.typography.title_font} {req.typography.title_size}号",
                f"正文 {req.typography.body_font} {req.typography.body_size}号",
                f"英文 {req.typography.english_font}",
                "详情页模块顺序与图文分区优先遵守选中的 Derived Rule",
                "先生成结构化页面 Layout JSON，再映射到 Figma / PSD 输出",
            ],
            "component_patterns": [item["layout"] for item in ctx.layout_blueprint],
            "prompt_templates": ["详情页页面规划", "场景图生成", "局部模块重生成", "设计评分"],
            "module_order": [item["name"] for item in ctx.layout_blueprint],
        }
        ctx.brand_profile = data
        return data

    def summarize(data: dict[str, Any], used: bool) -> str:
        fonts = data.get("fonts", {})
        return (
            f"规则版本：{data.get('version', '-')}；"
            f"Core/Derived/Asset 权重 {data.get('rule_weights', {})}；"
            f"主色 {data.get('primary_color', '-')}；字体 标题/{fonts.get('title', '-')} 正文/{fonts.get('body', '-')}。"
        )

    return _run_stage(
        "brand_knowledge",
        "品牌知识库 / 规则版本",
        "library",
        ctx,
        model_fn,
        fallback_fn,
        summarize,
    )


def stage_design(ctx: PipelineContext) -> StageResult:
    req = ctx.request
    detail_rule = ctx.detail_page_rule or {}

    def model_fn() -> dict[str, Any]:
        base_prompt = (
            f"商品结构：{json.dumps(ctx.structured_info, ensure_ascii=False)}\n"
            f"品牌风格：{json.dumps(ctx.brand_profile, ensure_ascii=False)}\n"
            f"选中的 Core Rule：{json.dumps(ctx.core_rule, ensure_ascii=False)}\n"
            f"选中的详情页 Derived Rule：{json.dumps(detail_rule, ensure_ascii=False)}\n"
            f"强布局蓝图：{json.dumps(ctx.layout_blueprint, ensure_ascii=False)}\n"
            f"工作流模式：{req.workflow_mode.value}\n"
            f"参考图说明：{req.reference_notes}\n\n"
            f"参考案例图片：{ctx.reference_images}\n\n"
            f"{_input_prompt_block(ctx, include_layout_reference=True)}"
            f"{_constraint_prompt_block(ctx)}"
            "请输出页面规划策略，字段："
            "direction(整体视觉方向，字符串), page_template(数组), information_architecture(数组), "
            "tone(色调与节奏), image_strategy(图片资产需求), brand_constraints(数组), risks(数组)。"
            "如果已提供详情页 Derived Rule，page_template 与 information_architecture 必须优先服从该规则，不要退回默认模块顺序。"
        )
        data = _invoke_stage_json_with_retry(
            ctx=ctx,
            stage_id="page_planner",
            base_prompt=base_prompt,
            invoke_model=lambda attempt_prompt: ctx.llm.invoke_json(
                req.prompts.design_agent_prompt, attempt_prompt
            ),
        )
        if ctx.layout_blueprint:
            data["page_template"] = [item["name"] for item in ctx.layout_blueprint]
        ctx.design_direction = data
        return data

    def fallback_fn() -> dict[str, Any]:
        page_template = [item["name"] for item in ctx.layout_blueprint]
        data = {
            "direction": "优先贴合选中的详情页规则与参考图：保留模块节奏、图文占比和主视觉位置，再补足商品卖点表达。",
            "page_template": page_template,
            "information_architecture": [
                f"{name}：优先沿用参考页同类型信息区块与图文分区"
                for name in page_template[: max(4, len(page_template))]
            ],
            "tone": "低饱和、冷静、商务；节奏优先复用参考页的大图、细节、参数与收尾顺序。",
            "image_strategy": "Image Studio 需补齐主视觉、卖点图、场景图与参数说明图；素材不足时以占位图进入设计师审核。",
            "brand_constraints": [
                "严格遵守品牌字体与字号" if req.typography.lock_brand_typography else "字体可在品牌库内微调",
                f"主色锁定 {req.layout.accent_color}",
                "页面结构必须优先遵守选中的详情页布局规则与模块顺序",
                *[f"布局约束：{item}" for item in ctx.effective_constraints.get("layout_constraints", [])[:4]],
                *[f"视觉约束：{item}" for item in ctx.effective_constraints.get("visual_constraints", [])[:4]],
            ],
            "risks": ["实拍素材需人工抠图调色", "文案避免绝对化与平台风险词"],
        }
        ctx.design_direction = data
        return data

    def summarize(data: dict[str, Any], used: bool) -> str:
        return str(data.get("direction", "已生成设计方向。"))

    return _run_stage(
        "page_planner", "页面规划 Agent", "palette", ctx, model_fn, fallback_fn, summarize
    )


_FALLBACK_MODULE_TEMPLATES = [
    ("01_Hero", "Hero", "hero_split", "hero"),
    ("02_Feature", "Feature", "three_column_cards", "feature"),
    ("03_Technology", "Technology", "detail_zoom", "technology"),
    ("04_Scenario", "Scenario", "full_bleed_scene", "scenario"),
    ("05_Parameter", "Parameter", "spec_table", "parameter"),
    ("06_BrandStory", "Brand Story", "minimal_logo", "brand_story"),
    ("07_CTA", "CTA", "cta_panel", "cta"),
]


def stage_layout(ctx: PipelineContext) -> StageResult:
    req = ctx.request
    count = req.layout.module_count
    layout_schema = _resolve_layout_schema(ctx)
    layout_guard = _build_layout_guard_report(layout_schema, ctx)

    def model_fn() -> dict[str, Any]:
        schema_modules = _modules_from_layout_schema(layout_schema, ctx)
        if layout_guard["can_execute"] and schema_modules:
            ctx.modules = schema_modules
            ctx.layout_validation = _validate_layout_schema(layout_schema, ctx)
            ctx.asset_match_report = _build_asset_match_report(ctx.modules, ctx)
            ctx.asset_guard = _build_asset_guard_report(ctx)
            return {
                "layout_schema": layout_schema,
                "layout_guard": layout_guard,
                "layout_validation": ctx.layout_validation,
                "asset_match_report": ctx.asset_match_report,
                "asset_guard": ctx.asset_guard,
                "modules": ctx.modules,
                "mode": "executable_schema",
            }
        prompt_payload = _layout_prompt_payload(ctx, layout_schema, layout_guard)
        base_prompt = (
            "请根据以下结构化上下文补全 layout modules。要求：\n"
            "1. 优先遵守 layout_schema 与 layout_guard，不要自由改写模块意图。\n"
            "2. 如果 layout_guard 未通过，只能输出与现有强布局蓝图一致的最小可行模块结果。\n"
            "3. 输出 modules 数组，每个元素包含："
            "name, layer_group, layout, height, role, image_role, elements。\n"
            f"4. 模块数量必须是 {count} 个。\n"
            "5. 不要重复返回完整规则原文，只输出布局结果。\n\n"
            f"{json.dumps(prompt_payload, ensure_ascii=False, indent=2)}"
        )
        data = _invoke_stage_json_with_retry(
            ctx=ctx,
            stage_id="layout_engine",
            base_prompt=base_prompt,
            invoke_model=lambda attempt_prompt: ctx.llm.invoke_json(
                req.prompts.layout_agent_prompt, attempt_prompt
            ),
        )
        modules = data.get("modules") or []
        ctx.modules = _normalize_modules(_merge_modules_with_blueprint(modules, ctx.layout_blueprint), ctx)
        ctx.layout_validation = {
            "status": "failed",
            "issues": list(layout_guard["issues"]) or ["未命中可执行详情页 Derived Rule / layout_schema，Layout Engine 未执行结构化 schema"],
            "warnings": list(layout_guard["warnings"]) + ["当前布局来自模型规划结果，仍需人工确认是否符合品牌模板"],
            "section_count": len(layout_schema.get("sections", [])) if isinstance(layout_schema, dict) else 0,
            "image_slot_count": len(layout_schema.get("image_slots", [])) if isinstance(layout_schema, dict) else 0,
            "guard_status": layout_guard["status"],
            "guard_can_execute": layout_guard["can_execute"],
            "high_priority_slot_count": layout_guard["high_priority_slot_count"],
            "required_asset_roles": layout_guard["required_asset_roles"],
            "available_asset_roles": layout_guard["available_asset_roles"],
            "missing_asset_roles": layout_guard["missing_asset_roles"],
        }
        ctx.asset_match_report = {
            "status": "skipped",
            "match_count": 0,
            "slot_count": len(layout_schema.get("image_slots", [])) if isinstance(layout_schema, dict) else 0,
            "unmatched_slots": [],
            "matches": [],
            "reason": "Layout Guard 未通过，当前布局未消费可执行 image_slots",
        }
        ctx.asset_guard = _build_asset_guard_report(ctx)
        return {
            "modules": ctx.modules,
            "layout_guard": layout_guard,
            "layout_validation": ctx.layout_validation,
            "asset_match_report": ctx.asset_match_report,
            "asset_guard": ctx.asset_guard,
            "mode": "llm_layout_plan",
        }

    def fallback_fn() -> dict[str, Any]:
        schema_modules = _modules_from_layout_schema(layout_schema, ctx)
        if layout_guard["can_execute"] and schema_modules:
            ctx.modules = schema_modules
            ctx.layout_validation = _validate_layout_schema(layout_schema, ctx)
            ctx.asset_match_report = _build_asset_match_report(ctx.modules, ctx)
            ctx.asset_guard = _build_asset_guard_report(ctx)
            return {
                "layout_schema": layout_schema,
                "layout_guard": layout_guard,
                "layout_validation": ctx.layout_validation,
                "asset_match_report": ctx.asset_match_report,
                "asset_guard": ctx.asset_guard,
                "modules": ctx.modules,
                "mode": "executable_schema_fallback",
            }
        modules = [
            {
                **item,
                "elements": ["BG_背景", "IMG_图片", "TXT_标题", "TXT_说明"],
            }
            for item in ctx.layout_blueprint[:count]
        ]
        ctx.modules = _normalize_modules(modules, ctx)
        ctx.layout_validation = {
            "status": "failed",
            "issues": list(layout_guard["issues"]) or ["未命中可执行详情页 Derived Rule / layout_schema，Layout Engine 已回退通用模块模板"],
            "warnings": list(layout_guard["warnings"]) or ["当前结果只能作为低保真草稿，不能视为已执行品牌详情页布局规范"],
            "section_count": len(layout_schema.get("sections", [])) if isinstance(layout_schema, dict) else 0,
            "image_slot_count": len(layout_schema.get("image_slots", [])) if isinstance(layout_schema, dict) else 0,
            "guard_status": layout_guard["status"],
            "guard_can_execute": layout_guard["can_execute"],
            "high_priority_slot_count": layout_guard["high_priority_slot_count"],
            "required_asset_roles": layout_guard["required_asset_roles"],
            "available_asset_roles": sorted({_asset_role(name) for name in [*ctx.images, *ctx.reference_images, *ctx.generated_image_names]}),
            "missing_asset_roles": layout_guard["missing_asset_roles"],
        }
        ctx.asset_match_report = {
            "status": "skipped",
            "match_count": 0,
            "slot_count": len(layout_schema.get("image_slots", [])) if isinstance(layout_schema, dict) else 0,
            "unmatched_slots": [],
            "matches": [],
            "reason": "Layout Guard 未通过或无可执行 image_slots，无法执行语义图片槽匹配",
        }
        ctx.asset_guard = _build_asset_guard_report(ctx)
        return {
            "modules": ctx.modules,
            "layout_guard": layout_guard,
            "layout_validation": ctx.layout_validation,
            "asset_match_report": ctx.asset_match_report,
            "asset_guard": ctx.asset_guard,
            "mode": "fallback_blueprint",
        }

    def summarize(data: dict[str, Any], used: bool) -> str:
        names = "、".join(m["name"] for m in data.get("modules", []))
        return f"已规划 {len(data.get('modules', []))} 个模块：{names}。"

    return _run_stage(
        "layout_engine", "Layout Engine", "grid", ctx, model_fn, fallback_fn, summarize
    )


def _normalize_modules(
    modules: list[dict[str, Any]], ctx: PipelineContext
) -> list[dict[str, Any]]:
    req = ctx.request
    images = ctx.images
    generated_images = ctx.generated_image_names
    normalized: list[dict[str, Any]] = []
    for index, raw in enumerate(modules):
        role = str(raw.get("role") or ("hero" if index == 0 else "feature"))
        is_hero = role == "hero" or index == 0
        height = raw.get("height")
        try:
            height = int(height)
        except (TypeError, ValueError):
            height = req.layout.hero_height if is_hero else req.layout.module_height
        normalized.append(
            {
                "index": index + 1,
                "name": str(raw.get("name") or f"模块{index + 1}"),
                "layer_group": str(raw.get("layer_group") or f"{index + 1:02d}_Module"),
                "layout": str(raw.get("layout") or "image_text"),
                "role": role,
                "height": max(300, min(height, 2400)),
                "image_role": str(raw.get("image_role") or ""),
                "elements": raw.get("elements") or ["BG_背景", "IMG_图片", "TXT_标题"],
                "image_candidates": (
                    generated_images[index : index + 1]
                    + images[index : index + 1]
                    + generated_images[:1]
                    + images[:1]
                ),
            }
        )
    return normalized


def _asset_role(name: str) -> str:
    text = name.lower()
    if any(token in text for token in ("hero", "主视觉", "头图", "banner", "kv")):
        return "hero"
    if any(token in text for token in ("recommend", "人气", "panenka", "campo", "conder", "kids", "v90")):
        return "recommendation"
    if any(token in text for token in ("scenario", "model", "routine", "moves", "小红书", "场景", "搭配", "lifestyle")):
        return "lifestyle"
    if any(token in text for token in ("parameter", "size", "尺码", "参数")):
        return "size"
    if any(token in text for token in ("brand", "story", "logo")):
        return "brand_story"
    if any(token in text for token in ("product_gallery", "_1", "packshot", "product", "产品", "volley")):
        return "product_gallery"
    return "detail"


def _ranked_image_candidates(role: str, ctx: PipelineContext) -> list[str]:
    images = ctx.generated_image_names + ctx.images + ctx.reference_images
    preferred = [name for name in images if _asset_role(name) == role]
    fallback = [name for name in images if name not in preferred]
    return preferred + fallback


def _compact_layout_schema_for_prompt(schema: dict[str, Any]) -> dict[str, Any]:
    sections = [
        {
            "id": str(item.get("id") or ""),
            "name": str(item.get("name") or ""),
            "role": str(item.get("role") or item.get("component_type") or ""),
            "order": int(item.get("order") or index),
            "w": int(item.get("w") or 0),
            "h": int(item.get("h") or 0),
        }
        for index, item in enumerate(schema.get("sections", []), start=1)
        if isinstance(item, dict)
    ]
    slots = [
        {
            "id": str(item.get("id") or ""),
            "section_id": str(item.get("section_id") or ""),
            "role": str(item.get("role") or item.get("asset_type") or ""),
            "priority": str(item.get("priority") or "medium"),
            "required": bool(item.get("required", True)),
            "semantic_tags": item.get("semantic_tags") or [],
            "w": int(item.get("w") or 0),
            "h": int(item.get("h") or 0),
        }
        for item in schema.get("image_slots", [])
        if isinstance(item, dict)
    ]
    return {
        "page_type": str(schema.get("page_type") or "detail_page"),
        "schema_version": str(schema.get("schema_version") or "brandos_layout_schema.v1"),
        "section_count": len(sections),
        "image_slot_count": len(slots),
        "sections": sections[:12],
        "image_slots": slots[:36],
    }


def _layout_prompt_payload(
    ctx: PipelineContext,
    layout_schema: dict[str, Any],
    layout_guard: dict[str, Any],
) -> dict[str, Any]:
    return {
        "design_direction": {
            "direction": ctx.design_direction.get("direction"),
            "page_template": ctx.design_direction.get("page_template"),
            "information_architecture": ctx.design_direction.get("information_architecture"),
        },
        "layout_guard": layout_guard,
        "layout_schema": _compact_layout_schema_for_prompt(layout_schema),
        "layout_blueprint": ctx.layout_blueprint,
        "available_assets": {
            "product_images": ctx.images,
            "reference_images": ctx.reference_images,
            "generated_images": ctx.generated_image_names,
        },
        "canvas": {
            "width": ctx.request.layout.canvas_width,
            "module_count": ctx.request.layout.module_count,
            "hero_height": ctx.request.layout.hero_height,
            "module_height": ctx.request.layout.module_height,
        },
        "constraints": _constraint_prompt_payload(ctx),
    }


def _slot_prompt_items(schema: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    sections = {
        str(section.get("id") or ""): section
        for section in schema.get("sections", [])
        if isinstance(section, dict)
    }
    for slot in schema.get("image_slots", []):
        if not isinstance(slot, dict):
            continue
        section = sections.get(str(slot.get("section_id") or ""), {})
        items.append(
            {
                "slot_id": str(slot.get("id") or ""),
                "section_id": str(slot.get("section_id") or ""),
                "section_name": str(section.get("name") or ""),
                "section_role": str(section.get("role") or section.get("component_type") or ""),
                "role": str(slot.get("role") or slot.get("asset_type") or ""),
                "priority": str(slot.get("priority") or "medium"),
                "required": bool(slot.get("required", True)),
                "semantic_tags": slot.get("semantic_tags") or [],
                "size": {
                    "w": int(slot.get("w") or 0),
                    "h": int(slot.get("h") or 0),
                },
            }
        )
    return items


def _modules_from_layout_schema(
    schema: dict[str, Any],
    ctx: PipelineContext,
) -> list[dict[str, Any]]:
    sections = [item for item in schema.get("sections", []) if isinstance(item, dict)]
    image_slots = [item for item in schema.get("image_slots", []) if isinstance(item, dict)]
    text_layers = [item for item in schema.get("text_layers", []) if isinstance(item, dict)]
    if not sections:
        return []

    modules: list[dict[str, Any]] = []
    for index, section in enumerate(sections[: ctx.request.layout.module_count], start=1):
        section_id = str(section.get("id") or f"section_{index:02d}")
        role = _normalize_module_token(
            str(section.get("role") or section.get("component_type") or section_id or section.get("name") or "detail")
        )
        section_slots = [slot for slot in image_slots if str(slot.get("section_id") or "") == section_id]
        section_text = [layer for layer in text_layers if str(layer.get("section_id") or "") == section_id]
        height = section.get("h") or section.get("height") or ctx.request.layout.module_height
        try:
            height = int(height)
        except (TypeError, ValueError):
            height = ctx.request.layout.module_height
        background = section.get("background") if isinstance(section.get("background"), dict) else {}
        primary_slot = section_slots[0] if section_slots else {}
        slot_role = str(primary_slot.get("role") or role)
        modules.append(
            {
                "index": index,
                "name": str(section.get("name") or _role_display_name(role)),
                "layer_group": f"{index:02d}_{role.title().replace('_', '')}",
                "layout": "schema_absolute",
                "role": role or ("hero" if index == 1 else "feature"),
                "height": max(220, min(height, 5000)),
                "image_role": slot_role,
                "elements": ["BG_背景", "IMG_图片槽", "TXT_文本层"],
                "image_candidates": _ranked_image_candidates(slot_role, ctx),
                "layout_schema_section": section,
                "image_slots": section_slots,
                "text_layers": section_text,
                "render_plan": {
                    "variant": "schema_absolute",
                    "background": "schema",
                    "background_color": background.get("color") or ctx.request.layout.background_color,
                    "image": {
                        "enabled": bool(section_slots),
                        "x": int(primary_slot.get("x") or 40),
                        "y": int(primary_slot.get("y") or 120),
                        "w": int(primary_slot.get("w") or max(120, ctx.request.layout.canvas_width - 80)),
                        "h": int(primary_slot.get("h") or 320),
                        "fit": primary_slot.get("fit") or "cover",
                        "crop": primary_slot.get("crop") or "center",
                    },
                    "text": {
                        "x": int((section_text[0] if section_text else {}).get("x") or 40),
                        "y": int((section_text[0] if section_text else {}).get("y") or 48),
                        "w": int((section_text[0] if section_text else {}).get("w") or ctx.request.layout.canvas_width - 80),
                        "align": "left",
                    },
                    "text_layers": section_text,
                    "image_slots": section_slots,
                    "point_style": "list",
                },
            }
        )
    return modules


def _build_layout_guard_report(schema: dict[str, Any], ctx: PipelineContext) -> dict[str, Any]:
    report = validate_layout_schema_payload(schema)
    normalized_schema = (
        report.get("normalized_schema")
        if isinstance(report.get("normalized_schema"), dict)
        else {}
    )
    slots = [item for item in normalized_schema.get("image_slots", []) if isinstance(item, dict)]
    issues = [str(item) for item in report.get("issues", []) if str(item).strip()]
    warnings = [str(item) for item in report.get("warnings", []) if str(item).strip()]
    high_priority_slots = [
        slot
        for slot in slots
        if str(slot.get("priority") or "").lower() == "high" or bool(slot.get("required", True))
    ]

    available_roles = sorted(
        {_asset_role(name) for name in [*ctx.images, *ctx.reference_images, *ctx.generated_image_names]}
    )
    required_roles = sorted(
        {str(slot.get("role") or slot.get("asset_type") or "detail") for slot in high_priority_slots}
    )
    missing_roles = [
        role for role in required_roles if role not in available_roles and role not in {"detail", "hero"}
    ]
    if missing_roles:
        warnings.append(f"高优先级图片槽缺少对应素材角色：{', '.join(missing_roles)}")

    status = "blocked" if issues else ("warning" if warnings else "passed")
    return {
        "status": status,
        "can_execute": not issues,
        "error_code": _guard_error_code("layout_guard", status),
        "issues": issues,
        "warnings": warnings,
        "section_count": int(report.get("section_count") or 0),
        "image_slot_count": int(report.get("image_slot_count") or 0),
        "high_priority_slot_count": int(report.get("high_priority_slot_count") or 0),
        "required_asset_roles": required_roles,
        "available_asset_roles": available_roles,
        "missing_asset_roles": missing_roles,
    }


def _validate_layout_schema(schema: dict[str, Any], ctx: PipelineContext) -> dict[str, Any]:
    guard = _build_layout_guard_report(schema, ctx)
    report = validate_layout_schema_payload(schema)
    normalized_schema = (
        report.get("normalized_schema")
        if isinstance(report.get("normalized_schema"), dict)
        else {}
    )
    sections = [item for item in normalized_schema.get("sections", []) if isinstance(item, dict)]
    slots = [item for item in normalized_schema.get("image_slots", []) if isinstance(item, dict)]
    issues = list(guard["issues"])
    warnings = list(guard["warnings"])
    if schema and not slots:
        warnings.append("layout_schema 缺少 image_slots，图片匹配会退回模块级候选")
    section_ids = {str(item.get("id") or "") for item in sections}
    for index, section in enumerate(sections, start=1):
        for key in ("id", "name", "w", "h"):
            if not section.get(key):
                warnings.append(f"section[{index}] 缺少 {key}")
        try:
            if int(section.get("w") or 0) <= 0 or int(section.get("h") or 0) <= 0:
                issues.append(f"section[{index}] 宽高无效")
        except (TypeError, ValueError):
            issues.append(f"section[{index}] 宽高不是数字")
    for index, slot in enumerate(slots, start=1):
        section_id = str(slot.get("section_id") or "")
        if section_id and section_id not in section_ids:
            warnings.append(f"image_slot[{index}] 引用不存在的 section_id={section_id}")
        for key in ("x", "y", "w", "h"):
            if slot.get(key) is None:
                warnings.append(f"image_slot[{index}] 缺少 {key}")
    available_roles = sorted({_asset_role(name) for name in [*ctx.images, *ctx.reference_images, *ctx.generated_image_names]})
    required_roles = sorted({str(slot.get("role") or slot.get("asset_type") or "detail") for slot in slots})
    missing_roles = [role for role in required_roles if role not in available_roles and role not in {"detail", "hero"}]
    return {
        "status": "failed" if issues else ("warning" if warnings or missing_roles else "passed"),
        "issues": issues,
        "warnings": warnings,
        "section_count": int(report.get("section_count") or len(sections)),
        "image_slot_count": int(report.get("image_slot_count") or len(slots)),
        "guard_status": guard["status"],
        "guard_can_execute": guard["can_execute"],
        "high_priority_slot_count": int(report.get("high_priority_slot_count") or guard["high_priority_slot_count"]),
        "required_asset_roles": required_roles,
        "available_asset_roles": available_roles,
        "missing_asset_roles": missing_roles,
    }


def _build_asset_match_report(modules: list[dict[str, Any]], ctx: PipelineContext) -> dict[str, Any]:
    assets = ctx.images + ctx.reference_images + ctx.generated_image_names
    used_assets: set[str] = set()
    matches = []
    unmatched = []

    def candidate_score(name: str, slot: dict[str, Any], module: dict[str, Any]) -> tuple[int, int, int, str]:
        role = str(slot.get("role") or slot.get("asset_type") or module.get("role") or "detail")
        normalized_name = name.lower()
        asset_role = _asset_role(name)
        semantic_tags = [str(tag).lower() for tag in slot.get("semantic_tags") or [] if str(tag).strip()]
        score = 0
        if asset_role == role:
            score += 60
        elif role in {"hero", "product_gallery"} and asset_role in {"product_gallery", "detail"}:
            score += 40
        elif role in {"scenario", "lifestyle"} and asset_role == "lifestyle":
            score += 40
        elif role in {"parameter", "size"} and asset_role == "size":
            score += 40
        elif role in {"brand_story"} and asset_role == "brand_story":
            score += 40
        elif asset_role == "detail":
            score += 20

        if str(module.get("role") or "") == "hero" and asset_role in {"hero", "product_gallery", "detail"}:
            score += 10
        if name in ctx.images:
            score += 8
        elif name in ctx.reference_images:
            score += 5
        elif name in ctx.generated_image_names:
            score += 2
        if name in used_assets:
            score -= 12

        tag_hits = 0
        for tag in semantic_tags:
            token = tag.replace("_", " ").strip()
            if not token:
                continue
            parts = [part for part in token.split() if len(part) > 1]
            if token in normalized_name or any(part in normalized_name for part in parts):
                tag_hits += 1
        score += tag_hits * 6
        return (score, tag_hits, 1 if name in ctx.images else 0, name)

    slot_queue: list[tuple[int, int, dict[str, Any], dict[str, Any]]] = []
    for module_index, module in enumerate(modules):
        for slot_index, slot in enumerate(module.get("image_slots") or []):
            if not isinstance(slot, dict):
                continue
            priority = str(slot.get("priority") or "medium").lower()
            required = bool(slot.get("required", True))
            weight = 0 if (required or priority == "high") else (1 if priority == "medium" else 2)
            slot_queue.append((weight, module_index * 100 + slot_index, module, slot))

    for _, _, module, slot in sorted(slot_queue, key=lambda item: (item[0], item[1])):
        role = str(slot.get("role") or slot.get("asset_type") or module.get("role") or "detail")
        ranked = sorted(
            assets,
            key=lambda name: candidate_score(name, slot, module),
            reverse=True,
        )
        candidates = [name for name in ranked if candidate_score(name, slot, module)[0] > 0] or ranked
        chosen = candidates[0] if candidates else ""
        if chosen:
            used_assets.add(chosen)
            slot["matched_asset"] = chosen
        item = {
            "slot_id": slot.get("id") or "",
            "section_id": slot.get("section_id") or "",
            "role": role,
            "priority": str(slot.get("priority") or "medium"),
            "required": bool(slot.get("required", True)),
            "semantic_tags": slot.get("semantic_tags") or [],
            "chosen_asset": chosen,
            "candidate_count": len(candidates),
            "top_candidates": candidates[:5],
        }
        matches.append(item)
        if not chosen:
            unmatched.append(item)

    for module in modules:
        slot_assets = [
            str(slot.get("matched_asset") or "").strip()
            for slot in module.get("image_slots") or []
            if isinstance(slot, dict) and str(slot.get("matched_asset") or "").strip()
        ]
        merged_candidates = []
        for name in [*slot_assets, *(module.get("image_candidates") or [])]:
            if name and name not in merged_candidates:
                merged_candidates.append(name)
        if merged_candidates:
            module["image_candidates"] = merged_candidates
    return {
        "status": "passed" if not unmatched else "warning",
        "match_count": len(matches) - len(unmatched),
        "slot_count": len(matches),
        "unmatched_slots": unmatched,
        "matches": matches[:120],
    }


def _asset_guard_action_items(
    missing_roles: list[str],
    missing_slot_ids: list[str],
    layout_failed: bool,
    slot_count: int,
) -> list[str]:
    actions: list[str] = []
    if layout_failed:
        actions.append("先修复 layout_schema / Layout Guard，再进入正式导出。")
    if slot_count == 0:
        actions.append("当前缺少可验证的 image_slots，建议先补齐可执行布局协议。")
    if missing_roles:
        actions.append("补齐关键素材类型：" + "、".join(missing_roles[:6]))
    if missing_slot_ids:
        actions.append("优先替换未命中的关键图片槽：" + "、".join(missing_slot_ids[:6]))
    if not actions:
        actions.append("关键素材已覆盖，可继续进入正式导出或人工精修。")
    return actions


def _build_asset_guard_report(ctx: PipelineContext) -> dict[str, Any]:
    layout_failed = str(ctx.layout_validation.get("status") or "") == "failed"
    modules = ctx.modules
    match_report = ctx.asset_match_report
    slots = [
        slot
        for module in modules
        for slot in (module.get("image_slots") or [])
        if isinstance(slot, dict)
    ]
    required_slots = [
        slot
        for slot in slots
        if bool(slot.get("required", True))
        or str(slot.get("priority") or "").lower() == "high"
    ]
    matched_required = [
        slot for slot in required_slots if str(slot.get("matched_asset") or "").strip()
    ]
    missing_required = [
        slot for slot in required_slots if not str(slot.get("matched_asset") or "").strip()
    ]
    missing_roles = sorted(
        {
            str(slot.get("role") or slot.get("asset_type") or "detail")
            for slot in missing_required
            if str(slot.get("role") or slot.get("asset_type") or "detail") not in {"detail"}
        }
    )
    missing_slot_ids = [
        str(slot.get("id") or slot.get("slot_id") or "")
        for slot in missing_required
        if str(slot.get("id") or slot.get("slot_id") or "").strip()
    ]
    slot_count = int(match_report.get("slot_count") or len(slots))
    match_count = int(match_report.get("match_count") or 0)
    slot_match_rate = round(match_count / slot_count, 3) if slot_count else 0.0

    issues: list[str] = []
    warnings: list[str] = []
    if layout_failed:
        issues.append("Layout Guard / layout_validation 未通过，当前结果不能进入正式导出。")
    if slot_count == 0:
        issues.append("当前没有可验证的 image_slots，无法执行 Asset Guard。")
    if missing_required:
        issues.append(
            "关键图片槽缺少素材："
            + "、".join(missing_slot_ids[:6] or missing_roles[:6] or ["required_slots"])
        )
    elif match_report.get("status") == "warning":
        warnings.append("存在非关键图片槽未命中，建议导出前继续补图。")
    if str(match_report.get("status") or "") == "skipped":
        warnings.append(str(match_report.get("reason") or "图片槽匹配未执行"))

    status = "blocked" if issues else ("warning" if warnings else "passed")
    return {
        "status": status,
        "can_export": not issues,
        "error_code": _guard_error_code("asset_guard", status),
        "issues": issues,
        "warnings": warnings,
        "slot_count": slot_count,
        "match_count": match_count,
        "slot_match_rate": slot_match_rate,
        "required_slot_count": len(required_slots),
        "matched_required_slot_count": len(matched_required),
        "missing_required_slot_ids": missing_slot_ids,
        "missing_required_asset_roles": missing_roles,
        "recommended_actions": _asset_guard_action_items(
            missing_roles,
            missing_slot_ids,
            layout_failed,
            slot_count,
        ),
    }


def _append_unique(items: list[str], values: list[str]) -> None:
    for value in values:
        text = str(value).strip()
        if text and text not in items:
            items.append(text)


def _stage_preflight_signal(ctx: PipelineContext, stage_id: str) -> dict[str, Any]:
    execution = (
        ctx.stage_execution.get(stage_id)
        if isinstance(ctx.stage_execution.get(stage_id), dict)
        else {}
    )
    contract = (
        ctx.stage_contracts.get(stage_id)
        if isinstance(ctx.stage_contracts.get(stage_id), dict)
        else {}
    )
    warnings: list[str] = []
    warning_codes: list[str] = []
    reasons: list[str] = []
    reason_codes: list[str] = []
    recommended_actions: list[str] = []
    contract_status = str(contract.get("status") or "")
    execution_status = str(execution.get("status") or "")
    retry_summary = _retry_summary_payload(stage_id, contract)
    error_code = str(
        execution.get("error_code")
        or contract.get("error_code")
        or (_stage_contract_failure_code(stage_id) if contract_status == "failed" else "")
    )
    if contract_status == "failed":
        reason_codes.append(f"{stage_id}_contract_failed")
        reasons.append(f"{stage_id} 阶段结构校验未通过，当前结果来自回退逻辑。")
        recommended_actions.append(f"修复 {stage_id} 阶段结构输出后重新生成。")
    elif execution_status == "fallback":
        warning_codes.append(f"{stage_id}_fallback_used")
        warnings.append(f"{stage_id} 阶段使用回退结果，建议导出前人工复核。")
        recommended_actions.append(f"复核 {stage_id} 阶段回退结果是否可接受。")
    elif int(contract.get("retries_used") or 0) > 0:
        warning_codes.append(f"{stage_id}_retried_before_passing")
        warnings.append(
            f"{stage_id} 阶段经过 {int(contract.get('retries_used') or 0)} 次重试后才通过结构校验。"
        )
    return {
        "stage_id": stage_id,
        "status": execution_status or contract_status or "unknown",
        "execution_status": execution_status or "unknown",
        "contract_status": contract_status or "unknown",
        "started_at": str(execution.get("started_at") or ""),
        "completed_at": str(execution.get("completed_at") or ""),
        "duration_ms": int(execution.get("duration_ms") or execution.get("elapsed_ms") or 0),
        "error_code": error_code,
        "retry": retry_summary,
        "contract_validation": dict(contract),
        "reasons": reasons,
        "reason_codes": reason_codes,
        "warnings": warnings,
        "warning_codes": warning_codes,
        "recommended_actions": recommended_actions,
    }


def _build_export_preflight(ctx: PipelineContext) -> dict[str, Any]:
    layout_status = str(ctx.layout_validation.get("status") or "failed")
    asset_guard_status = str(ctx.asset_guard.get("status") or "blocked")
    layout_schema_hit = bool(ctx.layout_validation.get("guard_can_execute"))
    checks = {
        "layout_validation": {
            "status": layout_status,
            "guard_can_execute": layout_schema_hit,
            "error_code": str(ctx.layout_validation.get("error_code") or ""),
        },
        "asset_guard": {
            "status": asset_guard_status,
            "can_export": bool(ctx.asset_guard.get("can_export")),
            "error_code": str(ctx.asset_guard.get("error_code") or ""),
        },
    }
    reasons: list[str] = []
    reason_codes: list[str] = []
    warnings: list[str] = []
    warning_codes: list[str] = []
    recommended_actions: list[str] = list(ctx.asset_guard.get("recommended_actions") or [])
    has_blocking_issue = False
    has_review_only_issue = False

    if not layout_schema_hit:
        has_blocking_issue = True
        _append_unique(reasons, ["未命中可执行 layout_schema，当前结果不能进入正式导出。"])
        _append_unique(reason_codes, ["layout_schema_unavailable"])
        _append_unique(recommended_actions, ["先补齐可执行 layout_schema 或修复布局协议。"])
    if layout_status == "failed":
        has_blocking_issue = True
        _append_unique(
            reasons,
            [str(item) for item in ctx.layout_validation.get("issues", []) if str(item).strip()],
        )
        _append_unique(reason_codes, ["layout_validation_failed"])
    elif layout_status == "warning":
        has_review_only_issue = True
        _append_unique(
            warnings,
            [str(item) for item in ctx.layout_validation.get("warnings", []) if str(item).strip()],
        )
        _append_unique(warning_codes, ["layout_validation_warning"])

    if asset_guard_status == "blocked":
        has_review_only_issue = True
        _append_unique(
            reasons,
            [str(item) for item in ctx.asset_guard.get("issues", []) if str(item).strip()],
        )
        _append_unique(reason_codes, ["asset_guard_blocked"])
    elif asset_guard_status == "warning":
        has_review_only_issue = True
        _append_unique(
            warnings,
            [str(item) for item in ctx.asset_guard.get("warnings", []) if str(item).strip()],
        )
        _append_unique(warning_codes, ["asset_guard_warning"])

    stage_checks: dict[str, Any] = {}
    for stage_id in ("image_generation", "copy"):
        signal = _stage_preflight_signal(ctx, stage_id)
        stage_checks[stage_id] = signal
        if signal["reason_codes"]:
            has_review_only_issue = True
        if signal["warning_codes"]:
            has_review_only_issue = True
        _append_unique(reasons, list(signal["reasons"]))
        _append_unique(reason_codes, list(signal["reason_codes"]))
        _append_unique(warnings, list(signal["warnings"]))
        _append_unique(warning_codes, list(signal["warning_codes"]))
        _append_unique(recommended_actions, list(signal["recommended_actions"]))
    checks["stage_contracts"] = stage_checks

    if has_blocking_issue:
        decision = "blocked"
        status = "blocked"
        error_code = "export_preflight_blocked"
        message = "导出前检查未通过，当前结果只能输出诊断与审稿材料。"
    elif has_review_only_issue:
        decision = "review_only"
        status = "warning"
        error_code = "export_preflight_review_only"
        message = "导出前检查存在风险，当前结果仅建议作为 review_only / 审稿包。"
    else:
        decision = "ready"
        status = "passed"
        error_code = ""
        message = "导出前检查通过，允许进入正式导出。"

    return {
        "status": status,
        "decision": decision,
        "error_code": error_code,
        "message": message,
        "reason_codes": reason_codes[:12],
        "warning_codes": warning_codes[:12],
        "reasons": reasons[:12],
        "warnings": warnings[:12],
        "recommended_actions": recommended_actions[:8],
        "checks": checks,
    }


def _build_result_state(ctx: PipelineContext) -> dict[str, Any]:
    export_preflight = _build_export_preflight(ctx)
    critical_stages = _critical_stage_payloads(ctx)
    critical_checks = _critical_check_payloads(ctx, export_preflight)
    layout_status = str(ctx.layout_validation.get("status") or "failed")
    asset_guard_status = str(ctx.asset_guard.get("status") or "blocked")
    layout_schema_hit = bool(ctx.layout_validation.get("guard_can_execute"))
    image_slot_count = int(
        ctx.layout_validation.get("image_slot_count")
        or ctx.asset_match_report.get("slot_count")
        or 0
    )
    slot_match_rate = (
        round(
            int(ctx.asset_match_report.get("match_count") or 0)
            / int(ctx.asset_match_report.get("slot_count") or 1),
            3,
        )
        if int(ctx.asset_match_report.get("slot_count") or 0)
        else 0.0
    )

    reasons = [str(item) for item in export_preflight.get("reasons", []) if str(item).strip()]
    warnings = [str(item) for item in export_preflight.get("warnings", []) if str(item).strip()]
    decision = str(export_preflight.get("decision") or "review_only")

    if decision == "blocked":
        tier = "方向稿"
        tier_code = "directional_draft"
        delivery_status = "blocked"
    elif decision == "review_only":
        tier = "低保真草稿"
        tier_code = "low_fidelity_draft"
        delivery_status = "review_only"
    else:
        tier = "可执行设计稿"
        tier_code = "executable_design"
        delivery_status = "ready"

    return {
        "tier": tier,
        "tier_code": tier_code,
        "delivery_status": delivery_status,
        "fallback_used": delivery_status != "ready",
        "layout_schema_hit": layout_schema_hit,
        "layout_validation_status": layout_status,
        "asset_guard_status": asset_guard_status,
        "image_slot_count": image_slot_count,
        "slot_match_rate": slot_match_rate,
        "reasons": reasons[:10],
        "reason_codes": list(export_preflight.get("reason_codes") or [])[:10],
        "warnings": warnings[:10],
        "warning_codes": list(export_preflight.get("warning_codes") or [])[:10],
        "error_code": str(export_preflight.get("error_code") or ""),
        "recommended_actions": list(export_preflight.get("recommended_actions") or [])[:6],
        "export_preflight": export_preflight,
        "critical_stages": critical_stages,
        "critical_checks": critical_checks,
    }


def _normalize_note_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for raw in value:
        text = str(raw).strip()
        if text and text not in items:
            items.append(text)
    return items


def _build_psd_stage_payload(
    ctx: PipelineContext,
    notes: list[str],
    risks: list[str],
    layer_naming: list[str],
    editability_checks: list[str],
    source: str,
) -> dict[str, Any]:
    return {
        "layer_tree": ctx.psd_layers,
        "notes": notes,
        "risks": risks,
        "layer_naming": layer_naming,
        "editability_checks": editability_checks,
        "asset_guard": ctx.asset_guard,
        "result_state_preview": _build_result_state(ctx),
        "json_contract": {
            "version": "figma_psd_stage.v2",
            "stable_keys": [
                "layer_tree",
                "notes",
                "risks",
                "layer_naming",
                "editability_checks",
                "asset_guard",
                "result_state_preview",
                "json_contract",
                "source",
            ],
            "source": source,
        },
        "source": source,
    }


def _export_review_payload(ctx: PipelineContext, result_state: dict[str, Any]) -> dict[str, Any]:
    delivery_status = str(result_state.get("delivery_status") or "review_only")
    preflight = (
        result_state.get("export_preflight")
        if isinstance(result_state.get("export_preflight"), dict)
        else _build_export_preflight(ctx)
    )
    if delivery_status == "ready":
        status = "ready_for_export"
        message = str(preflight.get("message") or "结构与关键素材已通过守门，允许进入正式导出。")
    elif delivery_status == "review_only":
        status = "review_only"
        message = str(preflight.get("message") or "当前结果仅建议作为低保真草稿 / 审稿包，不建议直接交付正式设计稿。")
    else:
        status = "blocked"
        message = str(preflight.get("message") or "当前结果被 Guard 阻断，只能输出诊断与审稿材料。")
    return {
        "status": status,
        "message": message,
        "error_code": str(preflight.get("error_code") or ""),
        "result_tier": result_state.get("tier"),
        "blocking_reasons": result_state.get("reasons", []),
        "reason_codes": list(result_state.get("reason_codes") or []),
        "warning_codes": list(result_state.get("warning_codes") or []),
        "recommended_actions": result_state.get("recommended_actions", []),
        "checks": preflight.get("checks", {}),
        "critical_stages": result_state.get("critical_stages", {}),
        "critical_checks": result_state.get("critical_checks", {}),
    }


def stage_image_generation(ctx: PipelineContext) -> StageResult:
    req = ctx.request
    layout_schema = _resolve_layout_schema(ctx)
    slot_items = _slot_prompt_items(layout_schema)
    expected_image_count = (
        len(
            [
                item
                for item in slot_items
                if str(item.get("role") or item.get("section_role") or "")
                not in {"brand_story", "cta", "interaction"}
            ]
        )
        if slot_items
        else len(
            [
                item
                for item in ctx.layout_blueprint
                if str(item.get("role") or "") not in {"brand_story", "cta"}
            ]
        )
    )

    def default_images() -> list[dict[str, Any]]:
        generated: list[dict[str, Any]] = []
        if slot_items:
            for index, slot in enumerate(slot_items, start=1):
                role = str(slot.get("role") or slot.get("section_role") or "detail")
                if role in ("brand_story", "cta", "interaction"):
                    continue
                generated.append(
                    {
                        "name": f"generated_{index:02d}_{role}_{slot.get('slot_id') or 'slot'}.svg",
                        "slot_id": slot.get("slot_id"),
                        "section_id": slot.get("section_id"),
                        "module_index": index,
                        "module_name": slot.get("section_name") or slot.get("section_role") or role,
                        "role": role,
                        "image_role": slot.get("role") or role,
                        "source": "generated_placeholder",
                        "prompt": f"{req.brand_name} {req.product_name} {slot.get('section_name') or role} {slot.get('role') or '配图'}",
                    }
                )
            return generated
        for index, item in enumerate(ctx.layout_blueprint, start=1):
            if item.get("role") in ("brand_story", "cta"):
                continue
            generated.append(
                {
                    "name": f"generated_{index:02d}_{item.get('role') or 'module'}.svg",
                    "module_index": index,
                    "module_name": item.get("name"),
                    "role": item.get("role"),
                    "image_role": item.get("image_role") or "模块配图",
                    "source": "generated_placeholder",
                    "prompt": f"{req.brand_name} {req.product_name} {item.get('name')} {item.get('image_role') or '配图'}",
                }
            )
        return generated

    def model_fn() -> dict[str, Any]:
        prompt_payload = {
            "brand": req.brand_name,
            "product": req.product_name,
            "design_direction": {
                "direction": ctx.design_direction.get("direction"),
                "information_architecture": ctx.design_direction.get("information_architecture"),
            },
            "slot_plan": slot_items[:48],
            "layout_blueprint": ctx.layout_blueprint if not slot_items else [],
            "available_assets": {
                "product_images": ctx.images,
                "reference_images": ctx.reference_images,
            },
            "constraints": _constraint_prompt_payload(ctx),
        }
        prompt = (
            "请根据以下结构化图片槽计划输出 images 数组。要求：\n"
            "1. 若存在 slot_plan，优先按 slot 逐一规划，不要只按模块粗略生成。\n"
            "2. 每个元素包含：name, slot_id, section_id, module_index, module_name, role, image_role, source, prompt。\n"
            "3. source 取值建议为 ai_generated 或 reference_derived。\n"
            "4. 同一高优先级 slot 不要复用完全相同的 prompt。\n\n"
            f"{json.dumps(prompt_payload, ensure_ascii=False, indent=2)}"
        )
        data = _invoke_stage_json_with_retry(
            ctx=ctx,
            stage_id="image_generation",
            base_prompt=prompt,
            invoke_model=lambda attempt_prompt: {
                **ctx.llm.invoke_json(req.prompts.design_agent_prompt, attempt_prompt),
                "_slot_plan": slot_items,
                "_expected_image_count": expected_image_count,
                "_require_slot_bindings": bool(slot_items),
            },
        )
        images = data.get("images") or []
        ctx.generated_images = [
            {
                "name": str(item.get("name") or f"generated_{idx + 1:02d}.svg"),
                "slot_id": str(item.get("slot_id") or ""),
                "section_id": str(item.get("section_id") or ""),
                "module_index": int(item.get("module_index") or idx + 1),
                "module_name": str(item.get("module_name") or ""),
                "role": str(item.get("role") or ""),
                "image_role": str(item.get("image_role") or "模块配图"),
                "source": str(item.get("source") or "ai_generated"),
                "prompt": str(item.get("prompt") or ""),
            }
            for idx, item in enumerate(images)
            if isinstance(item, dict)
        ] or default_images()
        return {
            "images": ctx.generated_images,
            "_contract_validation": dict(data.get("_contract_validation") or {}),
        }

    def fallback_fn() -> dict[str, Any]:
        ctx.generated_images = default_images()
        return {"images": ctx.generated_images}

    def summarize(data: dict[str, Any], used: bool) -> str:
        images = data.get("images", [])
        return f"已规划 {len(images)} 张模块配图，供后续 Layout 与导出阶段消费。"

    return _run_stage(
        "image_generation",
        "图片生成 Agent",
        "image",
        ctx,
        model_fn,
        fallback_fn,
        summarize,
    )


def stage_copy(ctx: PipelineContext) -> StageResult:
    req = ctx.request
    module_names = [m["name"] for m in ctx.modules]
    module_contracts = [
        {
            "name": str(module.get("name") or f"模块{index + 1}"),
            "role": str(module.get("role") or ""),
            "required_text_fields": _required_text_fields_for_role(
                str(module.get("role") or "")
            ),
        }
        for index, module in enumerate(ctx.modules)
    ]

    def model_fn() -> dict[str, Any]:
        base_prompt = (
            f"品牌：{req.brand_name}，商品：{req.product_name}\n"
            f"卖点：{ctx.structured_info.get('selling_points')}\n"
            f"{_input_prompt_block(ctx)}"
            f"模块列表：{module_names}\n\n"
            f"{_constraint_prompt_block(ctx)}"
            "请为每个模块生成文案，输出 blocks 为数组，"
            "顺序与模块列表一致，每个元素含："
            "headline(主标题), subtitle(副标题), body(短说明), points(要点数组)。"
            "文案必须基于 brief，不夸大、不使用绝对化或平台风险词。"
        )
        data = _invoke_stage_json_with_retry(
            ctx=ctx,
            stage_id="copy",
            base_prompt=base_prompt,
            invoke_model=lambda attempt_prompt: {
                **ctx.llm.invoke_json(req.prompts.copy_agent_prompt, attempt_prompt),
                "_expected_block_count": len(ctx.modules),
                "_module_contracts": module_contracts,
            },
        )
        blocks = data.get("blocks") or []
        _apply_copy(ctx, blocks)
        return {
            "blocks": [m["copy"] for m in ctx.modules],
            "_contract_validation": dict(data.get("_contract_validation") or {}),
        }

    def fallback_fn() -> dict[str, Any]:
        points = _selling_points(ctx)
        blocks = []
        for index, module in enumerate(ctx.modules):
            if module["role"] == "hero":
                blocks.append(
                    {
                        "headline": req.product_name,
                        "subtitle": req.brand_name,
                        "body": "为日常办公与通勤设计的多功能" + req.product_name,
                        "points": points[:3],
                    }
                )
            elif module["role"] in ("brand_story", "cta"):
                blocks.append(
                    {
                        "headline": req.brand_name if module["role"] == "brand_story" else "延续品牌一致的设计表达",
                        "subtitle": "品牌规则驱动的页面收尾" if module["role"] == "brand_story" else "进入审核与导出",
                        "body": "",
                        "points": [],
                    }
                )
            else:
                point = points[index % len(points)]
                blocks.append(
                    {
                        "headline": point,
                        "subtitle": module["name"],
                        "body": f"{point}，贴合真实使用场景。",
                        "points": [],
                    }
                )
        _apply_copy(ctx, blocks)
        return {"blocks": [m["copy"] for m in ctx.modules]}

    def summarize(data: dict[str, Any], used: bool) -> str:
        first = data.get("blocks", [{}])[0]
        return f"已生成 {len(data.get('blocks', []))} 段模块文案，主标题示例：{first.get('headline', '-')}。"

    return _run_stage(
        "copy", "文案 Agent", "type", ctx, model_fn, fallback_fn, summarize
    )


def _apply_copy(ctx: PipelineContext, blocks: list[dict[str, Any]]) -> None:
    for index, module in enumerate(ctx.modules):
        block = blocks[index] if index < len(blocks) else {}
        module["copy"] = {
            "headline": str(block.get("headline") or module["name"]),
            "subtitle": str(block.get("subtitle") or ""),
            "body": str(block.get("body") or ""),
            "points": list(block.get("points") or []),
        }


def stage_psd(ctx: PipelineContext) -> StageResult:
    req = ctx.request

    def build_layers() -> list[dict[str, Any]]:
        layers = []
        for module in ctx.modules:
            children = ["BG_背景"]
            if module["role"] not in ("brand_story", "cta"):
                children.append(f"IMG_{module['image_role'] or '图片'}")
            children.append("TXT_主标题")
            if module["copy"].get("subtitle"):
                children.append("TXT_副标题")
            if module["copy"].get("body"):
                children.append("TXT_正文")
            for i, _ in enumerate(module["copy"].get("points", []), start=1):
                children.append(f"TXT_要点{i}")
            if module["role"] in ("hero", "brand_story", "cta"):
                children.append("LOGO_品牌")
            layers.append({"group": module["layer_group"], "layers": children})
        return layers

    def model_fn() -> dict[str, Any]:
        if str(ctx.asset_guard.get("status") or "") == "blocked":
            raise LLMUnavailable("Asset Guard 未通过，Figma / PSD 阶段仅输出审稿包结构")
        # 设计稿阶段以确定性结构为主，模型只补充命名建议与注意事项。
        prompt = (
            f"模块与文案：{json.dumps([{'name': m['name'], 'copy': m['copy']} for m in ctx.modules], ensure_ascii=False)}\n\n"
            f"布局校验：{json.dumps(ctx.layout_validation, ensure_ascii=False)}\n"
            f"素材守门：{json.dumps(ctx.asset_guard, ensure_ascii=False)}\n\n"
            f"{_constraint_prompt_block(ctx)}"
            "请输出 Figma / PSD 生产说明，字段："
            "notes(数组)，risks(数组)，layer_naming(数组)，editability_checks(数组)。"
        )
        data = ctx.llm.invoke_json(req.prompts.psd_agent_prompt, prompt)
        ctx.psd_layers = build_layers()
        notes = _normalize_note_list(data.get("notes")) or [
            "所有文字保持可编辑文本层，不要转曲。",
            "图片与占位图层保持独立命名，避免合并到背景。",
        ]
        risks = _normalize_note_list(data.get("risks"))
        layer_naming = _normalize_note_list(data.get("layer_naming")) or [
            "模块分组统一使用 01_Hero / 02_Feature 这类稳定编号。",
            "图片图层统一使用 IMG_ 前缀，文本图层统一使用 TXT_ 前缀。",
        ]
        editability_checks = _normalize_note_list(data.get("editability_checks")) or [
            "检查主标题、副标题、正文和要点仍为文字层。",
            "检查每个模块图片槽都可被设计师直接替换。",
        ]
        return _build_psd_stage_payload(
            ctx,
            notes,
            risks,
            layer_naming,
            editability_checks,
            "model_augmented",
        )

    def fallback_fn() -> dict[str, Any]:
        ctx.psd_layers = build_layers()
        notes = [
            "所有文字保留为可编辑文字图层",
            "图片独立成层，命名以 IMG_ 前缀",
            "每个模块独立分组，分组名带序号",
        ]
        if str(ctx.asset_guard.get("status") or "") == "blocked":
            notes.insert(0, "Asset Guard 未通过：当前仅输出审稿用结构，不建议直接正式导出。")
        return _build_psd_stage_payload(
            ctx,
            notes,
            [],
            [
                "模块分组统一带序号，便于 Figma / PSD 双端复用。",
                "图片槽优先继承 schema_absolute / image_slots 坐标。",
            ],
            [
                "文字图层保持可编辑。",
                "图片槽与背景层不要合并。",
            ],
            "deterministic_fallback",
        )

    def summarize(data: dict[str, Any], used: bool) -> str:
        asset_status = str((data.get("asset_guard") or {}).get("status") or "unknown")
        suffix = "，当前仅建议审稿" if asset_status == "blocked" else ""
        return (
            f"已规划 {len(data.get('layer_tree', []))} 个 Figma Frame / PSD 图层分组，"
            f"文字层全部可编辑，Asset Guard={asset_status}{suffix}。"
        )

    return _run_stage(
        "figma_psd", "Figma / PSD 生成 Agent", "file-image", ctx, model_fn, fallback_fn, summarize
    )


def stage_design_score(ctx: PipelineContext) -> StageResult:
    ctx.check_cancelled("design_score:before")
    req = ctx.request
    started = time.perf_counter()
    started_at = datetime.utcnow()
    set_run_state(ctx.run_id, "running", "design_score", "Design Score", "check-circle")
    _workflow_log(ctx.run_id, "开始阶段：Design Score (design_score)")
    module_count = len(ctx.modules)
    brand_constraints = len(ctx.design_direction.get("brand_constraints", []))
    asset_penalty = 0 if ctx.images else 6
    layout_schema_hit = bool(ctx.layout_validation.get("guard_can_execute"))
    slot_count = int(
        ctx.asset_match_report.get("slot_count")
        or ctx.layout_validation.get("image_slot_count")
        or 0
    )
    match_count = int(ctx.asset_match_report.get("match_count") or 0)
    slot_match_rate = round(match_count / slot_count, 3) if slot_count else 0.0
    result_preview = _build_result_state(ctx)
    score = {
        "brand_match": min(96, 84 + brand_constraints * 3),
        "layout_quality": min(94, 82 + module_count),
        "visual_consistency": min(95, 88 + (2 if req.typography.lock_brand_typography else 0)),
        "readability": 88,
        "conversion_score": 86,
    }
    if ctx.layout_validation.get("status") == "passed":
        score["layout_quality"] = min(98, score["layout_quality"] + 5)
    elif ctx.layout_validation.get("status") == "failed":
        score["layout_quality"] = max(60, score["layout_quality"] - 24)
    elif ctx.layout_validation.get("status") == "warning":
        score["layout_quality"] = max(66, score["layout_quality"] - 8)
    if not layout_schema_hit:
        score["layout_quality"] = max(60, score["layout_quality"] - 12)
    if ctx.asset_match_report.get("status") == "passed" and ctx.asset_match_report.get("slot_count"):
        score["visual_consistency"] = min(98, score["visual_consistency"] + 4)
    elif ctx.asset_match_report.get("unmatched_slots"):
        score["visual_consistency"] = max(60, score["visual_consistency"] - 8)
    if str(ctx.asset_guard.get("status") or "") == "blocked":
        score["visual_consistency"] = max(60, score["visual_consistency"] - 16)
        score["conversion_score"] = max(60, score["conversion_score"] - 10)
    elif str(ctx.asset_guard.get("status") or "") == "warning":
        score["visual_consistency"] = max(60, score["visual_consistency"] - 6)
    golden_reference_count = len([name for name in ctx.reference_images if any(token in name.lower() for token in ("长图", "golden", "reference", "案例"))])
    golden_alignment = min(96, 78 + module_count * 2 + golden_reference_count * 8)
    if ctx.layout_validation.get("status") == "failed":
        golden_alignment = max(60, golden_alignment - 24)
    if ctx.asset_match_report.get("status") in {"skipped", "warning"}:
        golden_alignment = max(60, golden_alignment - 8)
    if not layout_schema_hit:
        golden_alignment = max(60, golden_alignment - 10)
    score["golden_case_alignment"] = golden_alignment
    score = {key: max(60, value - asset_penalty) for key, value in score.items()}
    overall = round(sum(score.values()) / len(score), 1)
    ctx.design_score = {
        **score,
        "overall": overall,
        "metrics": {
            "layout_schema_hit": layout_schema_hit,
            "fallback_used": bool(result_preview.get("fallback_used")),
            "layout_validation_status": ctx.layout_validation.get("status"),
            "image_slot_count": slot_count,
            "slot_match_rate": slot_match_rate,
            "asset_guard_status": ctx.asset_guard.get("status"),
            "result_tier_preview": result_preview.get("tier"),
        },
        "explain": [
            "评分用于给设计负责人提供可解释审核依据，不替代人工判断。",
            "品牌匹配优先参考 Core Rule、Derived Rule 与当前页面模板。",
            "layout_schema 未命中或 Layout Guard 失败时，布局质量和黄金案例贴合度会显著下降。",
            "Asset Guard 未通过或关键图片槽未命中时，视觉一致性和转化评分会被扣分。",
            "黄金案例匹配优先参考可执行 Layout Schema、图片槽命中率和参考案例输入。",
        ],
        "layout_validation": ctx.layout_validation,
        "asset_match_report": ctx.asset_match_report,
        "asset_guard": ctx.asset_guard,
        "result_state_preview": result_preview,
        "blocking_issues": [
            *([] if overall >= 85 else ["建议补充高质量商品图后再导出正式设计稿"]),
            *ctx.layout_validation.get("issues", []),
            *ctx.asset_guard.get("issues", []),
            *[f"缺少图片槽素材：{item.get('slot_id') or item.get('role')}" for item in ctx.asset_match_report.get("unmatched_slots", [])[:5]],
        ],
    }
    summary = f"综合评分 {overall}，品牌匹配 {ctx.design_score['brand_match']}，布局质量 {ctx.design_score['layout_quality']}。"
    ctx.report_parts.append(f"## Design Score\n{summary}")
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    completed_at = datetime.utcnow()
    _workflow_log(
        ctx.run_id,
        f"结束阶段：Design Score (design_score)，status=completed，used_model=False，elapsed_ms={elapsed_ms}，summary={summary}",
        ctx.design_score,
    )
    ctx.stage_execution["design_score"] = {
        "status": "completed",
        "used_model": False,
        "summary": summary,
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "duration_ms": elapsed_ms,
        "error_code": "",
        "retry": {},
        "error": {},
        "contract_validation": {},
    }
    result = StageResult(
        id="design_score",
        title="Design Score",
        icon="check-circle",
        status="completed",
        summary=summary,
        detail=json.dumps(ctx.design_score, ensure_ascii=False, indent=2),
        data=ctx.design_score,
        used_model=False,
        elapsed_ms=elapsed_ms,
        started_at=started_at.isoformat(),
        completed_at=completed_at.isoformat(),
        duration_ms=elapsed_ms,
        error_code="",
        retry={},
    )
    append_stage_result(ctx.run_id, result)
    ctx.check_cancelled("design_score:after")
    return result


def stage_outputs(ctx: PipelineContext) -> StageResult:
    ctx.check_cancelled("output_review:before")
    req = ctx.request
    started = time.perf_counter()
    started_at = datetime.utcnow()
    set_run_state(ctx.run_id, "running", "output_review", "输出、审核与反馈", "check-circle")
    _workflow_log(ctx.run_id, "开始阶段：输出、审核与反馈 (output_review)")
    output_labels = {
        "detail_page": "商品详情页结构化方案",
        "figma_page": "Figma 页面",
        "psd_file": "PSD 兼容文件",
        "main_image": "主图设计稿",
        "banner": "广告 Banner",
    }
    produced = [output_labels.get(o.value, o.value) for o in req.output_types]
    review_checklist = [
        "品牌一致性：是否符合品牌视觉规范",
        "字体字号：是否使用指定字体和允许字号",
        "图片质量：抠图、清晰度、色彩是否达标",
        "版式质量：是否接近参考图风格、是否美观",
        "文案准确性：是否与 brief 一致、是否有夸大",
        "Figma/PSD 可编辑性：图层是否清晰、文字是否可编辑",
        "Asset Guard：关键图片槽是否都有明确素材命中",
    ]
    ctx.result_state = _build_result_state(ctx)
    export_review = _export_review_payload(ctx, ctx.result_state)
    ctx.outputs = {
        "produced": produced,
        "review_checklist": review_checklist,
        "result_state": ctx.result_state,
        "export_review": export_review,
        "feedback_capture": {
            "tracked_changes": ["模块隐藏/删除", "字体字号调整", "颜色调整", "文案修改", "图片替换"],
            "learning_policy": "本阶段只记录设计师修改，不自动强化学习、不自动覆盖品牌规则。",
            "effective_constraints": ctx.effective_constraints,
            "feedback_constraints": ctx.feedback_constraints,
        },
        "next_step": (
            "进入正式导出与人工审核：设计师初审 → 运营/品牌方审核 → 记录反馈 → 交付上线。"
            if export_review["status"] == "ready_for_export"
            else "先补结构 / 素材缺口，再进行设计师初审与二次生成。"
        ),
    }
    summary = (
        f"已产出：{'、'.join(produced)}；当前结果等级：{ctx.result_state.get('tier')}；"
        f"导出判定：{export_review['status']}。"
    )
    ctx.report_parts.append(f"## 输出、审核与反馈\n{summary}")
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    completed_at = datetime.utcnow()
    _workflow_log(
        ctx.run_id,
        f"结束阶段：输出、审核与反馈 (output_review)，status=completed，used_model=False，elapsed_ms={elapsed_ms}，summary={summary}",
        ctx.outputs,
    )
    ctx.stage_execution["output_review"] = {
        "status": "completed",
        "used_model": False,
        "summary": summary,
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "duration_ms": elapsed_ms,
        "error_code": str(ctx.result_state.get("error_code") or ""),
        "retry": {},
        "error": {},
        "contract_validation": {},
    }
    result = StageResult(
        id="output_review",
        title="输出、审核与反馈",
        icon="check-circle",
        status="completed",
        summary=summary,
        detail=json.dumps(ctx.outputs, ensure_ascii=False, indent=2),
        data=ctx.outputs,
        used_model=False,
        elapsed_ms=elapsed_ms,
        started_at=started_at.isoformat(),
        completed_at=completed_at.isoformat(),
        duration_ms=elapsed_ms,
        error_code=str(ctx.result_state.get("error_code") or ""),
        retry={},
    )
    append_stage_result(ctx.run_id, result)
    ctx.check_cancelled("output_review:after")
    return result


PIPELINE_STAGES: list[Callable[[PipelineContext], StageResult]] = [
    stage_vision,
    stage_structured,
    stage_brand_rag,
    stage_design,
    stage_image_generation,
    stage_layout,
    stage_copy,
    stage_psd,
    stage_design_score,
    stage_outputs,
]


def run_pipeline(
    request: WorkflowRequest,
    assets: list[UploadedAsset],
    run_id: str = "",
    cancel_checker: Callable[[], bool] | None = None,
    selected_rule_context: dict[str, Any] | None = None,
    feedback_constraints: dict[str, Any] | None = None,
) -> tuple[list[StageResult], PipelineContext]:
    reset_run(run_id or "local")
    input_layers = build_input_layers(request.product_brief, assets)
    try:
        database.persist_run_started(
            run_id or "local",
            request,
            assets,
            input_layers=input_layers,
        )
    except Exception as exc:
        print(f"[DB] persist_run_started failed: {exc}", flush=True)
    ctx = PipelineContext(
        request=request,
        assets=assets,
        llm=LLMClient(request.model_settings, run_id=run_id or "local"),
        run_id=run_id or "local",
        cancel_checker=cancel_checker or (lambda: False),
        core_rule=dict((selected_rule_context or {}).get("coreRule") or {}),
        detail_page_rule=dict((selected_rule_context or {}).get("detailPageRule") or {}),
        requirement_constraints=request.requirement_constraints.model_dump(),
        feedback_constraints=dict(feedback_constraints or {}),
    )
    ctx.input_layers = input_layers
    ctx.effective_constraints = _merge_effective_constraints(
        ctx.requirement_constraints,
        ctx.feedback_constraints,
    )
    ctx.layout_blueprint = _build_layout_blueprint(
        ctx.detail_page_rule,
        request.layout.module_count,
        ctx.effective_constraints,
        ctx.strict_mode,
    )
    set_run_state(ctx.run_id, "running", None)
    _workflow_log(
        ctx.run_id,
        "工作流启动",
        {
            "project_name": request.project_name,
            "brand_name": request.brand_name,
            "product_name": request.product_name,
            "assets": [asset.model_dump() for asset in assets],
            "selected_rules": selected_rule_context or {},
            "requirement_constraints": ctx.requirement_constraints,
            "feedback_constraints": ctx.feedback_constraints,
            "effective_constraints": ctx.effective_constraints,
            "input_layers": {
                "brief_asset_count": ctx.input_layers.get("brief_asset_count", 0),
                "wireframe_asset_count": ctx.input_layers.get("wireframe_asset_count", 0),
                "brief_summary": ctx.input_layers.get("brief_summary", ""),
                "layout_reference": ctx.input_layers.get("layout_reference", ""),
                "raw_wireframe_dump": ctx.input_layers.get("raw_wireframe_dump", ""),
            },
        },
    )
    stages = [stage(ctx) for stage in PIPELINE_STAGES]
    set_run_state(ctx.run_id, "completed", None)
    _workflow_log(ctx.run_id, "工作流完成", {"stage_count": len(stages)})
    return stages, ctx
