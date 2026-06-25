from __future__ import annotations

import base64
import io
import json
import os
import re
from pathlib import Path
from typing import Any

from .models import ModelConfig


class LLMUnavailable(Exception):
    """模型不可用（缺依赖、缺 key 或初始化失败）时抛出，触发规则降级。"""


def resolve_api_key(settings: ModelConfig) -> str | None:
    env_key_name = f"{settings.provider.upper()}_API_KEY"
    return (
        settings.api_key
        or os.getenv(env_key_name)
        or os.getenv("OPENAI_API_KEY")
        or os.getenv("DASHSCOPE_API_KEY")
    )


def resolve_base_url(settings: ModelConfig, model_name: str | None = None) -> str | None:
    if settings.base_url:
        return settings.base_url
    if settings.provider == "openai":
        name = (model_name or settings.model or "").lower()
        if name.startswith(("qwen", "qwq")):
            return "https://dashscope.aliyuncs.com/compatible-mode/v1"
    return None


def encode_image_data_url(path: str, max_edge: int = 1280) -> str:
    """读取图片并编码为 data URL；优先用 Pillow 压缩，缺依赖时回退原图。"""
    file_path = Path(path)
    if not file_path.is_file():
        raise LLMUnavailable(f"图片不存在：{path}")
    try:
        from PIL import Image  # type: ignore

        with Image.open(file_path) as img:
            img = img.convert("RGB")
            img.thumbnail((max_edge, max_edge))
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=82)
            raw = buffer.getvalue()
        mime = "image/jpeg"
    except ModuleNotFoundError as exc:
        # 没有 Pillow：直接读原图，但限制体积，避免 base64 过大。
        raw = file_path.read_bytes()
        if len(raw) > 4_000_000:
            raise LLMUnavailable(
                f"未安装 Pillow 且图片过大（{len(raw) // 1024}KB），跳过多模态识别"
            ) from exc
        suffix = file_path.suffix.lower().lstrip(".") or "png"
        mime = f"image/{'jpeg' if suffix in ('jpg', 'jpeg') else suffix}"
    except Exception as exc:  # pragma: no cover - 图片解码异常
        raise LLMUnavailable(f"图片编码失败：{exc}") from exc

    encoded = base64.b64encode(raw).decode("ascii")
    return f"data:{mime};base64,{encoded}"


class LLMClient:
    """对 langchain init_chat_model 的薄封装，提供文本与 JSON 两种调用。"""

    def __init__(self, settings: ModelConfig):
        self.settings = settings
        self._model = None
        self._vision_model = None

    def _build_model(self, model_name: str):
        if not self.settings.enable_deepagents:
            raise LLMUnavailable("界面已关闭 DeepAgents / 模型调用")
        try:
            from langchain.chat_models import init_chat_model
        except Exception as exc:  # pragma: no cover - 取决于本地环境
            raise LLMUnavailable(f"langchain 依赖不可用：{exc}") from exc

        api_key = resolve_api_key(self.settings)
        if not api_key:
            raise LLMUnavailable("未配置模型 API Key（请在界面填写或设置环境变量）")

        kwargs: dict[str, Any] = {
            "model": model_name,
            "model_provider": self.settings.provider,
            "temperature": self.settings.temperature,
            "max_tokens": self.settings.max_tokens,
            "api_key": api_key,
        }
        base_url = resolve_base_url(self.settings, model_name)
        if base_url:
            kwargs["base_url"] = base_url
        try:
            return init_chat_model(**kwargs)
        except Exception as exc:  # pragma: no cover - 取决于模型服务
            raise LLMUnavailable(f"模型初始化失败：{exc}") from exc

    def ensure_ready(self) -> None:
        if self._model is None:
            self._model = self._build_model(self.settings.model)

    def _ensure_vision(self) -> None:
        if self._vision_model is None:
            self._vision_model = self._build_model(self.settings.vision_model)

    def invoke_text(self, system_prompt: str, user_prompt: str) -> str:
        self.ensure_ready()
        assert self._model is not None
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        try:
            response = self._model.invoke(messages)
        except Exception as exc:  # pragma: no cover - 取决于模型服务
            raise LLMUnavailable(f"模型调用失败：{exc}") from exc
        content = getattr(response, "content", None)
        if isinstance(content, list):
            content = "".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in content
            )
        return str(content or "").strip()

    def invoke_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        guidance = (
            "\n\n请只输出一个合法 JSON 对象，不要包含解释文字、注释或 markdown 代码块标记。"
        )
        text = self.invoke_text(system_prompt + guidance, user_prompt)
        return _parse_json_object(text)

    def invoke_vision_json(
        self,
        system_prompt: str,
        user_prompt: str,
        image_paths: list[str],
    ) -> dict[str, Any]:
        """把真实图片送入多模态模型并要求返回 JSON。"""
        self._ensure_vision()
        assert self._vision_model is not None
        guidance = (
            "\n\n请基于以上图片和文字输出一个合法 JSON 对象，"
            "不要包含解释文字、注释或 markdown 代码块标记。"
        )
        content: list[dict[str, Any]] = [{"type": "text", "text": user_prompt + guidance}]
        for path in image_paths:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": encode_image_data_url(path)},
                }
            )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content},
        ]
        try:
            response = self._vision_model.invoke(messages)
        except Exception as exc:  # pragma: no cover - 取决于模型服务
            raise LLMUnavailable(f"多模态模型调用失败：{exc}") from exc
        text = getattr(response, "content", None)
        if isinstance(text, list):
            text = "".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in text
            )
        return _parse_json_object(str(text or ""))


def _parse_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    else:
        brace = text.find("{")
        last = text.rfind("}")
        if brace != -1 and last != -1 and last > brace:
            text = text[brace : last + 1]
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LLMUnavailable(f"模型未返回合法 JSON：{exc}") from exc
    if not isinstance(data, dict):
        raise LLMUnavailable("模型 JSON 顶层必须是对象")
    return data
