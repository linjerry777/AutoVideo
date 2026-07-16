import unittest

from web import content_strategy
from web.claude_client import _STRATEGY_PRESETS
from web.routes import jobs
from web.routes import schedule
from scripts import publisher


class BusinessFinanceStrategyTest(unittest.TestCase):
    def test_business_finance_is_registered_across_pipeline_maps(self):
        self.assertIn("business_finance", _STRATEGY_PRESETS)
        self.assertEqual(content_strategy.strategy_label("business_finance"), "商業判讀")
        self.assertEqual(jobs._STRATEGY_LABEL["business_finance"], "商業判讀")
        self.assertEqual(schedule._STRATEGY_LABEL["business_finance"], "商業判讀")
        self.assertTrue(jobs._IS_AIGC_BY_STRATEGY["business_finance"])
        self.assertEqual(jobs._STRATEGY_CTA_GROUP["business_finance"], "none")
        self.assertIn("商業模式", jobs._YOUTUBE_TAGS_BY_STRATEGY["business_finance"])
        self.assertIn("#商業判讀", jobs._HASHTAGS["instagram"]["business_finance"])
        self.assertIn("#商業判讀", publisher._HASHTAGS_BY_STRATEGY["business_finance"])

    def test_business_finance_metadata_contains_guardrail_disclaimer(self):
        meta = content_strategy.seed_platform_meta({
            "strategy": "business_finance",
            "items": [
                {
                    "hook": "這家公司真正賺錢的不是產品",
                    "title": "AI 訂閱制商業模式",
                    "summary": "拆解 AI 公司如何靠訂閱和企業合約變現。",
                    "script": "這不是投資建議，而是用商業模式看懂公司風險。",
                }
            ],
        })

        self.assertIn("商業判讀", meta["youtube"]["title"])
        self.assertIn("非投資建議", meta["youtube"]["description"])
        self.assertIn("非投資建議", meta["instagram"]["title"])
        self.assertEqual(meta["facebook"]["facebook_page_id"], "1100141579843223")
        self.assertTrue(meta["tiktok"]["is_aigc"])


if __name__ == "__main__":
    unittest.main()
