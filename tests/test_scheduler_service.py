import unittest
from unittest.mock import patch

from web import scheduler_service


class SchedulerServiceTests(unittest.TestCase):
    def test_autopilot_excludes_linkedin_and_tiktok_from_all_lanes(self):
        platforms = ["youtube", "instagram", "facebook", "threads", "x", "linkedin", "tiktok"]
        with patch.object(scheduler_service.media_ops_strategy, "load_weights", return_value={}):
            with patch.object(scheduler_service.media_ops_strategy, "filter_platforms", side_effect=lambda _s, p, _w: p):
                self.assertEqual(
                    scheduler_service._platforms_for_lane(platforms, "tech"),
                    ["youtube", "instagram", "facebook", "threads", "x"],
                )
                self.assertEqual(
                    scheduler_service._platforms_for_lane(platforms, "entertainment"),
                    ["youtube", "instagram", "facebook", "threads", "x"],
                )
                self.assertEqual(
                    scheduler_service._platforms_for_lane(platforms, "figure_tech"),
                    ["youtube", "instagram", "facebook", "threads", "x"],
                )

    def test_news_quota_does_not_duplicate_existing_daily_jobs(self):
        def counts(_today, triggered_by):
            return {"autopilot_news": 1, "autopilot_news_boost": 1}.get(triggered_by, 0)

        with patch.object(scheduler_service, "_lane_count", side_effect=counts):
            with patch.object(scheduler_service.media_ops_strategy, "load_weights", return_value={"lane_actions": {"tech": {"daily_quota": 2}}}):
                with patch.object(scheduler_service, "_fire_news_autopilot") as fire:
                    scheduler_service._fire_news_autopilot_with_quota("2026-05-26", ["youtube"], False, "tech")

        fire.assert_not_called()

    def test_tech_judgement_duplicate_skips_before_fetching_candidates(self):
        with patch.object(scheduler_service, "_lane_already_created", return_value=True):
            with patch.object(scheduler_service, "_pick_news_items") as pick:
                scheduler_service._fire_tech_judgement_autopilot("2026-05-26", ["youtube"], False)

        pick.assert_not_called()

    def test_business_finance_autopilot_creates_job_with_business_strategy(self):
        items = [{"title": "AI 訂閱制", "hook": "商業模式才是重點", "url": "https://example.com"}]
        with patch.object(scheduler_service, "_lane_already_created", return_value=False):
            with patch.object(scheduler_service, "get_setting", side_effect=lambda key, default="": {
                "autopilot_business_finance_profile": "business",
                "autopilot_business_finance_sources": "google,bing",
                "autopilot_business_finance_keywords": "AI business model,科技財經",
            }.get(key, default)):
                with patch.object(scheduler_service, "create_job", return_value=123) as create_job:
                    with patch.object(scheduler_service.job_runner, "trigger_job") as trigger_job:
                        with patch("scripts.business_finance_collector.collect_candidates", return_value=items):
                            scheduler_service._fire_business_finance_autopilot("2026-05-26", ["youtube", "facebook"], False)

        create_job.assert_called_once_with(
            date="2026-05-26",
            triggered_by="autopilot_business_finance",
            platforms="youtube,facebook",
        )
        trigger_job.assert_called_once()
        kwargs = trigger_job.call_args.kwargs
        self.assertEqual(kwargs["job_id"], 123)
        self.assertEqual(kwargs["strategy"], "business_finance")
        self.assertEqual(kwargs["account_profile"], "business")
        self.assertEqual(kwargs["pre_news"], items)


if __name__ == "__main__":
    unittest.main()
