import unittest
from unittest.mock import patch

from scripts import tiktok_viral_fetcher as fetcher


class TikTokViralFetcherTests(unittest.TestCase):
    def test_extract_video_rows_from_nested_creative_center_data(self):
        data = {
            "props": {
                "pageProps": {
                    "dehydratedState": {
                        "queries": [
                            {"state": {"data": {"noise": [{"title": "not a video"}]}}},
                            {
                                "state": {
                                    "data": {
                                        "pages": [
                                            {
                                                "list": [
                                                    {
                                                        "item_id": "v1",
                                                        "author": {"nickname": "creator one"},
                                                        "desc": "first hook",
                                                        "play_count": "1200000",
                                                        "digg_count": "140000",
                                                        "share_count": "9000",
                                                        "comment_count": "2000",
                                                        "cover": "https://example.test/v1.jpg",
                                                    },
                                                    {
                                                        "video_id": "v2",
                                                        "nickname": "creator two",
                                                        "title": "second hook",
                                                        "view_count": 300000,
                                                    },
                                                ]
                                            }
                                        ]
                                    }
                                }
                            },
                        ]
                    }
                }
            }
        }

        rows = fetcher.extract_video_rows(data)

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["item_id"], "v1")
        self.assertEqual(rows[1]["video_id"], "v2")

    def test_rank_videos_marks_metadata_only_rights_and_sorts_by_views(self):
        rows = [
            {"item_id": "low", "desc": "small trend", "play_count": 99_000, "author": {"nickname": "low creator"}},
            {"item_id": "high", "desc": "big trend", "play_count": "2500000", "digg_count": "310000", "comment_count": "12000", "share_count": "44000", "author": {"nickname": "high creator"}},
        ]

        items = fetcher.rank_videos(rows, limit=5, min_views=100_000, region="TW", period="7")

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["tiktok_video_id"], "high")
        self.assertEqual(items[0]["view_count"], 2_500_000)
        self.assertEqual(items[0]["rights_status"], "external_reference_only")
        self.assertEqual(items[0]["reuse_policy"], "metadata_only_no_reupload")
        self.assertEqual(items[0]["source_type"], "tiktok_viral")
        self.assertIn("TikTok viral video", items[0]["source"])
        self.assertGreater(items[0]["media_ops_virality_score"], 0)

    def test_collect_viral_videos_uses_injected_html_fetcher(self):
        payload = {
            "props": {
                "pageProps": {
                    "data": {
                        "videoList": [
                            {"id": "abc", "title": "viral demo", "views": 400000, "likes": 50000, "creator": "demo"}
                        ]
                    }
                }
            }
        }
        html = '<html><script id="__NEXT_DATA__" type="application/json">' + fetcher.json_dumps(payload) + "</script></html>"

        items = fetcher.collect_viral_videos(
            region="TW",
            period="7",
            limit=3,
            min_views=100000,
            fetch_html=lambda _url: html,
        )

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "viral demo")
        self.assertEqual(items[0]["view_count"], 400000)

    def test_collect_viral_videos_tolerates_modern_shell_without_rows(self):
        payload = {
            "loaderData": {
                "layout": {"deviceType": "pc"},
                "creativeCenter/layout": {"dehydratedState": {"queries": []}},
            }
        }
        html = (
            '<html><script type="application/json" id="__MODERN_ROUTER_DATA__">'
            + fetcher.json_dumps(payload)
            + "</script></html>"
        )

        items = fetcher.collect_viral_videos(
            region="TW",
            period="7",
            limit=3,
            min_views=100000,
            fetch_html=lambda _url: html,
        )

        self.assertEqual(items, [])

    def test_collect_viral_videos_falls_back_to_high_view_hashtag_topics(self):
        shell_html = '<html><script type="application/json" id="__MODERN_ROUTER_DATA__">{"loaderData":{}}</script></html>'
        hashtag_payload = {
            "loaderData": {
                "creativeCenter/trends/(tab)/page": {
                    "dehydratedState": {
                        "queries": [
                            {
                                "queryKey": ["popular", "hashtags", {"period": 7, "countryCode": "TW"}],
                                "state": {
                                    "data": {
                                        "pages": [
                                            {
                                                "data": [
                                                    {
                                                        "hashtagID": "h1",
                                                        "hashtagName": "demoTrend",
                                                        "vv": "2500000",
                                                        "publishCnt": "40000",
                                                        "topCreators": [
                                                            {"handleName": "creator_one"},
                                                            {"nickname": "creator two"},
                                                        ],
                                                    }
                                                ]
                                            }
                                        ]
                                    }
                                },
                            }
                        ]
                    }
                }
            }
        }
        hashtag_html = (
            '<html><script type="application/json" id="__MODERN_ROUTER_DATA__">'
            + fetcher.json_dumps(hashtag_payload)
            + "</script></html>"
        )

        def fake_fetch(url):
            if "trends/hashtag" in url:
                return hashtag_html
            return shell_html

        items = fetcher.collect_viral_videos(
            region="TW",
            period="7",
            limit=3,
            min_views=100000,
            fetch_html=fake_fetch,
        )

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["source_type"], "tiktok_viral_topic")
        self.assertEqual(items[0]["tiktok_hashtag"], "demoTrend")
        self.assertEqual(items[0]["view_count"], 2_500_000)
        self.assertEqual(items[0]["reuse_policy"], "metadata_only_no_reupload")

    def test_news_route_fetch_all_includes_tiktok_viral_source(self):
        from web.routes import news

        candidate = {
            "title": "viral candidate",
            "url": "https://www.tiktok.com/@demo/video/123",
            "source": "TikTok viral video",
            "source_type": "tiktok_viral",
            "view_count": 1_000_000,
        }

        with patch("scripts.tiktok_viral_fetcher.collect_viral_videos", return_value=[candidate]) as collect:
            items = news._fetch_all("", "zh-TW", ["tiktok_viral"], limit_per=3)

        collect.assert_called_once()
        self.assertEqual(items, [candidate])
