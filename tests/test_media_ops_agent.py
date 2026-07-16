import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from scripts import media_ops_agent


class MediaOpsAgentTests(unittest.TestCase):
    def test_classifies_ai_and_tech_leader_topics(self):
        self.assertEqual(media_ops_agent.classify_topic("Sam Altman explains GPT agents"), "ai_agent")
        self.assertEqual(media_ops_agent.classify_topic("Jensen Huang NVIDIA GPU keynote"), "semiconductor")

    def test_external_item_scoring_prefers_view_rich_items(self):
        low = media_ops_agent.score_external_item({"source_type": "youtube_tw", "view_count": 100})
        high = media_ops_agent.score_external_item({"source_type": "youtube_tw", "view_count": 1_000_000})
        self.assertGreater(high, low)

    def test_collect_external_trends_includes_tiktok_viral_videos(self):
        from web.routes import news

        tiktok_item = {
            "title": "viral stitch format",
            "summary": "TikTok high-view candidate: 2,000,000 views",
            "url": "https://www.tiktok.com/@demo/video/123",
            "source": "TikTok viral video",
            "source_type": "tiktok_viral",
            "view_count": 2_000_000,
            "rights_status": "external_reference_only",
        }

        with patch.object(news, "_fetch_youtube_trending", return_value=[]), \
             patch.object(news, "_fetch_google_trends_tw", return_value=[]), \
             patch.object(news, "_fetch_tiktok_tw", return_value=[]), \
             patch.object(news, "_fetch_last30days", return_value=[]), \
             patch.object(news, "_fetch_tiktok_viral", return_value=[tiktok_item]) as fetch_viral, \
             patch("scripts.shorts_trend_calibrator.fetch_google_news", return_value=[]):
            items = media_ops_agent.collect_external_trends(limit_per_source=3)

        fetch_viral.assert_called_once()
        self.assertTrue(any(item.get("source_type") == "tiktok_viral" for item in items))

    def test_strategy_weights_combine_internal_and_external_signals(self):
        internal = {
            "baseline_views": 100,
            "by_topic": [
                {"key": "tech_leader", "avg_views": 220},
                {"key": "entertainment_kpop", "avg_views": 30},
            ],
        }
        external = {
            "topics": [
                {"key": "tech_leader", "avg_score": 80},
                {"key": "ai_model", "avg_score": 70},
            ]
        }
        result = media_ops_agent.build_strategy_weights(internal, external)
        self.assertGreater(result["strategy_weights"]["figure_tech"], result["strategy_weights"]["entertainment"])
        self.assertEqual(result["recommended_mix"][0]["strategy"], "figure_tech")
        self.assertIn("direction", result)
        self.assertEqual(result["direction"]["lane_keywords"]["figure_tech"], "Sam Altman Jensen Huang")
        self.assertIn("creative_directives", result)
        self.assertEqual(result["creative_directives"]["figure_tech"]["editing_style"], "quote_context_breakdown")

    def test_strategy_weights_prefer_mature_topic_metrics(self):
        internal = {
            "baseline_views": 100,
            "mature_baseline_views": 100,
            "by_topic": [
                {"key": "semiconductor", "avg_views": 20},
                {"key": "entertainment_kpop", "avg_views": 220},
            ],
            "mature_by_topic": [
                {"key": "semiconductor", "avg_views": 220},
                {"key": "entertainment_kpop", "avg_views": 20},
            ],
        }
        result = media_ops_agent.build_strategy_weights(internal, {"topics": []})
        self.assertGreater(result["topic_weights"]["semiconductor"], 1.0)
        self.assertLess(result["topic_weights"]["entertainment_kpop"], 1.0)
        self.assertGreater(result["strategy_weights"]["figure_tech"], result["strategy_weights"]["entertainment"])

    def test_creative_directives_react_to_weak_strategy_and_style_signals(self):
        result = media_ops_agent.build_creative_directives(
            {
                "baseline_views": 100,
                "by_strategy": [{"key": "tech", "videos": 3, "avg_views": 40}],
            },
            {"style_signals": [{"key": "ai_visuals"}, {"key": "large_captions"}]},
            {"topic_weights": {"ai_model": 1.4}},
        )
        tech = result["tech"]
        self.assertEqual(tech["risk_mode"], "aggressive_hook_test")
        self.assertEqual(tech["image2_scene_count"], 3)
        self.assertEqual(tech["subtitle_scale"], "large")
        self.assertIn("new_content_type_backlog", result)

    def test_lane_actions_pause_repeated_weak_non_core_lane(self):
        actions = media_ops_agent.build_lane_actions(
            {
                "baseline_views": 100,
                "by_strategy": [
                    {"key": "tech_judgement", "videos": 6, "avg_views": 35, "best_views": 60},
                    {"key": "tech", "videos": 6, "avg_views": 130, "best_views": 240},
                ],
            },
            {"tech_judgement": 0.7, "tech": 1.2},
        )
        self.assertEqual(actions["tech_judgement"]["action"], "pause")
        self.assertEqual(actions["tech_judgement"]["daily_quota"], 0)
        self.assertEqual(actions["tech"]["action"], "boost")

    def test_lane_actions_keep_core_lane_as_experiment_when_weak(self):
        actions = media_ops_agent.build_lane_actions(
            {
                "baseline_views": 100,
                "by_strategy": [{"key": "figure_tech", "videos": 6, "avg_views": 35, "best_views": 60}],
            },
            {"figure_tech": 0.7},
        )
        self.assertEqual(actions["figure_tech"]["action"], "experiment")
        self.assertEqual(actions["figure_tech"]["cadence_days"], 2)

    def test_platform_actions_pause_repeated_zero_reach_platforms(self):
        actions = media_ops_agent.build_platform_actions({
            "by_strategy_platform": [
                {"key": "tech_judgement:tiktok", "videos": 4, "avg_views": 0, "best_views": 0},
                {"key": "tech:x", "videos": 4, "avg_views": 1, "best_views": 2},
                {"key": "tech:facebook", "videos": 4, "avg_views": 220, "best_views": 260},
            ]
        })
        self.assertEqual(actions["tech_judgement"]["tiktok"]["action"], "pause")
        self.assertEqual(actions["tech"]["x"]["action"], "pause")
        self.assertEqual(actions["tech"]["facebook"]["action"], "keep")

    def test_internal_summary_exposes_mature_strategy_metrics(self):
        old = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
        fresh = datetime.now(timezone.utc).isoformat()
        result = media_ops_agent.summarize_internal([
            {"job_id": 1, "strategy": "tech", "total_views": 100, "engagements": 0, "finished_at": old, "platform_stats": []},
            {"job_id": 2, "strategy": "tech", "total_views": 0, "engagements": 0, "finished_at": fresh, "platform_stats": []},
        ])
        self.assertEqual(result["mature_video_count"], 1)
        self.assertEqual(result["mature_baseline_views"], 100)
        self.assertEqual(result["mature_by_strategy"][0]["avg_views"], 100)

    def test_mature_row_waits_for_latest_platform_schedule(self):
        finished = (datetime.now(timezone.utc) - timedelta(hours=60)).isoformat()
        recent_schedule = (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat()
        old_schedule = (datetime.now(timezone.utc) - timedelta(hours=30)).isoformat()
        self.assertFalse(media_ops_agent._is_mature_row({
            "finished_at": finished,
            "latest_scheduled_at": recent_schedule,
        }))
        self.assertTrue(media_ops_agent._is_mature_row({
            "finished_at": finished,
            "latest_scheduled_at": old_schedule,
        }))

    def test_latest_scheduled_at_ignores_linkedin_and_uses_timezone(self):
        latest = media_ops_agent.latest_scheduled_at([
            {"platform": "youtube", "scheduled_date": "2026-05-26T14:00:00", "timezone": "Asia/Taipei"},
            {"platform": "linkedin", "scheduled_date": "2026-05-27T14:00:00", "timezone": "Asia/Taipei"},
            {"platform": "instagram", "scheduled_date": "2026-05-26T15:00:00", "timezone": "Asia/Taipei"},
        ])
        self.assertEqual(latest, "2026-05-26T07:00:00+00:00")

    def test_cluster_weights_reward_account_winners_and_demote_losers(self):
        result = media_ops_agent.build_cluster_weights({
            "mature_baseline_views": 100,
            "mature_by_cluster": [
                {"key": "semiconductor:nvidia", "videos": 3, "avg_views": 180},
                {"key": "ai_model:openai", "videos": 3, "avg_views": 40},
                {"key": "ai_model:google", "videos": 1, "avg_views": 500},
            ],
        })
        self.assertGreater(result["semiconductor:nvidia"], 1.0)
        self.assertLess(result["ai_model:openai"], 1.0)
        self.assertNotIn("ai_model:google", result)

    def test_source_weights_reward_reliable_sources_and_demote_losers(self):
        result = media_ops_agent.build_source_weights({
            "mature_baseline_views": 100,
            "mature_by_source_key": [
                {"key": "ithome", "videos": 4, "avg_views": 160},
                {"key": "weak-source", "videos": 3, "avg_views": 40},
                {"key": "single-winner", "videos": 1, "avg_views": 500},
            ],
        })
        self.assertGreater(result["ithome"], 1.0)
        self.assertLess(result["weak-source"], 1.0)
        self.assertNotIn("single-winner", result)

    def test_internal_summary_groups_platform_performance(self):
        result = media_ops_agent.summarize_internal([
            {
                "job_id": 1,
                "strategy": "tech_judgement",
                "topic_class": "ai_tool",
                "source_key": "ithome",
                "total_views": 20,
                "engagements": 2,
                "stats_rows": 2,
                "platform_stats": [
                    {"platform": "youtube", "views": 10, "likes": 1, "comments": 0, "shares": 0},
                    {"platform": "tiktok", "views": 30, "likes": 3, "comments": 1, "shares": 1},
                ],
                "experiment_meta": {"hook_pattern": "contradiction"},
            }
        ])
        by_platform = {row["key"]: row for row in result["by_platform"]}
        by_strategy_platform = {row["key"]: row for row in result["by_strategy_platform"]}
        self.assertEqual(by_platform["tiktok"]["views"], 30)
        self.assertEqual(by_strategy_platform["tech_judgement:tiktok"]["avg_views"], 30)
        self.assertEqual(result["by_source_key"][0]["key"], "ithome")

    def test_daily_briefing_markdown_explains_platforms_and_reasons(self):
        brief = {
            "date": "2026-05-21",
            "jobs": [{
                "job_id": 196,
                "strategy": "tech_judgement",
                "title": "Google升級Flow",
                "status": "done",
                "decision_reason": "Media Ops focus=ai_tool; style=doro_judgement_editorial",
                "platforms": [
                    {"platform": "youtube", "status": "uploaded", "scheduled_date": "2026-05-22T14:00:00"},
                    {"platform": "tiktok", "status": "uploaded", "scheduled_date": "2026-05-22T07:00:00"},
                ],
            }],
            "platform_summary": [{"platform": "tiktok", "uploaded": 1, "scheduled": 1, "views": 0}],
            "decisions": [{"title": "tech_judgement", "reason": "TikTok復健測試", "action": "keep"}],
            "guardrails": ["科技新聞暫不發 TikTok"],
        }
        text = media_ops_agent.render_daily_briefing_markdown(brief)
        self.assertIn("Job #196", text)
        self.assertIn("tiktok:uploaded", text)
        self.assertIn("TikTok復健測試", text)
        self.assertIn("科技新聞暫不發 TikTok", text)

    def test_direction_plan_keeps_lane_keywords_separate(self):
        result = media_ops_agent.build_direction_plan(
            {"tech": 1.0, "entertainment": 1.5},
            {"entertainment_kpop": 2.0, "ai_agent": 1.3},
            {"topics": [{"key": "entertainment_kpop", "label": "K-pop", "score": 90}]},
        )
        self.assertEqual(result["lane_keywords"]["entertainment"], "Kpop")
        self.assertEqual(result["lane_keywords"]["tech"], "AI agent")


if __name__ == "__main__":
    unittest.main()
