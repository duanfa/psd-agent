import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backend.app.models import StagePayloadValidationError, validate_stage_contract_payload
from backend.app.pipeline import (
    StageContractError,
    _build_retry_prompt,
    _build_export_preflight,
    _build_result_state,
    _export_review_payload,
    _invoke_stage_json_with_retry,
)
from backend.app.retry_settings import (
    clear_stage_retry_policy_settings_cache,
    resolve_stage_retry_policy,
)


class _FakeContext:
    def __init__(self) -> None:
        self.run_id = "unit-test-run"

    def check_cancelled(self, checkpoint: str) -> None:
        return None


class StageContractTests(unittest.TestCase):
    def test_product_brief_contract_normalizes_lists(self) -> None:
        payload = {
            "brand": " BrandOS ",
            "product": " 电脑包 ",
            "audience": "通勤人群",
            "selling_points": [
                {"title": "轻量通勤"},
                "多分区收纳",
                "多分区收纳",
            ],
            "specifications": {"material": "尼龙"},
            "scenarios": [{"name": "办公"}, "出差"],
            "design_focus": "保持商务感与可编辑性",
        }

        result = validate_stage_contract_payload("product_brief", payload)

        self.assertEqual(result["brand"], "BrandOS")
        self.assertEqual(result["product"], "电脑包")
        self.assertEqual(result["selling_points"], ["轻量通勤", "多分区收纳"])
        self.assertEqual(result["scenarios"], ["办公", "出差"])

    def test_page_planner_contract_rejects_missing_template(self) -> None:
        with self.assertRaisesRegex(ValueError, "page_template"):
            validate_stage_contract_payload(
                "page_planner",
                {
                    "direction": "极简",
                    "information_architecture": ["首屏", "卖点"],
                    "tone": "冷静商务",
                    "image_strategy": "优先主图",
                },
            )

    def test_retry_helper_recovers_on_second_attempt(self) -> None:
        responses = [
            {
                "brand": "BrandOS",
                "product": "电脑包",
                "audience": "通勤人群",
                "selling_points": [],
                "specifications": {},
                "scenarios": ["办公"],
                "design_focus": "突出功能",
            },
            {
                "brand": "BrandOS",
                "product": "电脑包",
                "audience": "通勤人群",
                "selling_points": ["轻量通勤", "多分区收纳"],
                "specifications": {},
                "scenarios": ["办公"],
                "design_focus": "突出功能",
            },
        ]
        prompts: list[str] = []

        def invoke_model(prompt: str) -> dict:
            prompts.append(prompt)
            return responses[len(prompts) - 1]

        with patch("backend.app.pipeline._workflow_log"):
            result = _invoke_stage_json_with_retry(
                ctx=_FakeContext(),
                stage_id="product_brief",
                invoke_model=invoke_model,
                base_prompt="输出 Product Brief JSON",
            )

        self.assertEqual(result["selling_points"], ["轻量通勤", "多分区收纳"])
        self.assertEqual(result["_contract_validation"]["attempt_count"], 2)
        self.assertEqual(result["_contract_validation"]["retries_used"], 1)
        self.assertTrue(result["_contract_validation"]["did_retry"])
        self.assertEqual(result["_contract_validation"]["final_status"], "passed")
        self.assertEqual(result["_contract_validation"]["policy"]["max_attempts"], 2)
        self.assertEqual(
            result["_contract_validation"]["retry"]["status"],
            "passed_after_retry",
        )
        self.assertEqual(len(result["_contract_validation"]["history"]), 2)
        self.assertEqual(
            result["_contract_validation"]["history"][0]["error_code"],
            "missing_required_fields",
        )
        self.assertEqual(
            result["_contract_validation"]["history"][0]["error_category"],
            "contract",
        )
        self.assertEqual(
            result["_contract_validation"]["history"][0]["error_family"],
            "missing",
        )
        self.assertEqual(len(prompts), 2)
        self.assertIn("上一次输出未通过结构校验", prompts[1])
        self.assertIn("优先补齐这些缺口", prompts[1])
        self.assertIn("selling_points", prompts[1])

    def test_retry_helper_exhausts_retryable_errors(self) -> None:
        prompts: list[str] = []
        ctx = _FakeContext()

        def invoke_model(prompt: str) -> dict:
            prompts.append(prompt)
            return {
                "images": [
                    {
                        "name": "hero_visual",
                        "slot_id": "hero_slot",
                        "section_id": "hero_section",
                        "module_index": 1,
                        "module_name": "Hero",
                        "role": "hero",
                        "image_role": "hero",
                        "source": "ai_generated",
                        "prompt": "主视觉图",
                    }
                ],
                "_slot_plan": [
                    {"slot_id": "hero_slot", "role": "hero", "required": True, "priority": "high"},
                    {"slot_id": "detail_slot", "role": "detail", "required": True, "priority": "medium"},
                ],
                "_expected_image_count": 2,
                "_require_slot_bindings": True,
            }

        with patch("backend.app.pipeline._workflow_log"):
            with self.assertRaises(StageContractError) as cm:
                _invoke_stage_json_with_retry(
                    ctx=ctx,
                    stage_id="image_generation",
                    invoke_model=invoke_model,
                    base_prompt="输出 Image JSON",
                )

        error = cm.exception
        self.assertEqual(error.error_code, "image_generation_schema_contract_failed")
        self.assertIn("images 数量不足，期望至少 2 条，实际 1 条", error.issues)
        self.assertIn("images 未覆盖关键 slot_id：detail_slot", error.issues)
        self.assertEqual(
            ctx.stage_contracts["image_generation"]["retry"]["error_code"],
            "image_generation_retry_exhausted",
        )
        self.assertEqual(len(prompts), 3)

    def test_non_retryable_error_does_not_retry(self) -> None:
        prompts: list[str] = []
        ctx = _FakeContext()

        def invoke_model(prompt: str) -> dict:
            prompts.append(prompt)
            return {"blocks": []}

        with patch("backend.app.pipeline._workflow_log"), patch(
            "backend.app.pipeline.validate_stage_contract_payload",
            side_effect=StagePayloadValidationError(
                "未知阶段结构校验：copy",
                error_code="unknown_stage",
                issues=["未知阶段结构校验：copy"],
            ),
        ):
            with self.assertRaises(StageContractError):
                _invoke_stage_json_with_retry(
                    ctx=ctx,
                    stage_id="copy",
                    invoke_model=invoke_model,
                    base_prompt="输出 Copy JSON",
                )

        metadata = ctx.stage_contracts["copy"]
        self.assertEqual(len(prompts), 1)
        self.assertEqual(metadata["attempt_count"], 1)
        self.assertFalse(metadata["did_retry"])
        self.assertEqual(metadata["final_status"], "failed")
        self.assertEqual(metadata["final_error_code"], "unknown_stage")
        self.assertEqual(metadata["stop_reason"], "non_retryable_error")
        self.assertEqual(metadata["policy"]["max_attempts"], 3)
        self.assertEqual(metadata["history"][0]["error_code"], "unknown_stage")
        self.assertFalse(metadata["history"][0]["retry_scheduled"])
        self.assertEqual(metadata["final_error_category"], "unknown")
        self.assertEqual(metadata["final_error_family"], "unsupported_stage")

    def test_image_generation_contract_normalizes_slot_bound_images(self) -> None:
        payload = {
            "images": [
                {
                    "name": "hero_visual",
                    "slot_id": "hero_slot",
                    "section_id": "hero_section",
                    "module_index": "1",
                    "module_name": "Hero",
                    "role": "hero",
                    "image_role": "hero",
                    "source": " ai_generated ",
                    "prompt": " 主视觉图 ",
                },
                {
                    "slot_id": "detail_slot",
                    "section_id": "detail_section",
                    "module_index": 2,
                    "module_name": "卖点模块",
                    "role": "detail",
                    "image_role": "detail",
                    "source": "",
                    "prompt": "细节特写",
                },
            ],
            "_slot_plan": [
                {"slot_id": "hero_slot", "role": "hero", "required": True, "priority": "high"},
                {"slot_id": "detail_slot", "role": "detail", "required": True, "priority": "medium"},
            ],
            "_expected_image_count": 2,
            "_require_slot_bindings": True,
        }

        result = validate_stage_contract_payload("image_generation", payload)

        self.assertEqual(result["images"][0]["name"], "hero_visual.svg")
        self.assertEqual(result["images"][0]["module_index"], 1)
        self.assertEqual(result["images"][0]["source"], "ai_generated")
        self.assertEqual(result["images"][0]["prompt"], "主视觉图")
        self.assertEqual(result["images"][1]["name"], "generated_02_detail.svg")

    def test_copy_contract_rejects_missing_required_fields(self) -> None:
        with self.assertRaisesRegex(ValueError, "必填字段"):
            validate_stage_contract_payload(
                "copy",
                {
                    "blocks": [
                        {
                            "headline": "轻量通勤",
                            "subtitle": "Hero 模块",
                            "body": "",
                            "points": [],
                        }
                    ],
                    "_expected_block_count": 1,
                    "_module_contracts": [
                        {
                            "name": "Hero",
                            "role": "hero",
                            "required_text_fields": ["headline", "subtitle", "body"],
                        }
                    ],
                },
            )

    def test_stage_contract_error_adds_type_category_metadata(self) -> None:
        with self.assertRaises(StagePayloadValidationError) as cm:
            validate_stage_contract_payload(
                "layout_engine",
                {"modules": [None]},
            )

        error = cm.exception
        self.assertEqual(error.error_code, "invalid_field_type")
        self.assertEqual(error.error_category, "schema")
        self.assertEqual(error.error_family, "type")

    def test_retry_prompt_uses_reference_specific_guidance(self) -> None:
        prompt = _build_retry_prompt(
            stage_id="image_generation",
            base_prompt="输出 Image JSON",
            error_code="invalid_reference",
            error_category="reference",
            error_family="invalid",
            issues=[
                "image_slots 引用了不存在的 section：slot_hero",
                "section[2] required_image_slots 存在跨 section 槽位引用：detail_slot",
            ],
            last_payload={"images": []},
        )

        self.assertIn("错误类别：reference", prompt)
        self.assertIn("所有 section_id、slot_id 和 required_image_slots 引用都必须来自当前 JSON 中已声明的 id", prompt)
        self.assertIn("slot_hero", prompt)
        self.assertIn("detail_slot", prompt)

    def test_stage_retry_policy_supports_env_override(self) -> None:
        clear_stage_retry_policy_settings_cache()
        override = {
            "stages": {
                "copy": {
                    "max_attempts": 4,
                    "retryable_error_codes": [
                        "missing_required_fields",
                        "count_mismatch",
                    ],
                }
            }
        }

        with patch.dict(
            os.environ,
            {"BRANDOS_STAGE_RETRY_POLICY_OVERRIDES": json.dumps(override)},
        ):
            clear_stage_retry_policy_settings_cache()
            policy = resolve_stage_retry_policy("copy")

        clear_stage_retry_policy_settings_cache()
        self.assertEqual(policy.max_attempts, 4)
        self.assertEqual(
            policy.retryable_error_codes,
            ("missing_required_fields", "count_mismatch"),
        )

    def test_result_state_marks_contract_fallback_as_review_only(self) -> None:
        ctx = SimpleNamespace(
            layout_validation={
                "status": "passed",
                "guard_can_execute": True,
                "image_slot_count": 2,
                "error_code": "",
            },
            asset_guard={
                "status": "passed",
                "can_export": True,
                "recommended_actions": [],
                "issues": [],
                "warnings": [],
                "error_code": "",
            },
            asset_match_report={"match_count": 2, "slot_count": 2},
            stage_execution={
                "image_generation": {
                    "status": "completed",
                    "started_at": "2026-07-01T09:00:00",
                    "completed_at": "2026-07-01T09:00:02",
                    "duration_ms": 2000,
                    "error_code": "",
                    "retry": {
                        "status": "not_needed",
                        "attempt_count": 1,
                        "retries_used": 0,
                        "max_attempts": 3,
                        "did_retry": False,
                        "error_code": "",
                        "final_error_code": "",
                    },
                },
                "copy": {
                    "status": "fallback",
                    "started_at": "2026-07-01T09:00:02",
                    "completed_at": "2026-07-01T09:00:05",
                    "duration_ms": 3000,
                    "error_code": "copy_schema_contract_failed",
                    "retry": {
                        "status": "retry_exhausted",
                        "attempt_count": 3,
                        "retries_used": 2,
                        "max_attempts": 3,
                        "did_retry": True,
                        "error_code": "copy_retry_exhausted",
                        "final_error_code": "missing_required_fields",
                    },
                },
            },
            stage_contracts={
                "image_generation": {
                    "status": "passed",
                    "retries_used": 0,
                    "error_code": "",
                },
                "copy": {
                    "status": "failed",
                    "retries_used": 2,
                    "error_code": "copy_schema_contract_failed",
                    "final_error_code": "missing_required_fields",
                    "attempt_count": 3,
                    "max_attempts": 3,
                    "stop_reason": "max_attempts_reached",
                    "did_retry": True,
                },
            },
        )

        result = _build_result_state(ctx)

        self.assertEqual(result["delivery_status"], "review_only")
        self.assertIn("copy_contract_failed", result["reason_codes"])
        self.assertEqual(result["error_code"], "export_preflight_review_only")
        self.assertEqual(
            result["critical_stages"]["copy"]["error_code"],
            "copy_schema_contract_failed",
        )
        self.assertEqual(
            result["critical_stages"]["copy"]["retry"]["error_code"],
            "copy_retry_exhausted",
        )

    def test_export_review_propagates_stage_contract_signals(self) -> None:
        ctx = SimpleNamespace(
            layout_validation={
                "status": "passed",
                "guard_can_execute": True,
                "image_slot_count": 2,
                "issues": [],
                "warnings": [],
                "error_code": "",
            },
            asset_guard={
                "status": "passed",
                "can_export": True,
                "recommended_actions": [],
                "issues": [],
                "warnings": [],
                "error_code": "",
            },
            asset_match_report={"match_count": 2, "slot_count": 2},
            stage_execution={
                "image_generation": {
                    "status": "completed",
                    "started_at": "2026-07-01T09:00:00",
                    "completed_at": "2026-07-01T09:00:02",
                    "duration_ms": 2000,
                    "error_code": "",
                    "retry": {
                        "status": "passed_after_retry",
                        "attempt_count": 2,
                        "retries_used": 1,
                        "max_attempts": 3,
                        "did_retry": True,
                        "error_code": "",
                        "final_error_code": "",
                    },
                },
                "copy": {
                    "status": "fallback",
                    "started_at": "2026-07-01T09:00:02",
                    "completed_at": "2026-07-01T09:00:05",
                    "duration_ms": 3000,
                    "error_code": "copy_schema_contract_failed",
                    "retry": {
                        "status": "retry_exhausted",
                        "attempt_count": 3,
                        "retries_used": 2,
                        "max_attempts": 3,
                        "did_retry": True,
                        "error_code": "copy_retry_exhausted",
                        "final_error_code": "missing_required_fields",
                    },
                },
            },
            stage_contracts={
                "image_generation": {
                    "status": "passed",
                    "retries_used": 1,
                    "attempt_count": 2,
                    "max_attempts": 3,
                    "did_retry": True,
                    "error_code": "",
                },
                "copy": {
                    "status": "failed",
                    "retries_used": 2,
                    "attempt_count": 3,
                    "max_attempts": 3,
                    "did_retry": True,
                    "stop_reason": "max_attempts_reached",
                    "error_code": "copy_schema_contract_failed",
                    "final_error_code": "missing_required_fields",
                },
            },
        )

        preflight = _build_export_preflight(ctx)
        result_state = _build_result_state(ctx)
        export_review = _export_review_payload(ctx, result_state)

        self.assertEqual(preflight["decision"], "review_only")
        self.assertEqual(
            preflight["checks"]["stage_contracts"]["image_generation"]["warning_codes"],
            ["image_generation_retried_before_passing"],
        )
        self.assertEqual(
            preflight["checks"]["stage_contracts"]["image_generation"]["contract_validation"]["retries_used"],
            1,
        )
        self.assertEqual(
            preflight["checks"]["stage_contracts"]["copy"]["reason_codes"],
            ["copy_contract_failed"],
        )
        self.assertEqual(
            preflight["checks"]["stage_contracts"]["copy"]["contract_validation"]["status"],
            "failed",
        )
        self.assertEqual(
            preflight["checks"]["stage_contracts"]["copy"]["error_code"],
            "copy_schema_contract_failed",
        )
        self.assertEqual(
            preflight["checks"]["stage_contracts"]["copy"]["retry"]["error_code"],
            "copy_retry_exhausted",
        )
        self.assertIn("copy_contract_failed", result_state["reason_codes"])
        self.assertIn("image_generation_retried_before_passing", result_state["warning_codes"])
        self.assertEqual(result_state["delivery_status"], "review_only")
        self.assertEqual(result_state["error_code"], "export_preflight_review_only")
        self.assertEqual(
            result_state["critical_checks"]["export_preflight"]["error_code"],
            "export_preflight_review_only",
        )
        self.assertEqual(export_review["status"], "review_only")
        self.assertEqual(export_review["error_code"], "export_preflight_review_only")
        self.assertIn("copy_contract_failed", export_review["reason_codes"])
        self.assertIn("image_generation_retried_before_passing", export_review["warning_codes"])
        self.assertEqual(
            export_review["critical_stages"]["copy"]["retry"]["error_code"],
            "copy_retry_exhausted",
        )
        self.assertEqual(
            export_review["checks"]["stage_contracts"]["copy"]["execution_status"],
            "fallback",
        )


if __name__ == "__main__":
    unittest.main()
