import json
import unittest
from unittest.mock import patch

from web import claude_client


class ClaudeClientMetadataTests(unittest.TestCase):
    def test_enrich_news_preserves_media_ops_candidate_metadata(self):
        raw = [{
            "title": "Nvidia source headline",
            "summary": "raw summary",
            "url": "https://example.com/story",
            "source": "Example News",
            "source_type": "google_news",
            "view_count": 12345,
            "media_ops_score": 58.2,
            "media_ops_cluster": "semiconductor:nvidia",
            "media_ops_source_key": "example",
        }]
        enriched = [{
            "hook": "別只看晶片",
            "title": "AI 算力新戰場",
            "summary": "rewritten summary",
            "script": "這次重點不是單一新品。",
            "script_short": "這次重點不是單一新品。",
            "script_long": "這次重點不是單一新品，而是供應鏈節奏。",
            "source_url": "https://example.com/story",
            "source_name": "Example News",
        }]

        with patch.object(claude_client, "call_claude", return_value=(json.dumps(enriched), {})) as call:
            items = claude_client.enrich_news_items(raw, topic="AI", strategy="tech")

        prompt = call.call_args.args[0]
        self.assertIn("Media Ops signals are upstream performance clues", prompt)
        self.assertIn("score=58.2", prompt)
        self.assertIn("cluster=semiconductor:nvidia", prompt)
        self.assertEqual(items[0]["title"], "AI 算力新戰場")
        self.assertEqual(items[0]["media_ops_score"], 58.2)
        self.assertEqual(items[0]["media_ops_cluster"], "semiconductor:nvidia")
        self.assertEqual(items[0]["media_ops_source_key"], "example")
        self.assertEqual(items[0]["source_type"], "google_news")
        self.assertEqual(items[0]["view_count"], 12345)
        self.assertEqual(items[0]["raw_title"], "Nvidia source headline")
        self.assertEqual(items[0]["raw_url"], "https://example.com/story")

    def test_tech_judgement_preserves_metadata_for_selected_source(self):
        raw = [{
            "title": "Google Flow update",
            "summary": "raw summary",
            "url": "https://example.com/flow",
            "source": "iThome",
            "media_ops_score": 51.0,
            "media_ops_cluster": "ai_tool:google",
        }]
        enriched = [{
            "hook": "AI 影片門檻變了",
            "title": "Gemini 影片 AI 模擬世界",
            "script_short": "先別只看模型，這次關鍵是影片工作流。",
            "script": "先別只看模型，這次關鍵是影片工作流。",
            "source_url": "https://example.com/flow",
            "source_name": "iThome",
        }]

        with patch.object(claude_client, "call_claude", return_value=(json.dumps(enriched), {})) as call:
            items = claude_client.enrich_news_items(raw, topic="AI", strategy="tech_judgement")

        prompt = call.call_args.args[0]
        self.assertIn("Media Ops signals are upstream performance clues", prompt)
        self.assertIn("score=51.0", prompt)
        self.assertIn("cluster=ai_tool:google", prompt)
        self.assertEqual(items[0]["media_ops_score"], 51.0)
        self.assertEqual(items[0]["media_ops_cluster"], "ai_tool:google")
        self.assertNotIn("script_long", items[0])


if __name__ == "__main__":
    unittest.main()
