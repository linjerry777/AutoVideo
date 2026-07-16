import unittest

from web import content_strategy
from web.routes import jobs as job_routes


class ContentStrategyTest(unittest.TestCase):
    def test_figure_tech_platform_meta_uses_tech_account_rules(self):
        meta = content_strategy.seed_platform_meta({
            "strategy": "figure_tech",
            "items": [
                {
                    "hook": "黃仁勳一句話",
                    "title": "Jensen AI",
                    "summary": "AI 觀點",
                    "script": "黃仁勳說 AI 會改變工作方式。",
                }
            ],
        })

        self.assertEqual(meta["youtube"]["video_version"], "long")
        self.assertIn("科技大咖原片解析", meta["youtube"]["title"])
        self.assertIn("黃仁勳", meta["youtube"]["tags"])
        self.assertEqual(meta["facebook"]["facebook_page_id"], "1100141579843223")
        self.assertTrue(meta["tiktok"]["is_aigc"])

    def test_entertainment_is_not_aigc_and_uses_entertain_page(self):
        meta = content_strategy.seed_platform_meta({
            "strategy": "entertainment",
            "items": [{"hook": "熱搜爆了", "title": "娛樂新聞", "summary": "摘要"}],
        })

        self.assertFalse(meta["tiktok"]["is_aigc"])
        self.assertEqual(meta["facebook"]["facebook_page_id"], "1012830001921459")
        self.assertNotIn("留言", meta["instagram"]["title"])
        self.assertNotIn("完整版", meta["instagram"]["first_comment"])

    def test_pet_uses_nailao_facebook_page(self):
        meta = content_strategy.seed_platform_meta({
            "strategy": "pet",
            "items": [{"hook": "牠以為罐罐要來了", "title": "奶烙", "summary": "貓咪短片"}],
        })

        self.assertEqual(meta["facebook"]["facebook_page_id"], "1181556318367016")
        self.assertIn("_nailao1998", meta["instagram"]["title"])
        self.assertNotIn("今日娛樂", meta["instagram"]["title"])
        self.assertNotIn("三件事", meta["instagram"]["title"])

    def test_manychat_cta_is_opt_in_for_tech_only(self):
        news = {
            "strategy": "tech",
            "items": [{"hook": "AI 爆了", "title": "OpenAI 新工具", "summary": "摘要"}],
        }

        default_meta = content_strategy.seed_platform_meta(news)
        self.assertNotIn("留言", default_meta["instagram"]["title"])
        self.assertNotIn("留言", default_meta["instagram"]["first_comment"])

        def get_setting(key, default=""):
            return {
                "manychat_cta_enabled": "true",
                "manychat_cta_strategies": "tech,figure_tech",
            }.get(key, default)

        enabled_meta = content_strategy.seed_platform_meta(news, get_setting=get_setting)
        self.assertIn("留言", enabled_meta["instagram"]["title"])
        self.assertIn("留言", enabled_meta["instagram"]["first_comment"])
        self.assertIn("AI", enabled_meta["instagram"]["title"])
        self.assertIn("AI", enabled_meta["instagram"]["first_comment"])

        entertainment_meta = content_strategy.seed_platform_meta(
            {"strategy": "entertainment", "items": [{"hook": "熱搜爆了", "title": "娛樂新聞"}]},
            get_setting=get_setting,
        )
        self.assertNotIn("留言", entertainment_meta["instagram"]["title"])
        self.assertNotIn("留言", entertainment_meta["instagram"]["first_comment"])

    def test_media_ops_schedule_offset_flows_into_schedule_meta(self):
        meta = content_strategy.seed_platform_meta({
            "strategy": "tech",
            "items": [{"title": "AI news", "hook": "AI", "media_ops_schedule_offset_hours": 2}],
        })
        self.assertEqual(meta["_schedule"]["media_ops_offset_hours"], 2)

    def test_basic_metadata_uses_same_title_formula(self):
        meta = content_strategy.build_basic_metadata(
            [{"hook": "3件AI大事", "title": "Gemini", "summary": "摘要"}],
            strategy="tech",
        )

        self.assertIn("Gemini", meta["title"])
        self.assertIn("AI 大事一次看完", meta["title"])
        self.assertIn("Doro", meta["description"])

    def test_generic_hook_title_falls_back_to_source_angle(self):
        meta = content_strategy.seed_platform_meta({
            "strategy": "tech",
            "items": [
                {
                    "hook": "3件AI大事",
                    "raw_title": "黃仁勳示警台灣電力吃緊 - TVBS新聞網",
                    "title": "3件AI大事",
                    "summary": "NVIDIA 執行長提醒 AI 資料中心會讓用電需求上升。",
                }
            ],
        })

        self.assertIn("黃仁勳示警台灣電力吃緊", meta["youtube"]["title"])
        self.assertNotIn("3件AI大事", meta["youtube"]["title"])

    def test_tech_judgement_uses_short_upload_and_native_cover(self):
        meta = content_strategy.seed_platform_meta({
            "strategy": "tech_judgement",
            "items": [{"hook": "先別滑走", "title": "NVIDIA 台灣總部動土", "summary": "科技判讀"}],
        })

        self.assertEqual(meta["youtube"]["video_version"], "short")
        self.assertEqual(meta["x"]["video_version"], "short")
        self.assertFalse(meta["youtube"]["use_auto_thumbnail"])
        self.assertTrue(meta["instagram"]["use_auto_thumbnail"])

    def test_route_seed_platform_meta_delegates_to_shared_strategy(self):
        news = {
            "strategy": "tech",
            "items": [{"hook": "3件AI大事", "raw_title": "OpenAI 發表新代理功能 - iThome", "title": "3件AI大事"}],
        }

        self.assertEqual(
            job_routes._seed_platform_meta(news)["youtube"]["title"],
            content_strategy.seed_platform_meta(news)["youtube"]["title"],
        )


if __name__ == "__main__":
    unittest.main()
