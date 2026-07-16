import unittest
from datetime import datetime, timedelta, timezone

from scripts import analytics_fetcher


class AnalyticsFetcherSmartTests(unittest.TestCase):
    def test_due_platform_missing_stats_needs_refresh(self):
        now = datetime(2026, 5, 26, 8, 0, tzinfo=timezone.utc)
        ctx = {
            "job_id": 1,
            "finished_at": now - timedelta(days=1),
            "scheduled": {
                "youtube": now - timedelta(minutes=30),
                "instagram": now + timedelta(hours=1),
            },
            "request_ids": {
                "youtube": "yt-req",
                "instagram": "ig-req",
            },
        }
        stale_before = now - timedelta(hours=6)

        self.assertEqual(
            analytics_fetcher._platforms_needing_refresh(ctx, [], now=now, stale_before=stale_before),
            ["youtube"],
        )

    def test_due_platform_fresh_stats_does_not_need_refresh(self):
        now = datetime(2026, 5, 26, 8, 0, tzinfo=timezone.utc)
        ctx = {
            "job_id": 1,
            "finished_at": now - timedelta(days=1),
            "scheduled": {"youtube": now - timedelta(minutes=30)},
            "request_ids": {"youtube": "yt-req"},
        }
        stale_before = now - timedelta(hours=6)
        stats = [{"platform": "youtube", "fetched_at": (now - timedelta(minutes=5)).isoformat()}]

        self.assertEqual(
            analytics_fetcher._platforms_needing_refresh(ctx, stats, now=now, stale_before=stale_before),
            [],
        )

    def test_future_platform_is_not_due(self):
        now = datetime(2026, 5, 26, 8, 0, tzinfo=timezone.utc)
        ctx = {
            "job_id": 1,
            "finished_at": now - timedelta(days=1),
            "scheduled": {"youtube": now + timedelta(minutes=30)},
            "request_ids": {"youtube": "yt-req"},
        }

        self.assertFalse(analytics_fetcher._platform_due(ctx, "youtube", now=now))

    def test_old_missing_platform_does_not_trigger_endless_catchup(self):
        now = datetime(2026, 5, 26, 8, 0, tzinfo=timezone.utc)
        ctx = {
            "job_id": 1,
            "finished_at": now - timedelta(days=3),
            "scheduled": {"youtube": now - timedelta(hours=36)},
            "request_ids": {"youtube": "yt-req", "linkedin": "li-req"},
        }
        stale_before = now - timedelta(hours=6)

        self.assertEqual(
            analytics_fetcher._platforms_needing_refresh(ctx, [], now=now, stale_before=stale_before),
            [],
        )


if __name__ == "__main__":
    unittest.main()
