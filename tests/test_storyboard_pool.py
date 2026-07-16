import tempfile
import unittest
import json
from pathlib import Path

from scripts import seedance_storyboard_renderer
from scripts import entertainment_storyboard_agent
from web import db


class StoryboardPoolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_db_path = db.DB_PATH
        db.DB_PATH = Path(self.tmp.name) / "dashboard.db"
        db.init_db()

    def tearDown(self):
        db.DB_PATH = self.old_db_path
        self.tmp.cleanup()

    def test_create_list_and_update_movie_language_candidate(self):
        candidate = {
            "title": "奶烙出任務：不要被罐罐誘惑",
            "hook": "不是貓在演電影，是用電影鏡頭語法拍貓貓日常災難。",
            "synopsis": "未來貓警告過去貓不要被罐罐誘惑。",
            "reference_title": "Interstellar",
            "reference_scene": "future observer warns the past",
            "shot_language": "alternate future observer and reaction shots",
            "adaptation_rule": "future cat watches past cat take the can and get carried to bath time",
            "media_ops_score": 72,
            "estimated_seconds": 12,
            "estimated_cost_usd": 1.2,
        }
        frames = [
            {
                "frame_index": 1,
                "shot_code": "A1",
                "title": "誘惑出現",
                "visual_prompt": "one vertical 9:16 frame, no grid, no text",
                "seedance_prompt": "animate can temptation",
                "sound_prompt": "can rolls",
                "duration_seconds": 4,
                "trim_seconds": 2.0,
            },
            {
                "frame_index": 2,
                "shot_code": "B1",
                "title": "未來警告",
                "visual_prompt": "future cat warns from window",
                "seedance_prompt": "animate warning",
                "sound_prompt": "paw taps glass",
                "duration_seconds": 4,
                "trim_seconds": 1.8,
            },
        ]

        candidate_id = db.create_storyboard_candidate(candidate, frames)
        item = db.get_storyboard_candidate(candidate_id)

        self.assertEqual(item["target_profile"], "entertainment_yt")
        self.assertEqual(item["reference_title"], "Interstellar")
        self.assertEqual(item["status"], "draft")
        self.assertEqual(len(item["frames"]), 2)
        self.assertEqual(item["frames"][0]["shot_code"], "A1")
        self.assertEqual(item["frames"][0]["trim_seconds"], 2.0)

        db.update_storyboard_candidate(
            candidate_id,
            status="video_ready",
            output_video_path="storyboards/test/output.mp4",
            video_status="ready",
        )
        db.update_storyboard_frame(
            item["frames"][0]["id"],
            image_path="storyboards/test/frame_01.jpg",
            video_path="storyboards/test/segment_01.mp4",
            status="image2_frame",
            video_status="ready",
        )

        listed = db.list_storyboard_candidates()
        self.assertEqual(listed[0]["status"], "video_ready")
        self.assertEqual(listed[0]["output_video_path"], "storyboards/test/output.mp4")
        self.assertEqual(listed[0]["frames"][0]["video_status"], "ready")

        self.assertTrue(db.delete_storyboard_candidate(candidate_id))
        self.assertIsNone(db.get_storyboard_candidate(candidate_id))
        self.assertEqual(db.list_storyboard_candidates(), [])
        self.assertFalse(db.delete_storyboard_candidate(candidate_id))

    def test_build_candidate_creates_frame_first_movie_language_prompts(self):
        trend = {
            "title": "cat can temptation meme",
            "summary": "pet meme short",
            "source": "local",
            "url": "https://example.test/trend",
            "score": 61,
        }

        candidate, frames = entertainment_storyboard_agent.build_candidate(trend, 1, "entertainment_yt")

        self.assertEqual(candidate["lane"], "entertainment_storyboard")
        self.assertEqual(candidate["target_profile"], "entertainment_yt")
        self.assertEqual(candidate["reference_title"], "Interstellar")
        self.assertIn("電影鏡頭語法", candidate["hook"])
        self.assertEqual(len(frames), 6)
        self.assertTrue(all(frame["visual_prompt"] for frame in frames))
        self.assertTrue(all(frame["seedance_prompt"] for frame in frames))
        self.assertTrue(all(frame["sound_prompt"] for frame in frames))
        self.assertTrue(all("No grid" in frame["visual_prompt"] for frame in frames))
        self.assertTrue(all("No music" in frame["seedance_prompt"] for frame in frames))

    def test_seedance_pair_mode_renders_two_frames_per_segment(self):
        pipeline_dir = Path(self.tmp.name) / "pipeline"
        image_dir = pipeline_dir / "storyboards" / "test"
        image_dir.mkdir(parents=True)
        frames = []
        for idx in range(1, 7):
            image = image_dir / f"frame_{idx:02d}.jpg"
            image.write_bytes(b"fake image")
            frames.append(
                {
                    "frame_index": idx,
                    "shot_code": f"S{idx}",
                    "title": f"shot {idx}",
                    "visual_prompt": f"visual {idx}",
                    "seedance_prompt": f"animate shot {idx}",
                    "duration_seconds": 4,
                    "trim_seconds": 4,
                    "image_path": str(image.relative_to(pipeline_dir)).replace("\\", "/"),
                    "status": "image2_frame",
                }
            )

        candidate_id = db.create_storyboard_candidate(
            {
                "title": "Milu pair mode",
                "status": "images_ready",
                "agent_reason": json.dumps({"seedance_pair_mode": True}, ensure_ascii=False),
                "estimated_seconds": 12,
            },
            frames,
        )

        old_pipeline_dir = seedance_storyboard_renderer.PIPELINE_DIR
        old_submit = seedance_storyboard_renderer.submit_seedance_task
        old_poll = seedance_storyboard_renderer.poll_seedance_task
        old_download = seedance_storyboard_renderer.download_file
        old_normalize = seedance_storyboard_renderer.normalize_segment
        old_concat = seedance_storyboard_renderer.concat_segments
        calls = []

        def fake_submit(frame_path, prompt, duration=4, resolution="720p", last_frame_path=None):
            calls.append((frame_path.name, last_frame_path.name if last_frame_path else None, prompt))
            return f"task-{len(calls)}"

        def fake_download(_url, output):
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(b"raw video")

        def fake_normalize(_input, output):
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(b"segment")

        def fake_concat(paths, output):
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(("|".join(path.name for path in paths)).encode("utf-8"))

        try:
            seedance_storyboard_renderer.PIPELINE_DIR = pipeline_dir
            seedance_storyboard_renderer.submit_seedance_task = fake_submit
            seedance_storyboard_renderer.poll_seedance_task = lambda _task_id: "https://example.test/video.mp4"
            seedance_storyboard_renderer.download_file = fake_download
            seedance_storyboard_renderer.normalize_segment = fake_normalize
            seedance_storyboard_renderer.concat_segments = fake_concat

            output = seedance_storyboard_renderer.render_candidate(candidate_id)
        finally:
            seedance_storyboard_renderer.PIPELINE_DIR = old_pipeline_dir
            seedance_storyboard_renderer.submit_seedance_task = old_submit
            seedance_storyboard_renderer.poll_seedance_task = old_poll
            seedance_storyboard_renderer.download_file = old_download
            seedance_storyboard_renderer.normalize_segment = old_normalize
            seedance_storyboard_renderer.concat_segments = old_concat

        self.assertEqual(
            calls,
            [
                ("frame_01.jpg", "frame_02.jpg", "animate shot 1"),
                ("frame_03.jpg", "frame_04.jpg", "animate shot 3"),
                ("frame_05.jpg", "frame_06.jpg", "animate shot 5"),
            ],
        )
        self.assertEqual(output, image_dir / "output.mp4")
        item = db.get_storyboard_candidate(candidate_id)
        self.assertEqual(item["status"], "video_ready")
        self.assertEqual(item["output_video_path"], "storyboards/test/output.mp4")
        first, second, third, fourth, fifth, sixth = item["frames"]
        self.assertEqual(first["video_path"], "storyboards/test/segments/segment-01-S1-to-S2.mp4")
        self.assertEqual(second["video_status"], "paired_with_previous")
        self.assertEqual(third["video_path"], "storyboards/test/segments/segment-02-S3-to-S4.mp4")
        self.assertEqual(fourth["video_status"], "paired_with_previous")
        self.assertEqual(fifth["video_path"], "storyboards/test/segments/segment-03-S5-to-S6.mp4")
        self.assertEqual(sixth["video_status"], "paired_with_previous")


if __name__ == "__main__":
    unittest.main()
