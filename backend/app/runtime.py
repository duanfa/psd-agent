from __future__ import annotations

import json
import sys
import time
from collections.abc import Mapping
from datetime import date, datetime
from pathlib import Path
from typing import Any

from . import database

MAX_LOG_LINES = 1200

RUN_LOGS: dict[str, list[str]] = {}
RUN_STATE: dict[str, dict[str, str | None]] = {}
RUN_STAGES: dict[str, list[dict[str, Any]]] = {}


def reset_run(run_id: str) -> None:
    RUN_LOGS[run_id] = []
    RUN_STAGES[run_id] = []
    RUN_STATE[run_id] = {"status": "running", "current_stage": None}


def sanitize_for_log(value: Any) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if hasattr(value, "model_dump"):
        try:
            return sanitize_for_log(value.model_dump(mode="json"))
        except Exception:
            return sanitize_for_log(value.model_dump())
    if isinstance(value, Mapping):
        if "image_url" in value:
            image_url = value.get("image_url") or {}
            url = image_url.get("url", "") if isinstance(image_url, dict) else str(image_url)
            sanitized = {key: sanitize_for_log(item) for key, item in value.items()}
            sanitized["image_url"] = f"<image data url omitted, length={len(str(url))}>"
            return sanitized
        return {key: sanitize_for_log(item) for key, item in value.items()}
    if isinstance(value, list | tuple | set):
        return [sanitize_for_log(item) for item in value]
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    return str(value)


def _safe_console_print(message: str) -> None:
    try:
        print(message, flush=True)
        return
    except UnicodeEncodeError:
        pass

    stream = sys.stdout
    text = f"{message}\n"
    encoding = getattr(stream, "encoding", None) or "utf-8"
    buffer = getattr(stream, "buffer", None)
    if buffer is not None:
        buffer.write(text.encode(encoding, errors="replace"))
        buffer.flush()
        return
    stream.write(text.encode(encoding, errors="replace").decode(encoding, errors="replace"))
    stream.flush()


def append_log(run_id: str, scope: str, title: str, payload: Any | None = None) -> None:
    if isinstance(payload, str):
        body = payload
    elif payload is None:
        body = ""
    else:
        body = json.dumps(sanitize_for_log(payload), ensure_ascii=False, indent=2)

    timestamp = time.strftime("%H:%M:%S")
    header = f"[{timestamp}][{scope}] {title}"
    line = f"{header}\n{body}" if body else header
    _safe_console_print(line)

    logs = RUN_LOGS.setdefault(run_id, [])
    logs.append(line)
    if len(logs) > MAX_LOG_LINES:
        del logs[: len(logs) - MAX_LOG_LINES]
    try:
        database.persist_log(run_id, scope, title, line, sanitize_for_log(payload))
    except Exception as exc:
        _safe_console_print(f"[DB] persist_log failed: {exc}")


def set_run_state(
    run_id: str,
    status: str,
    current_stage: str | None = None,
    current_stage_title: str | None = None,
    current_stage_icon: str | None = None,
) -> None:
    RUN_STATE[run_id] = {
        "status": status,
        "current_stage": current_stage,
        "current_stage_title": current_stage_title,
        "current_stage_icon": current_stage_icon,
    }
    try:
        database.persist_run_state(
            run_id,
            status,
            current_stage,
            current_stage_title,
            current_stage_icon,
        )
    except Exception as exc:
        _safe_console_print(f"[DB] persist_run_state failed: {exc}")


def append_stage_result(run_id: str, stage: Any) -> None:
    if hasattr(stage, "model_dump"):
        data = stage.model_dump()
    elif hasattr(stage, "dict"):
        data = stage.dict()
    else:
        data = dict(stage)

    stages = RUN_STAGES.setdefault(run_id, [])
    stages[:] = [item for item in stages if item.get("id") != data.get("id")]
    stages.append(data)
    try:
        database.persist_stage(run_id, data)
    except Exception as exc:
        _safe_console_print(f"[DB] persist_stage failed: {exc}")


def get_run_snapshot(run_id: str) -> dict[str, Any]:
    state = RUN_STATE.get(run_id, {"status": "unknown", "current_stage": None})
    stages = list(RUN_STAGES.get(run_id, []))
    if state.get("status") == "unknown" and not stages:
        try:
            persisted = database.load_run_snapshot(run_id)
            if persisted:
                return persisted
        except Exception as exc:
            _safe_console_print(f"[DB] load_run_snapshot failed: {exc}")
    current_stage = state.get("current_stage")
    if state.get("status") == "running" and current_stage:
        if not any(stage.get("id") == current_stage for stage in stages):
            stages.append(
                {
                    "id": current_stage,
                    "title": state.get("current_stage_title") or current_stage,
                    "icon": state.get("current_stage_icon") or "sparkles",
                    "status": "running",
                    "summary": "当前阶段正在执行，大模型请求与返回会实时写入日志。",
                    "detail": "",
                    "data": {},
                    "used_model": False,
                    "elapsed_ms": 0,
                    "started_at": None,
                    "completed_at": None,
                    "duration_ms": 0,
                    "error_code": "",
                    "retry": {},
                }
            )
    return {
        "run_id": run_id,
        "status": state.get("status", "unknown"),
        "current_stage": current_stage,
        "logs": RUN_LOGS.get(run_id, []),
        "stages": stages,
    }
