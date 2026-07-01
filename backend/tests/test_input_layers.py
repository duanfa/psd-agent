import unittest

from backend.app.input_layers import (
    build_asset_input_layers,
    build_input_layers,
    render_input_prompt,
    semantic_brief_text,
)
from backend.app.models import UploadedAsset


def _sample_wireframe_spec() -> dict:
    return {
        "schema_version": "wireframe_spec.v1",
        "source_file": "layout.xlsx",
        "media_count": 1,
        "drawing_object_count": 1,
        "sheets": [
            {
                "name": "详情页",
                "dimensions": {"rows": 24, "cols": 6, "width_px": 790, "height_px": 1800},
                "merged_ranges": ["A1:F4"],
                "column_widths_px": [120, 120, 120],
                "row_heights_px": [80, 80, 80],
                "cells": [
                    {
                        "address": "A1",
                        "row": 1,
                        "col": 1,
                        "text": "首屏主视觉",
                        "box": {"x": 0, "y": 0, "w": 790, "h": 320},
                        "style": {"bold": True},
                    }
                ],
                "drawing_path": "xl/drawings/drawing1.xml",
                "objects": [
                    {
                        "type": "image",
                        "name": "hero_image",
                        "text": "",
                        "cell_anchor": {"from": {"row": 1, "col": 1}, "to": {"row": 4, "col": 6}},
                        "box": {"x": 0, "y": 0, "w": 790, "h": 320},
                        "media_path": "xl/media/image1.png",
                        "relationship_id": "rId1",
                    }
                ],
            }
        ],
    }


class InputLayersTests(unittest.TestCase):
    def test_build_asset_input_layers_separates_summary_and_wireframe(self) -> None:
        extracted_text = "\n".join(
            [
                "[Sheet] Brief",
                "商品名称 | VEJA Volley",
                "核心卖点 | 轻量通勤 | 防滑鞋底",
                "[WireframeSpec]",
                "- cell A1 box=0,0,790,320 text=首屏主视觉",
            ]
        )

        layers = build_asset_input_layers(
            "layout.xlsx",
            extracted_text,
            {"wireframe_spec": _sample_wireframe_spec()},
        )

        self.assertIn("[来源文件] layout.xlsx", layers["brief_summary"])
        self.assertIn("商品名称 | VEJA Volley", layers["brief_summary"])
        self.assertNotIn("[WireframeSpec]", layers["brief_summary"])
        self.assertIn("[WireframeSpec]", layers["layout_reference"])
        self.assertIn('"schema_version":"wireframe_spec.v1"', layers["raw_wireframe_dump"])

    def test_build_input_layers_keeps_user_brief_and_excel_summary_layered(self) -> None:
        asset = UploadedAsset(
            name="layout.xlsx",
            bucket="brief",
            extracted_text="[Sheet] Brief\n商品名称 | VEJA Volley\n核心卖点 | 轻量通勤",
            metadata={"input_layers": {"brief_summary": "[来源文件] layout.xlsx\n商品名称 | VEJA Volley"}},
        )

        layers = build_input_layers("用户 brief：法式复古、运动感。", [asset])

        self.assertIn("[用户 brief]", layers["brief_summary"])
        self.assertIn("法式复古、运动感", layers["brief_summary"])
        self.assertIn("[来源文件] layout.xlsx", layers["brief_summary"])
        self.assertEqual(semantic_brief_text(layers), layers["brief_summary"])

    def test_render_input_prompt_default_excludes_raw_wireframe_dump(self) -> None:
        asset = UploadedAsset(
            name="layout.xlsx",
            bucket="brief",
            extracted_text="[Sheet] Brief\n核心卖点 | 轻量通勤",
            metadata={
                "wireframe_spec": _sample_wireframe_spec(),
            },
        )
        layers = build_input_layers("用户 brief：复古运动。", [asset])

        prompt = render_input_prompt(layers)

        self.assertIn("brief_summary：", prompt)
        self.assertNotIn("layout_reference：", prompt)
        self.assertNotIn("raw_wireframe_dump", prompt)
        self.assertNotIn('"schema_version":"wireframe_spec.v1"', prompt)

    def test_render_input_prompt_layout_stage_includes_layout_reference_only(self) -> None:
        asset = UploadedAsset(
            name="layout.xlsx",
            bucket="brief",
            extracted_text="[Sheet] Brief\n核心卖点 | 轻量通勤",
            metadata={
                "wireframe_spec": _sample_wireframe_spec(),
            },
        )
        layers = build_input_layers("用户 brief：复古运动。", [asset])

        prompt = render_input_prompt(layers, include_layout_reference=True)

        self.assertIn("brief_summary：", prompt)
        self.assertIn("layout_reference：", prompt)
        self.assertNotIn("raw_wireframe_dump", prompt)


if __name__ == "__main__":
    unittest.main()
