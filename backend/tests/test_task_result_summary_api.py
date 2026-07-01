import tempfile
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from backend.app import database


@contextmanager
def temporary_database():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "task-result-summary.db"
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


def _seed_brand_and_pages() -> None:
    with database.session_scope() as session:
        assert session is not None
        session.add(database.Brand(name="VEJA", status="已初始化"))
        database._set_setting(
            session,
            "dashboard_page",
            {
                "title": "工作台",
                "subtitle": "查看最近设计任务",
                "currentBrandName": "VEJA",
                "quickActions": [],
            },
        )
        database._set_setting(
            session,
            "design_tasks_page",
            {"title": "设计任务", "subtitle": "查看设计任务列表"},
        )


def _persist_completed_run(
    run_id: str,
    *,
    product_name: str,
    design_spec: dict,
    artifact_paths: dict,
    status: str = "completed",
    summary: str = "结果已生成",
    brand_name: str = "VEJA",
    task_type: str = "商品详情页",
    task_code: str | None = None,
    created_at: datetime | None = None,
) -> None:
    database.persist_run_started(
        run_id,
        {
            "project_name": "详情页自动生成",
            "brand_name": brand_name,
            "product_name": product_name,
            "workflow_mode": "smart_recommend",
        },
        [],
    )
    database.persist_run_completed(
        run_id,
        status,
        summary,
        False,
        "",
        design_spec,
        artifact_paths,
        output_dir=f"/tmp/{run_id}",
        warnings=[],
    )
    with database.session_scope() as session:
        assert session is not None
        run = session.get(database.WorkflowRun, run_id)
        assert run is not None
        run.task_code = task_code or run_id
        run.task_type = task_type
        if created_at is not None:
            run.created_at = created_at


class TaskResultSummaryApiTests(unittest.TestCase):
    def test_design_tasks_page_embeds_lightweight_result_summary(self) -> None:
        with temporary_database():
            _seed_brand_and_pages()
            _persist_completed_run(
                "run-design-spec",
                product_name="Volley",
                summary="设计规格已生成",
                design_spec={
                    "result_state": {
                        "tier": "低保真草稿",
                        "tier_code": "low_fidelity_draft",
                        "delivery_status": "review_only",
                        "fallback_used": True,
                        "layout_schema_hit": True,
                        "layout_validation_status": "passed",
                        "asset_guard_status": "warning",
                        "image_slot_count": 3,
                        "error_code": "export_preflight_review_only",
                        "reason_codes": ["copy_contract_failed"],
                        "warning_codes": ["image_generation_retried_before_passing"],
                        "reasons": ["文案 contract 未通过"],
                        "warnings": ["图片阶段先重试后通过"],
                        "critical_stages": {
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
                        "critical_checks": {
                            "layout_guard": {"status": "passed", "error_code": ""},
                            "asset_guard": {"status": "warning", "error_code": "asset_guard_warning"},
                            "export_preflight": {
                                "status": "warning",
                                "error_code": "export_preflight_review_only",
                            },
                        },
                        "export_preflight": {
                            "status": "warning",
                            "decision": "review_only",
                            "error_code": "export_preflight_review_only",
                            "reason_codes": ["copy_contract_failed"],
                            "warning_codes": ["image_generation_retried_before_passing"],
                            "checks": {
                                "layout_validation": {"status": "passed", "guard_can_execute": True},
                                "asset_guard": {"status": "warning", "can_export": True},
                                "stage_contracts": {
                                    "image_generation": {
                                        "stage_id": "image_generation",
                                        "execution_status": "completed",
                                        "contract_status": "passed",
                                        "warning_codes": ["image_generation_retried_before_passing"],
                                        "warnings": ["图片阶段先重试后通过"],
                                    },
                                    "copy": {
                                        "stage_id": "copy",
                                        "execution_status": "fallback",
                                        "contract_status": "failed",
                                        "reason_codes": ["copy_contract_failed"],
                                        "reasons": ["文案 contract 未通过"],
                                    },
                                },
                            },
                        },
                    },
                    "export_review": {
                        "status": "review_only",
                        "message": "当前结果仅建议作为审稿包。",
                        "error_code": "export_preflight_review_only",
                        "reason_codes": ["copy_contract_failed"],
                        "critical_stages": {
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
                            }
                        },
                        "critical_checks": {
                            "export_preflight": {
                                "status": "warning",
                                "error_code": "export_preflight_review_only",
                            }
                        },
                    },
                },
                artifact_paths={
                    "preview_svg": "preview.svg",
                    "design_spec": "design_spec.json",
                    "photoshop_jsx": "create.jsx",
                    "readme": "README.md",
                },
            )

            page = database.get_design_tasks_page_data()

        self.assertIsNotNone(page)
        assert page is not None
        task = next(item for item in page["tasks"] if item["runId"] == "run-design-spec")
        self.assertEqual(task["summary"], "设计规格已生成")
        self.assertEqual(task["resultSummary"]["resultState"]["delivery_status"], "review_only")
        self.assertTrue(task["resultSummary"]["resultState"]["layout_schema_hit"])
        self.assertEqual(task["resultSummary"]["resultState"]["image_slot_count"], 3)
        self.assertTrue(task["resultSummary"]["resultState"]["fallback_used"])
        self.assertEqual(task["resultSummary"]["resultState"]["error_code"], "export_preflight_review_only")
        self.assertEqual(
            task["resultSummary"]["resultState"]["critical_stages"]["copy"]["error_code"],
            "copy_schema_contract_failed",
        )
        self.assertEqual(
            task["resultSummary"]["resultState"]["critical_stages"]["copy"]["retry"]["error_code"],
            "copy_retry_exhausted",
        )
        self.assertEqual(task["resultSummary"]["exportPreflight"]["decision"], "review_only")
        self.assertEqual(
            task["resultSummary"]["exportPreflight"]["checks"]["stage_contracts"]["copy"][
                "reason_codes"
            ],
            ["copy_contract_failed"],
        )
        self.assertEqual(task["resultSummary"]["exportReview"]["status"], "review_only")
        self.assertEqual(
            task["resultSummary"]["exportReview"]["critical_checks"]["export_preflight"]["error_code"],
            "export_preflight_review_only",
        )

    def test_dashboard_and_design_tasks_fall_back_to_artifact_summary(self) -> None:
        with temporary_database():
            _seed_brand_and_pages()
            _persist_completed_run(
                "run-artifact-fallback",
                product_name="Volley Artifact",
                design_spec={},
                artifact_paths={
                    "preview_svg": "preview.svg",
                    "design_spec": "design_spec.json",
                    "photoshop_jsx": "create.jsx",
                    "readme": "README.md",
                    "result_tier": "可交付",
                    "tier_code": "ready_for_delivery",
                    "delivery_status": "ready",
                    "error_code": "",
                    "reason_codes": [],
                    "warning_codes": [],
                    "export_preflight": {
                        "status": "passed",
                        "decision": "ready",
                        "checks": {
                            "layout_validation": {"status": "passed", "guard_can_execute": True},
                            "asset_guard": {"status": "passed", "can_export": True},
                        },
                    },
                    "export_review": {"status": "ready", "message": "可直接交付"},
                },
            )

            design_tasks_page = database.get_design_tasks_page_data()
            dashboard = database.get_dashboard_data()

        self.assertIsNotNone(design_tasks_page)
        self.assertIsNotNone(dashboard)
        assert design_tasks_page is not None
        assert dashboard is not None

        design_task = next(
            item for item in design_tasks_page["tasks"] if item["runId"] == "run-artifact-fallback"
        )
        dashboard_task = next(
            item for item in dashboard["designTasks"] if item["runId"] == "run-artifact-fallback"
        )

        self.assertEqual(design_task["resultSummary"]["resultState"]["tier"], "可交付")
        self.assertEqual(design_task["resultSummary"]["resultState"]["delivery_status"], "ready")
        self.assertEqual(design_task["resultSummary"]["exportPreflight"]["status"], "passed")
        self.assertEqual(dashboard_task["brand"], "VEJA")
        self.assertEqual(dashboard_task["taskType"], "商品详情页")
        self.assertEqual(dashboard_task["resultSummary"]["exportReview"]["status"], "ready")

    def test_design_tasks_page_filters_and_paginates_with_result_summary(self) -> None:
        with temporary_database():
            _seed_brand_and_pages()
            with database.session_scope() as session:
                assert session is not None
                session.add(database.Brand(name="ACME", status="已初始化"))

            base_time = datetime(2026, 1, 1, 12, 0, 0)
            ready_design_spec = {
                "result_state": {
                    "tier": "可交付",
                    "delivery_status": "ready",
                    "image_slot_count": 2,
                },
                "export_review": {"status": "ready", "message": "可直接交付"},
            }
            default_artifacts = {
                "preview_svg": "preview.svg",
                "design_spec": "design_spec.json",
                "photoshop_jsx": "create.jsx",
                "readme": "README.md",
            }
            _persist_completed_run(
                "run-veja-ready",
                product_name="Volley Ready",
                design_spec=ready_design_spec,
                artifact_paths=default_artifacts,
                brand_name="VEJA",
                task_type="商品详情页",
                task_code="TASK-VEJA-READY",
                created_at=base_time + timedelta(minutes=1),
            )
            _persist_completed_run(
                "run-veja-review",
                product_name="Campo Review",
                design_spec={},
                artifact_paths=default_artifacts,
                status="fallback_completed",
                brand_name="VEJA",
                task_type="海报",
                task_code="TASK-VEJA-REVIEW",
                created_at=base_time + timedelta(minutes=2),
            )
            _persist_completed_run(
                "run-acme-failed",
                product_name="Acme Poster",
                design_spec={},
                artifact_paths=default_artifacts,
                status="failed",
                brand_name="ACME",
                task_type="海报",
                task_code="TASK-ACME-FAILED",
                created_at=base_time + timedelta(minutes=3),
            )
            database.persist_run_started(
                "run-veja-running",
                {
                    "project_name": "详情页自动生成",
                    "brand_name": "VEJA",
                    "product_name": "Volley Running",
                    "workflow_mode": "smart_recommend",
                },
                [],
            )
            with database.session_scope() as session:
                assert session is not None
                running_run = session.get(database.WorkflowRun, "run-veja-running")
                assert running_run is not None
                running_run.task_code = "TASK-VEJA-RUNNING"
                running_run.task_type = "商品详情页"
                running_run.created_at = base_time + timedelta(minutes=4)

            first_page = database.get_design_tasks_page_data(
                brand="VEJA",
                task_type="商品详情页",
                search="volley",
                limit=1,
                offset=0,
            )
            second_page = database.get_design_tasks_page_data(
                brand="VEJA",
                task_type="商品详情页",
                search="volley",
                limit=1,
                offset=1,
            )
            failed_page = database.get_design_tasks_page_data(
                status="failed",
                task_type="海报",
                search="acme",
                limit=10,
                offset=0,
            )

        assert first_page is not None
        assert second_page is not None
        assert failed_page is not None

        self.assertEqual(first_page["filters"]["brand"], "VEJA")
        self.assertEqual(first_page["filters"]["taskType"], "商品详情页")
        self.assertEqual(first_page["metrics"], {"total": 2, "running": 1, "success": 1, "failed": 0})
        self.assertEqual(first_page["pagination"]["limit"], 1)
        self.assertEqual(first_page["pagination"]["offset"], 0)
        self.assertEqual(first_page["pagination"]["total"], 2)
        self.assertTrue(first_page["pagination"]["hasMore"])
        self.assertEqual(first_page["tasks"][0]["runId"], "run-veja-running")

        self.assertEqual(second_page["pagination"]["offset"], 1)
        self.assertFalse(second_page["pagination"]["hasMore"])
        self.assertEqual(second_page["tasks"][0]["runId"], "run-veja-ready")
        self.assertEqual(second_page["tasks"][0]["resultSummary"]["resultState"]["tier"], "可交付")
        self.assertEqual(second_page["tasks"][0]["resultSummary"]["exportReview"]["status"], "ready")

        self.assertEqual(failed_page["metrics"], {"total": 1, "running": 0, "success": 0, "failed": 1})
        self.assertEqual([item["runId"] for item in failed_page["tasks"]], ["run-acme-failed"])
        self.assertIn("ACME", failed_page["brands"])
        self.assertIn("海报", failed_page["taskTypes"])
        self.assertIn("failed", failed_page["statuses"])


if __name__ == "__main__":
    unittest.main()
