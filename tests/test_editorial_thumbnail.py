import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from scripts import editorial_thumbnail


class EditorialThumbnailTest(unittest.TestCase):
    def test_tech_and_entertainment_use_editorial_cover(self):
        self.assertTrue(editorial_thumbnail.should_use_editorial_cover({"strategy": "tech"}))
        self.assertTrue(editorial_thumbnail.should_use_editorial_cover({"strategy": "entertainment"}))
        self.assertTrue(editorial_thumbnail.should_use_editorial_cover({"strategy": "tech_judgement"}))
        self.assertFalse(editorial_thumbnail.should_use_editorial_cover({"content_type": "figure_quote"}))

    def test_image_prompt_asks_for_visual_without_text_or_logos(self):
        prompt = editorial_thumbnail.build_image_prompt(
            {"strategy": "tech"},
            {"title": "AI Studio生App", "summary": "Google讓使用者用自然語言建立App"},
        )

        self.assertIn("vertical 9:16", prompt)
        self.assertIn("no readable text", prompt)
        self.assertIn("no logos", prompt)
        self.assertIn("AI Studio", prompt)

    def test_palette_is_not_purple_for_supported_strategies(self):
        for strategy in ("tech", "entertainment", "tech_judgement"):
            palette = editorial_thumbnail.palette_for_strategy(strategy)
            joined = " ".join(palette.values()).lower()
            self.assertNotIn("#4a148c", joined)
            self.assertNotIn("#880e4f", joined)

    def test_image2_cover_generation_prefers_vertical_size_then_falls_back(self):
        calls = []

        def fake_generate(_prompt, output, size, timeout):
            calls.append(size)
            if size == "1024x1792":
                raise RuntimeError("unsupported")
            Path(output).write_bytes(b"ok")
            return Path(output)

        with TemporaryDirectory() as td:
            out = Path(td) / "cover.png"
            with patch("web.claude_client.generate_image", side_effect=fake_generate):
                generated = editorial_thumbnail._generate_image2("prompt", out)

        self.assertEqual(generated, out)
        self.assertEqual(calls[:2], ["1024x1792", "1024x1536"])


if __name__ == "__main__":
    unittest.main()
