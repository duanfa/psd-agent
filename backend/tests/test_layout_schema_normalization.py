import unittest

from backend.app.models import normalize_layout_schema_payload, validate_layout_schema_payload


class LayoutSchemaNormalizationTests(unittest.TestCase):
    def test_normalize_layout_schema_maps_hero_aliases(self) -> None:
        payload = {
            "schema_version": "brandos_layout_schema.v1",
            "canvas": {"width": 790, "height_mode": "auto"},
            "sections": [
                {
                    "id": "content_intro",
                    "name": "卖点说明",
                    "role": "feature_highlight",
                    "component_type": "grid_module",
                    "order": 1,
                    "x": 0,
                    "y": 0,
                    "w": 790,
                    "h": 240,
                },
                {
                    "id": "main_image_area",
                    "name": "主图展示区",
                    "component_type": "image_carousel",
                    "order": 2,
                    "x": 0,
                    "y": 240,
                    "w": 790,
                    "h": 320,
                },
            ],
            "image_slots": [
                {
                    "id": "hero_slot",
                    "section_id": "main_image_area",
                    "role": "primary_view",
                    "asset_type": "image",
                    "x": 0,
                    "y": 0,
                    "w": 790,
                    "h": 320,
                    "required": True,
                }
            ],
        }

        normalized = normalize_layout_schema_payload(payload)

        hero_section = next(
            section for section in normalized["sections"] if section["id"] == "main_image_area"
        )
        self.assertEqual(hero_section["role"], "hero")

    def test_validate_layout_schema_allows_header_before_hero(self) -> None:
        payload = {
            "schema_version": "brandos_layout_schema.v1",
            "canvas": {"width": 790, "height_mode": "auto"},
            "sections": [
                {
                    "id": "header_nav",
                    "name": "顶部导航",
                    "role": "navigation",
                    "component_type": "navbar",
                    "order": 1,
                    "x": 0,
                    "y": 0,
                    "w": 790,
                    "h": 60,
                    "required_image_slots": [],
                    "required_text_fields": ["logo"],
                },
                {
                    "id": "main_image_area",
                    "name": "主图展示区",
                    "role": "product_display",
                    "component_type": "image_carousel",
                    "order": 2,
                    "x": 0,
                    "y": 60,
                    "w": 790,
                    "h": 320,
                    "required_image_slots": ["hero_slot"],
                    "required_text_fields": [],
                },
                {
                    "id": "selling_points",
                    "name": "卖点区",
                    "role": "feature_highlight",
                    "component_type": "grid_module",
                    "order": 3,
                    "x": 0,
                    "y": 380,
                    "w": 790,
                    "h": 240,
                    "required_image_slots": ["feature_slot"],
                    "required_text_fields": ["headline"],
                },
            ],
            "image_slots": [
                {
                    "id": "hero_slot",
                    "section_id": "main_image_area",
                    "role": "primary_view",
                    "asset_type": "image",
                    "x": 0,
                    "y": 0,
                    "w": 790,
                    "h": 320,
                    "required": True,
                },
                {
                    "id": "feature_slot",
                    "section_id": "selling_points",
                    "role": "detail",
                    "asset_type": "image",
                    "x": 0,
                    "y": 0,
                    "w": 300,
                    "h": 240,
                    "required": True,
                },
            ],
            "text_layers": [],
        }

        report = validate_layout_schema_payload(
            payload,
            require_explicit_training_fields=True,
        )

        self.assertEqual(report["status"], "passed")
        hero_section = next(
            section
            for section in report["normalized_schema"]["sections"]
            if section["id"] == "main_image_area"
        )
        self.assertEqual(hero_section["role"], "hero")

    def test_normalize_layout_schema_preserves_zero_order(self) -> None:
        payload = {
            "schema_version": "brandos_layout_schema.v1",
            "canvas": {"width": 790, "height_mode": "auto"},
            "sections": [
                {
                    "id": "header_nav",
                    "name": "顶部导航",
                    "role": "navigation",
                    "component_type": "navbar",
                    "order": 0,
                    "x": 0,
                    "y": 0,
                    "w": 790,
                    "h": 60,
                },
                {
                    "id": "main_image_area",
                    "name": "主图展示区",
                    "role": "product_display",
                    "component_type": "image_carousel",
                    "order": 1,
                    "x": 0,
                    "y": 60,
                    "w": 790,
                    "h": 320,
                },
            ],
            "image_slots": [
                {
                    "id": "hero_slot",
                    "section_id": "main_image_area",
                    "role": "primary_view",
                    "asset_type": "image",
                    "x": 0,
                    "y": 0,
                    "w": 790,
                    "h": 320,
                    "required": True,
                }
            ],
        }

        normalized = normalize_layout_schema_payload(payload)

        self.assertEqual(normalized["sections"][0]["id"], "header_nav")
        self.assertEqual(normalized["sections"][0]["order"], 0)
        self.assertEqual(normalized["sections"][1]["id"], "main_image_area")
        self.assertEqual(normalized["sections"][1]["order"], 1)


if __name__ == "__main__":
    unittest.main()
