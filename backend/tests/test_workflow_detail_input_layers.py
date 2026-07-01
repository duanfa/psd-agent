import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from backend.app import database


@contextmanager
def temporary_database():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "workflow-detail-input-layers.db"
        engine = create_engine(f"sqlite+pysqlite:///{db_path}", future=True)
        event.listen(
            engine,
            "connect",
            lambda dbapi_connection, _connection_record: dbapi_connection.create_collation(
                "utf8mb4_unicode_ci",
                lambda left, right: (left > right) - (left < right),
            ),
        )
        session_local = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
        try:
            database.Base.metadata.create_all(bind=engine)
            with patch.object(database, "engine", engine), patch.object(database, "SessionLocal", session_local):
                yield
        finally:
            engine.dispose()


class WorkflowDetailInputLayersTests(unittest.TestCase):
    def test_get_workflow_detail_returns_stage_timing_and_retry_fields(self) -> None:
        with temporary_database():
            database.persist_run_started(
                "run-stage-meta",
                {
                    "project_name": "详情页自动生成",
                    "brand_name": "VEJA",
                    "product_name": "Volley",
                    "workflow_mode": "smart_recommend",
                    "product_brief": "",
                },
                [],
            )
            database.persist_stage(
                "run-stage-meta",
                {
                    "id": "copy",
                    "title": "文案 Agent",
                    "icon": "type",
                    "status": "fallback",
                    "summary": "文案阶段发生回退",
                    "detail": "{}",
                    "data": {},
                    "used_model": True,
                    "elapsed_ms": 3200,
                    "started_at": "2026-07-01T09:00:00",
                    "completed_at": "2026-07-01T09:00:03.200000",
                    "duration_ms": 3200,
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
            )

            detail = database.get_workflow_detail("run-stage-meta")

        self.assertIsNotNone(detail)
        assert detail is not None
        self.assertEqual(detail["stages"][0]["status"], "fallback")
        self.assertEqual(detail["stages"][0]["duration_ms"], 3200)
        self.assertEqual(detail["stages"][0]["error_code"], "copy_schema_contract_failed")
        self.assertEqual(detail["stages"][0]["retry"]["error_code"], "copy_retry_exhausted")
        self.assertEqual(detail["stages"][0]["started_at"], "2026-07-01T09:00:00")

    def test_get_workflow_detail_returns_persisted_input_layers(self) -> None:
        raw_dump = '{"schema_version":"wireframe_spec.v1","nodes":"' + ("x" * 4500) + '"}'
        input_layers = {
            "user_brief": "用户 brief：法式复古、运动感。",
            "brief_summary": "[用户 brief]\n法式复古、运动感。\n\n[来源文件] layout.xlsx\n商品名称 | VEJA Volley",
            "layout_reference": "[WireframeSpec]\n- section hero: 首屏主视觉",
            "raw_wireframe_dump": raw_dump,
            "sources": [
                {
                    "name": "layout.xlsx",
                    "bucket": "brief",
                    "has_brief_summary": True,
                    "has_layout_reference": True,
                    "has_raw_wireframe_dump": True,
                }
            ],
            "brief_asset_count": 1,
            "wireframe_asset_count": 1,
        }

        with temporary_database():
            database.persist_run_started(
                "run-persisted",
                {
                    "project_name": "详情页自动生成",
                    "brand_name": "VEJA",
                    "product_name": "Volley",
                    "workflow_mode": "smart_recommend",
                    "product_brief": "用户 brief：法式复古、运动感。",
                },
                [
                    {
                        "name": "layout.xlsx",
                        "bucket": "brief",
                        "saved_path": "D:/tmp/layout.xlsx",
                        "extracted_text": "[Sheet] Brief\n商品名称 | VEJA Volley",
                    }
                ],
                input_layers=input_layers,
            )

            detail = database.get_workflow_detail("run-persisted")

        self.assertIsNotNone(detail)
        assert detail is not None
        self.assertEqual(detail["inputLayers"]["source"], "request_payload")
        self.assertIn("VEJA Volley", detail["inputLayers"]["brief_summary"])
        self.assertIn("[WireframeSpec]", detail["inputLayers"]["layout_reference"])
        self.assertTrue(detail["inputLayers"]["raw_wireframe_dump_truncated"])
        self.assertEqual(detail["inputLayers"]["raw_wireframe_dump_chars"], len(raw_dump))

    def test_get_workflow_detail_falls_back_to_logged_input_layers(self) -> None:
        with temporary_database():
            database.persist_run_started(
                "run-logged",
                {
                    "project_name": "详情页自动生成",
                    "brand_name": "VEJA",
                    "product_name": "Volley",
                    "workflow_mode": "smart_recommend",
                    "product_brief": "",
                },
                [],
            )
            database.persist_log(
                "run-logged",
                "Workflow",
                "工作流启动",
                "工作流启动",
                {
                    "input_layers": {
                        "brief_summary": "[来源文件] layout.xlsx\n商品名称 | VEJA Volley",
                        "layout_reference": "[WireframeSpec]\n- section hero: 首屏主视觉",
                        "raw_wireframe_dump": '{"schema_version":"wireframe_spec.v1"}',
                        "sources": [
                            {
                                "name": "layout.xlsx",
                                "bucket": "brief",
                                "has_brief_summary": True,
                                "has_layout_reference": True,
                                "has_raw_wireframe_dump": True,
                            }
                        ],
                        "brief_asset_count": 1,
                        "wireframe_asset_count": 1,
                    }
                },
            )

            detail = database.get_workflow_detail("run-logged")

        self.assertIsNotNone(detail)
        assert detail is not None
        self.assertEqual(detail["inputLayers"]["source"], "workflow_log")
        self.assertIn("VEJA Volley", detail["inputLayers"]["brief_summary"])
        self.assertIn("首屏主视觉", detail["inputLayers"]["layout_reference"])
        self.assertIn("wireframe_spec.v1", detail["inputLayers"]["raw_wireframe_dump"])

    def test_get_workflow_detail_rebuilds_brief_summary_for_legacy_runs(self) -> None:
        with temporary_database():
            database.persist_run_started(
                "run-rebuilt",
                {
                    "project_name": "详情页自动生成",
                    "brand_name": "VEJA",
                    "product_name": "Volley",
                    "workflow_mode": "smart_recommend",
                    "product_brief": "用户 brief：法式复古、运动感。",
                },
                [
                    {
                        "name": "layout.xlsx",
                        "bucket": "brief",
                        "saved_path": "D:/tmp/layout.xlsx",
                        "extracted_text": "[Sheet] Brief\n商品名称 | VEJA Volley\n核心卖点 | 轻量通勤",
                    }
                ],
            )

            detail = database.get_workflow_detail("run-rebuilt")

        self.assertIsNotNone(detail)
        assert detail is not None
        self.assertEqual(detail["inputLayers"]["source"], "assets_rebuilt")
        self.assertIn("[用户 brief]", detail["inputLayers"]["brief_summary"])
        self.assertIn("商品名称 | VEJA Volley", detail["inputLayers"]["brief_summary"])
        self.assertEqual(detail["inputLayers"]["layout_reference"], "")
        self.assertEqual(detail["inputLayers"]["raw_wireframe_dump"], "")


if __name__ == "__main__":
    unittest.main()
