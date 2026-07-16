import json
import tempfile
import unittest
from pathlib import Path

from web.render_templates import load_render_template_spec


class RenderTemplatesTest(unittest.TestCase):
    def test_defaults_include_news_and_figure_safe_positions(self):
        spec = load_render_template_spec()

        self.assertEqual(spec["canvas"]["width"], 1080)
        self.assertGreaterEqual(spec["safe_zone"]["top"], 100)
        self.assertEqual(spec["news"]["subtitle_bottom"], 340)
        self.assertEqual(spec["figure"]["video_y"], 340)

    def test_override_deep_merges(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "spec.json"
            path.write_text(json.dumps({"news": {"subtitle_bottom": 380}}), encoding="utf-8")

            spec = load_render_template_spec(path)

            self.assertEqual(spec["news"]["subtitle_bottom"], 380)
            self.assertEqual(spec["news"]["opening_label"], "先看這個重點")


if __name__ == "__main__":
    unittest.main()
