import json
import tempfile
import unittest
from pathlib import Path

from scripts import shorts_trend_calibrator
from scripts.shorts_trend_calibrator import apply_profile_to_news


class ShortsTrendCalibratorTest(unittest.TestCase):
    def test_applies_profile_hooks_and_render_fields(self):
        profile = {
            "date": "2026-05-19",
            "generated_at": "2026-05-19T00:00:00+00:00",
            "evidence": [{"title": "retention"}],
            "rules": {
                "opening_label": "先看這個重點",
                "subtitle_bottom": 340,
                "visual_change_seconds": 1.8,
                "hook_max_chars": 11,
            },
        }
        payload = {
            "items": [
                {
                    "hook": "別再亂用 AI",
                    "hook_variants": ["別再亂用 AI", "AI 怎麼教科學？"],
                    "title": "Gemini教師認證",
                    "bullets": ["教師增能", "專屬認證", "AI備課"],
                    "script_short": "Gemini 研習不是上手而已。",
                    "script_long": "Gemini 研習不是上手而已，還衝認證。",
                },
                {
                    "hook": "原來不只記憶體",
                    "title": "威剛押AI機器人",
                    "bullets": ["機器人", "AI入口", "硬體布局"],
                    "script_short": "威剛不只秀硬體。",
                },
                {
                    "hook": "AI怎麼教科學？",
                    "title": "成大AI論壇登場",
                    "bullets": ["科學教育", "研究創新", "實驗加速"],
                    "script_short": "成大 AI 論壇問一件事。",
                },
            ]
        }
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "news.json"
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            old = shorts_trend_calibrator.MEDIA_OPS_WEIGHTS_FILE
            shorts_trend_calibrator.MEDIA_OPS_WEIGHTS_FILE = Path(td) / "missing_weights.json"
            try:
                updated = apply_profile_to_news(path, profile)
            finally:
                shorts_trend_calibrator.MEDIA_OPS_WEIGHTS_FILE = old

        first = updated["items"][0]
        self.assertEqual(first["hook"], "3件AI大事")
        self.assertEqual(first["opening_label"], "先看這個重點")
        self.assertEqual(first["subtitle_bottom"], 340)
        self.assertEqual(first["visual_change_seconds"], 1.8)
        self.assertTrue(first["script_short"].startswith("先別滑走，"))
        self.assertIn("shorts_trend_profile", updated)

    def test_applies_media_ops_creative_directive(self):
        profile = {
            "date": "2026-05-21",
            "generated_at": "2026-05-21T00:00:00+00:00",
            "evidence": [],
            "rules": {"opening_label": "old", "subtitle_bottom": 340, "visual_change_seconds": 1.8, "hook_max_chars": 12},
        }
        payload = {
            "strategy": "tech_judgement",
            "items": [{"title": "AI治理能力變新聞檻", "hook": "AI治理", "script_short": "這次更新影響企業導入AI。"}],
        }
        weights = {
            "creative_directives": {
                "tech_judgement": {
                    "editing_style": "doro_judgement_editorial",
                    "opening_label": "發生什麼",
                    "hook_patterns": ["why_it_matters"],
                    "subtitle_bottom": 305,
                    "visual_change_seconds": 1.4,
                    "emotion": "curiosity",
                    "scene_type": "robot",
                    "layout_mode": "image2_editorial",
                    "thumbnail_brief": "image2 cover brief",
                }
            }
        }
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            path = td_path / "news.json"
            directive_path = td_path / "weights.json"
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            directive_path.write_text(json.dumps(weights, ensure_ascii=False), encoding="utf-8")
            old = shorts_trend_calibrator.MEDIA_OPS_WEIGHTS_FILE
            shorts_trend_calibrator.MEDIA_OPS_WEIGHTS_FILE = directive_path
            try:
                updated = apply_profile_to_news(path, profile)
            finally:
                shorts_trend_calibrator.MEDIA_OPS_WEIGHTS_FILE = old

        first = updated["items"][0]
        self.assertEqual(updated["layout_mode"], "image2_editorial")
        self.assertEqual(first["opening_label"], "發生什麼")
        self.assertEqual(first["subtitle_bottom"], 305)
        self.assertEqual(first["visual_change_seconds"], 1.4)
        self.assertEqual(first["emotion"], "curiosity")
        self.assertEqual(first["scene_type"], "robot")
        self.assertEqual(first["media_ops_editing_style"], "doro_judgement_editorial")
        self.assertEqual(first["thumbnail_brief"], "image2 cover brief")


if __name__ == "__main__":
    unittest.main()
