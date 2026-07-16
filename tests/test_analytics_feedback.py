import tempfile
import unittest
import json
from pathlib import Path

from web import analytics_feedback


class AnalyticsFeedbackTest(unittest.TestCase):
    def test_write_feedback_groups_experiment_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "feedback.json"
            feedback = analytics_feedback.write_feedback(
                [
                    {
                        "job_id": 1,
                        "total_views": 120,
                        "experiment_meta": {
                            "strategy": "tech",
                            "hook_pattern": "specific_number",
                            "layout_mode": "article_rotate",
                            "thumbnail_style": "custom",
                            "thumbnail_source": "image2",
                            "media_ops_cluster": "semiconductor:nvidia",
                            "media_ops_source_key": "ithome",
                        },
                    },
                    {
                        "job_id": 2,
                        "total_views": 40,
                        "experiment_meta": {
                            "strategy": "tech",
                            "hook_pattern": "curiosity_gap",
                            "layout_mode": "article_rotate",
                            "thumbnail_style": "custom",
                            "thumbnail_source": "fallback",
                            "media_ops_cluster": "ai_tool:google",
                            "media_ops_source_key": "tvbs",
                        },
                    },
                ],
                output_path=out,
            )

            self.assertTrue(out.exists())
            self.assertEqual(feedback["groups"]["strategy:tech"]["videos"], 2)
            self.assertEqual(feedback["groups"]["strategy:tech"]["avg_views"], 80)
            self.assertEqual(feedback["groups"]["hook_pattern:specific_number"]["best_job_id"], 1)
            self.assertEqual(feedback["groups"]["cluster:semiconductor:nvidia"]["avg_views"], 120)
            self.assertEqual(feedback["groups"]["source:ithome"]["avg_views"], 120)
            self.assertEqual(feedback["groups"]["thumbnail_source:image2"]["avg_views"], 120)

    def test_experiment_meta_records_thumbnail_source(self):
        with tempfile.TemporaryDirectory() as td:
            old_pipeline = analytics_feedback.PIPELINE_DIR
            analytics_feedback.PIPELINE_DIR = Path(td)
            try:
                job_dir = Path(td) / "2026-05-19" / "job_1"
                (job_dir / "assets").mkdir(parents=True)
                (job_dir / "news.json").write_text(
                    json.dumps({"strategy": "tech", "items": [{"hook": "AI", "title": "AI news"}]}, ensure_ascii=False),
                    encoding="utf-8",
                )
                (job_dir / "thumbnail.png").write_bytes(b"thumb")
                (job_dir / "assets" / "cover_image2.png").write_bytes(b"image2")

                meta = analytics_feedback.experiment_meta_for_job("2026-05-19", 1)

                self.assertEqual(meta["thumbnail_style"], "custom")
                self.assertEqual(meta["thumbnail_source"], "image2")
                self.assertTrue(meta["youtube_custom_cover"])
                self.assertTrue(meta["instagram_custom_cover"])
            finally:
                analytics_feedback.PIPELINE_DIR = old_pipeline

    def test_experiment_meta_tolerates_null_trend_rules(self):
        with tempfile.TemporaryDirectory() as td:
            old_pipeline = analytics_feedback.PIPELINE_DIR
            analytics_feedback.PIPELINE_DIR = Path(td)
            try:
                job_dir = Path(td) / "2026-05-19" / "job_1"
                job_dir.mkdir(parents=True)
                (job_dir / "news.json").write_text(
                    json.dumps({
                        "strategy": "tech",
                        "shorts_trend_profile": {"rules": None},
                        "items": [{"hook": "3件AI大事"}],
                    }, ensure_ascii=False),
                    encoding="utf-8",
                )

                meta = analytics_feedback.experiment_meta_for_job("2026-05-19", 1)

                self.assertEqual(meta["strategy"], "tech")
                self.assertEqual(meta["hook"], "3件AI大事")
                self.assertEqual(meta["visual_change_seconds"], "")
            finally:
                analytics_feedback.PIPELINE_DIR = old_pipeline


if __name__ == "__main__":
    unittest.main()
