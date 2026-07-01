import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from backend.app.pipeline import _build_result_state, _export_review_payload
from backend.app.render import write_artifacts


def _sample_spec() -> dict:
    return {
        "project": {
            "name": "Test Project",
            "brand": "BrandOS",
            "product": "Backpack",
        },
        "canvas": {
            "width": 790,
            "height": 820,
            "background_color": "#ffffff",
            "accent_color": "#111827",
        },
        "typography": {
            "title_size": 28,
            "subtitle_size": 18,
            "body_size": 12,
            "text_color": "#1f2937",
        },
        "modules": [
            {
                "index": 1,
                "name": "Hero",
                "role": "hero",
                "height": 820,
                "layer_group": "01_Hero",
                "image_role": "hero",
                "copy": {
                    "headline": "轻量通勤",
                    "subtitle": "主打卖点",
                    "body": "适合日常通勤与短途出差。",
                    "points": ["轻量", "耐磨"],
                },
                "render_plan": {
                    "variant": "hero_split",
                    "background": "card",
                    "text": {"x": 40, "y": 56, "w": 280, "align": "left"},
                    "image": {"enabled": False, "x": 0, "y": 0, "w": 0, "h": 0},
                    "point_style": "list",
                },
            }
        ],
        "result_state": {
            "tier": "低保真草稿",
            "tier_code": "low_fidelity_draft",
            "delivery_status": "review_only",
            "error_code": "export_preflight_review_only",
            "reason_codes": ["copy_contract_failed"],
            "warning_codes": ["layout_validation_warning"],
            "export_preflight": {
                "status": "warning",
                "decision": "review_only",
                "error_code": "export_preflight_review_only",
                "reason_codes": ["copy_contract_failed"],
                "warning_codes": ["layout_validation_warning"],
                "reasons": ["文案阶段发生 contract fallback"],
                "warnings": ["布局校验存在 warning"],
                "recommended_actions": ["补齐 copy 后再正式导出"],
                "checks": {
                    "layout_validation": {"status": "warning", "guard_can_execute": True},
                    "asset_guard": {"status": "passed", "can_export": True},
                },
            },
        },
        "export_review": {
            "status": "review_only",
            "message": "当前结果仅建议作为低保真草稿 / 审稿包。",
            "error_code": "export_preflight_review_only",
            "reason_codes": ["copy_contract_failed"],
            "warning_codes": ["layout_validation_warning"],
            "recommended_actions": ["补齐 copy 后再正式导出"],
            "checks": {
                "layout_validation": {"status": "warning", "guard_can_execute": True},
                "asset_guard": {"status": "passed", "can_export": True},
            },
        },
    }


class ArtifactMetadataTests(unittest.TestCase):
    def test_write_artifacts_emits_stable_output_metadata(self) -> None:
        spec = _sample_spec()
        ctx = SimpleNamespace(run_id="artifact-metadata-test", assets=[], generated_images=[])

        with tempfile.TemporaryDirectory() as tmpdir:
            result = write_artifacts(Path(tmpdir), spec, ctx)

            self.assertEqual(result["result_tier"], "低保真草稿")
            self.assertEqual(result["delivery_status"], "review_only")
            self.assertEqual(result["error_code"], "export_preflight_review_only")
            self.assertEqual(result["reason_codes"], ["copy_contract_failed"])
            self.assertEqual(result["warning_codes"], ["layout_validation_warning"])
            self.assertTrue(str(result["output_metadata"]).endswith("output_metadata.json"))

            metadata = json.loads(Path(str(result["output_metadata"])).read_text(encoding="utf-8"))
            self.assertEqual(metadata["run_id"], "artifact-metadata-test")
            self.assertEqual(metadata["export"]["status"], result["export_status"])
            self.assertEqual(metadata["result"]["error_code"], "export_preflight_review_only")
            self.assertEqual(metadata["result"]["reason_codes"], ["copy_contract_failed"])
            self.assertEqual(
                metadata["result"]["export_preflight"]["decision"], "review_only"
            )
            self.assertEqual(metadata["result"]["export_review"]["status"], "review_only")
            self.assertEqual(metadata["artifacts"]["design_spec"], "design_spec.json")

    def test_write_artifacts_preserves_stage_driven_review_only_chain(self) -> None:
        pipeline_ctx = SimpleNamespace(
            layout_validation={
                "status": "passed",
                "guard_can_execute": True,
                "image_slot_count": 2,
                "issues": [],
                "warnings": [],
            },
            asset_guard={
                "status": "passed",
                "can_export": True,
                "recommended_actions": [],
                "issues": [],
                "warnings": [],
            },
            asset_match_report={"match_count": 2, "slot_count": 2},
            stage_execution={
                "image_generation": {"status": "completed"},
                "copy": {"status": "fallback"},
            },
            stage_contracts={
                "image_generation": {"status": "passed", "retries_used": 0},
                "copy": {"status": "failed", "retries_used": 1},
            },
        )
        result_state = _build_result_state(pipeline_ctx)
        export_review = _export_review_payload(pipeline_ctx, result_state)
        spec = _sample_spec()
        spec["result_state"] = result_state
        spec["export_review"] = export_review
        artifact_ctx = SimpleNamespace(run_id="stage-chain-test", assets=[], generated_images=[])

        with tempfile.TemporaryDirectory() as tmpdir:
            result = write_artifacts(Path(tmpdir), spec, artifact_ctx)

            self.assertEqual(result["delivery_status"], "review_only")
            self.assertEqual(result["error_code"], "export_preflight_review_only")
            self.assertIn("copy_contract_failed", result["reason_codes"])
            self.assertEqual(result["export_review"]["status"], "review_only")
            self.assertEqual(
                result["export_preflight"]["checks"]["stage_contracts"]["copy"]["contract_status"],
                "failed",
            )

            metadata = json.loads(Path(str(result["output_metadata"])).read_text(encoding="utf-8"))
            self.assertEqual(metadata["export"]["decision"], "review_only")
            self.assertEqual(metadata["export"]["error_code"], "export_preflight_review_only")
            self.assertIn("copy_contract_failed", metadata["export"]["reason_codes"])
            self.assertEqual(metadata["result"]["export_review"]["status"], "review_only")
            self.assertEqual(
                metadata["result"]["export_preflight"]["checks"]["stage_contracts"]["copy"][
                    "contract_status"
                ],
                "failed",
            )


if __name__ == "__main__":
    unittest.main()
