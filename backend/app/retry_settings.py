from __future__ import annotations

import json
import os
from copy import deepcopy
from dataclasses import dataclass
from functools import lru_cache
from typing import Any


DEFAULT_RETRYABLE_ERROR_CODES = (
    "invalid_payload_type",
    "invalid_field_type",
    "missing_required_array",
    "missing_required_fields",
    "count_mismatch",
    "invalid_reference",
    "duplicate_identifier",
    "contract_violation",
)

DEFAULT_NON_RETRYABLE_ERROR_CODES = ("unknown_stage",)


@dataclass(frozen=True)
class RetryPolicy:
    enabled: bool = True
    max_attempts: int = 2
    retryable_error_codes: tuple[str, ...] = DEFAULT_RETRYABLE_ERROR_CODES
    non_retryable_error_codes: tuple[str, ...] = DEFAULT_NON_RETRYABLE_ERROR_CODES


DEFAULT_STAGE_RETRY_POLICY_SETTINGS: dict[str, Any] = {
    "default": {
        "enabled": False,
        "max_attempts": 1,
        "retryable_error_codes": list(DEFAULT_RETRYABLE_ERROR_CODES),
        "non_retryable_error_codes": list(DEFAULT_NON_RETRYABLE_ERROR_CODES),
    },
    "stages": {
        "product_brief": {
            "enabled": True,
            "max_attempts": 2,
        },
        "brand_knowledge": {
            "enabled": True,
            "max_attempts": 2,
        },
        "page_planner": {
            "enabled": True,
            "max_attempts": 2,
        },
        "layout_engine": {
            "enabled": True,
            "max_attempts": 2,
        },
        "image_generation": {
            "enabled": True,
            "max_attempts": 3,
        },
        "copy": {
            "enabled": True,
            "max_attempts": 3,
            "retryable_error_codes": [
                "invalid_payload_type",
                "invalid_field_type",
                "missing_required_array",
                "missing_required_fields",
                "count_mismatch",
                "contract_violation",
            ],
        },
    },
}


def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in patch.items():
        current = merged.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            merged[key] = _deep_merge(current, value)
        else:
            merged[key] = deepcopy(value)
    return merged


def _normalize_error_code_list(
    value: Any,
    *,
    fallback: tuple[str, ...],
) -> tuple[str, ...]:
    if not isinstance(value, list):
        return fallback
    normalized: list[str] = []
    for raw in value:
        code = str(raw or "").strip()
        if code and code not in normalized:
            normalized.append(code)
    return tuple(normalized or fallback)


def _read_env_overrides() -> dict[str, Any]:
    raw = os.getenv("BRANDOS_STAGE_RETRY_POLICY_OVERRIDES", "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:  # pragma: no cover - 配置错误只在运行时出现
        raise ValueError("环境变量 BRANDOS_STAGE_RETRY_POLICY_OVERRIDES 不是合法 JSON") from exc
    if not isinstance(data, dict):
        raise ValueError("环境变量 BRANDOS_STAGE_RETRY_POLICY_OVERRIDES 必须是 JSON object")
    return data


@lru_cache(maxsize=1)
def load_stage_retry_policy_settings() -> dict[str, Any]:
    return _deep_merge(DEFAULT_STAGE_RETRY_POLICY_SETTINGS, _read_env_overrides())


def clear_stage_retry_policy_settings_cache() -> None:
    load_stage_retry_policy_settings.cache_clear()


def resolve_stage_retry_policy(stage_id: str) -> RetryPolicy:
    settings = load_stage_retry_policy_settings()
    default_policy = settings.get("default")
    stage_overrides = (settings.get("stages") or {}).get(stage_id)
    merged = _deep_merge(
        default_policy if isinstance(default_policy, dict) else {},
        stage_overrides if isinstance(stage_overrides, dict) else {},
    )
    return RetryPolicy(
        enabled=bool(merged.get("enabled", False)),
        max_attempts=max(1, int(merged.get("max_attempts") or 1)),
        retryable_error_codes=_normalize_error_code_list(
            merged.get("retryable_error_codes"),
            fallback=DEFAULT_RETRYABLE_ERROR_CODES,
        ),
        non_retryable_error_codes=_normalize_error_code_list(
            merged.get("non_retryable_error_codes"),
            fallback=DEFAULT_NON_RETRYABLE_ERROR_CODES,
        ),
    )
