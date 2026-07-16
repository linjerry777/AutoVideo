import unittest

from web import media_ops_strategy


class MediaOpsStrategyTests(unittest.TestCase):
    def test_preferred_keyword_is_lane_aware(self):
        weights = {
            "topic_weights": {
                "entertainment_kpop": 2.0,
                "ai_agent": 1.4,
            }
        }
        self.assertEqual(media_ops_strategy.preferred_keyword("AI", "tech", weights), "AI agent")
        self.assertEqual(media_ops_strategy.preferred_keyword("trend", "entertainment", weights), "Kpop")

    def test_candidate_keywords_explore_beyond_top_topic(self):
        weights = {
            "topic_weights": {"semiconductor": 1.2, "ai_model": 0.6, "ai_agent": 0.4},
            "direction": {"lane_focus_topics": {"tech": ["semiconductor", "ai_model", "ai_agent"]}},
        }
        keywords = media_ops_strategy.candidate_keywords("AI", "tech", weights, limit=3)
        self.assertIn("Nvidia", keywords)
        self.assertIn("AI tools", keywords)
        self.assertIn("GPT", keywords)

    def test_rank_candidates_prefers_matching_hot_topic(self):
        weights = {
            "strategy_weights": {"tech": 1.0},
            "topic_weights": {"ai_agent": 1.7, "entertainment_kpop": 2.0},
        }
        items = [
            {"title": "ITZY comeback MV", "source_type": "youtube_tw", "view_count": 5_000_000, "url": "a"},
            {"title": "OpenAI agent can now operate browser tasks", "source_type": "last30days", "view_count": 20_000, "url": "b"},
        ]
        ranked = media_ops_strategy.rank_candidates(items, "tech", weights)
        self.assertEqual(ranked[0]["media_ops_topic"], "ai_agent")
        self.assertIn("OpenAI", ranked[0]["title"])
        self.assertIn("media_ops_virality_score", ranked[0])

    def test_should_run_lane_respects_pause_and_experiment_cadence(self):
        weights = {
            "lane_actions": {
                "tech_judgement": {"action": "pause", "reason": "weak"},
                "entertainment": {"action": "experiment", "cadence_days": 2, "reason": "test"},
            }
        }
        allowed, reason = media_ops_strategy.should_run_lane("tech_judgement", weights, today="2026-05-26")
        self.assertFalse(allowed)
        self.assertEqual(reason, "weak")

        even_day = "2026-05-26"
        odd_day = "2026-05-27"
        first, _ = media_ops_strategy.should_run_lane("entertainment", weights, today=even_day)
        second, _ = media_ops_strategy.should_run_lane("entertainment", weights, today=odd_day)
        self.assertNotEqual(first, second)

    def test_virality_score_rewards_conflict_numbers_and_questions(self):
        strong = media_ops_strategy.virality_score({"title": "Why Nvidia's first AI chip ban could cost $5 billion?"})
        weak = media_ops_strategy.virality_score({"title": "Company announces weekly roundup and minor update"})
        self.assertGreater(strong, weak)

    def test_daily_quota_reads_lane_action(self):
        weights = {"lane_actions": {"tech": {"daily_quota": 2}}}
        self.assertEqual(media_ops_strategy.daily_quota("tech", weights), 2)

    def test_filter_platforms_removes_paused_platforms(self):
        weights = {
            "platform_actions": {
                "tech_judgement": {
                    "tiktok": {"action": "pause"},
                    "x": {"action": "experiment"},
                }
            }
        }
        self.assertEqual(
            media_ops_strategy.filter_platforms("tech_judgement", ["youtube", "tiktok", "x"], weights),
            ["youtube", "x"],
        )

    def test_candidate_gate_filters_low_quality_items(self):
        weights = {
            "strategy_weights": {"tech": 1.0},
            "topic_weights": {"ai_agent": 1.2},
            "lane_actions": {"tech": {"action": "keep"}},
        }
        items = [
            {"title": "OpenAI agent breakthrough: 5 things developers should know", "source_type": "last30days", "view_count": 50_000, "url": "good"},
            {"title": "Company minor update", "source_type": "google", "view_count": 0, "url": "bad"},
        ]
        filtered = media_ops_strategy.filter_candidates(items, "tech", weights)
        self.assertEqual([item["url"] for item in filtered], ["good"])

    def test_candidate_score_uses_account_cluster_weight(self):
        base_weights = {
            "strategy_weights": {"tech": 1.0},
            "topic_weights": {"semiconductor": 1.0},
        }
        item = {"title": "Nvidia breakthrough: 5 AI GPU warnings", "source_type": "last30days", "view_count": 50_000, "url": "nvidia"}
        base = media_ops_strategy.candidate_score(item, "tech", base_weights)
        boosted = media_ops_strategy.candidate_score(item, "tech", {**base_weights, "cluster_weights": {"semiconductor:nvidia": 1.4}})
        demoted = media_ops_strategy.candidate_score(item, "tech", {**base_weights, "cluster_weights": {"semiconductor:nvidia": 0.6}})
        self.assertGreater(boosted, base)
        self.assertLess(demoted, base)

    def test_candidate_score_uses_source_weight(self):
        base_weights = {
            "strategy_weights": {"tech": 1.0},
            "topic_weights": {"semiconductor": 1.0},
        }
        item = {"title": "Nvidia breakthrough: 5 AI GPU warnings", "source": "iThome", "view_count": 50_000, "url": "nvidia"}
        base = media_ops_strategy.candidate_score(item, "tech", base_weights)
        boosted = media_ops_strategy.candidate_score(item, "tech", {**base_weights, "source_weights": {"ithome": 1.25}})
        demoted = media_ops_strategy.candidate_score(item, "tech", {**base_weights, "source_weights": {"ithome": 0.75}})
        self.assertGreater(boosted, base)
        self.assertLess(demoted, base)

    def test_candidate_score_penalizes_offbrand_crypto_for_tech(self):
        weights = {
            "strategy_weights": {"tech": 1.0},
            "topic_weights": {"general": 1.0},
        }
        clean = {"title": "AI tool breakthrough: 5 things creators should know", "source_type": "last30days", "view_count": 50_000}
        offbrand = {"title": "Binance AI liquidity crisis and crypto market warning", "source_type": "last30days", "view_count": 50_000}
        self.assertLess(
            media_ops_strategy.candidate_score(offbrand, "tech", weights),
            media_ops_strategy.candidate_score(clean, "tech", weights),
        )

    def test_candidate_threshold_is_stricter_for_boost(self):
        keep = media_ops_strategy.candidate_threshold("tech", {"lane_actions": {"tech": {"action": "keep"}}})
        boost = media_ops_strategy.candidate_threshold("tech", {"lane_actions": {"tech": {"action": "boost"}}})
        self.assertGreater(boost, keep)

    def test_story_cluster_groups_same_entity(self):
        a = media_ops_strategy.story_cluster({"title": "Nvidia reveals new AI GPU"})
        b = media_ops_strategy.story_cluster({"title": "黃仁勳談輝達 AI 晶片"})
        self.assertEqual(a, b)
        self.assertEqual(a, "semiconductor:nvidia")

    def test_filter_candidates_skips_used_clusters(self):
        weights = {
            "strategy_weights": {"tech": 1.0},
            "topic_weights": {"semiconductor": 1.5, "ai_agent": 1.2},
            "lane_actions": {"tech": {"action": "keep"}},
        }
        items = [
            {"title": "Nvidia breakthrough: 5 AI GPU warnings", "source_type": "last30days", "view_count": 50_000, "url": "nvidia"},
            {"title": "OpenAI agent breakthrough: 5 things developers should know", "source_type": "last30days", "view_count": 50_000, "url": "openai"},
        ]
        filtered = media_ops_strategy.filter_candidates(items, "tech", weights, skip_clusters={"semiconductor:nvidia"})
        self.assertEqual([item["url"] for item in filtered], ["openai"])

    def test_select_diverse_candidates_prefers_unique_sources(self):
        weights = {
            "strategy_weights": {"tech": 1.0},
            "topic_weights": {"semiconductor": 1.5, "ai_agent": 1.2},
            "lane_actions": {"tech": {"action": "keep"}},
        }
        items = [
            {"title": "Nvidia warning: 5 AI GPU risks", "source": "A", "source_type": "last30days", "view_count": 50_000, "url": "a1"},
            {"title": "Nvidia warning: 5 AI GPU risks update", "source": "A", "source_type": "last30days", "view_count": 45_000, "url": "a2"},
            {"title": "Nvidia warning: 5 AI GPU risks explained", "source": "B", "source_type": "last30days", "view_count": 40_000, "url": "b1"},
        ]
        selected = media_ops_strategy.select_diverse_candidates(items, "tech", 2, weights)
        self.assertEqual({item["url"] for item in selected}, {"a1", "b1"})
        self.assertEqual(len({item["media_ops_source_key"] for item in selected}), 2)

    def test_select_diverse_candidates_limits_cluster_before_relaxing(self):
        weights = {
            "strategy_weights": {"tech": 1.0},
            "topic_weights": {"semiconductor": 1.5, "ai_agent": 1.2, "ai_model": 1.2},
            "lane_actions": {"tech": {"action": "keep"}},
        }
        items = [
            {"title": "Nvidia warning: 5 AI GPU risks", "source": "A", "source_type": "last30days", "view_count": 50_000, "url": "n1"},
            {"title": "Nvidia breakthrough: 5 AI GPU wins", "source": "B", "source_type": "last30days", "view_count": 50_000, "url": "n2"},
            {"title": "Nvidia crisis: 5 AI GPU costs", "source": "C", "source_type": "last30days", "view_count": 50_000, "url": "n3"},
            {"title": "OpenAI agent breakthrough: 5 things developers should know", "source": "D", "source_type": "last30days", "view_count": 50_000, "url": "o1"},
        ]
        selected = media_ops_strategy.select_diverse_candidates(items, "tech", 3, weights, max_per_cluster=2)
        self.assertEqual([item["url"] for item in selected], ["n1", "n2", "o1"])

    def test_select_diverse_candidates_can_escape_one_flooded_cluster(self):
        weights = {
            "strategy_weights": {"tech": 1.0},
            "topic_weights": {"semiconductor": 1.0, "ai_tool": 1.0},
            "lane_actions": {"tech": {"action": "keep"}},
        }
        items = [
            {"title": f"Nvidia AI GPU warning {i}", "source": f"source-{i}", "source_type": "last30days", "view_count": 50_000, "url": f"n{i}"}
            for i in range(8)
        ] + [
            {"title": "AI tools breakthrough for creators", "source": "tool-source", "source_type": "last30days", "view_count": 50_000, "url": "tool"}
        ]
        selected = media_ops_strategy.select_diverse_candidates(items, "tech", 3, weights, max_per_cluster=2)
        self.assertTrue(any(str(item["media_ops_cluster"]).startswith("ai_tool:") for item in selected))


if __name__ == "__main__":
    unittest.main()
