import unittest

from scripts import figure_segment_quality


class FigureSegmentQualityTest(unittest.TestCase):
    def test_scores_complete_segment_higher_than_thin_segment(self):
        good = {
            "figure_name": "Jensen Huang",
            "start_seconds": 20,
            "end_seconds": 50,
            "hook": "AI別只看效率",
            "quote_zh": "黃仁勳說，AI 不是取代人，而是讓懂工具的人跑得更快。",
            "script_short": "黃仁勳這句話的重點，不是 AI 會不會搶工作，而是誰能把它變成槓桿。",
            "script_long": "黃仁勳這段話其實在提醒我們，AI 不是單純取代人，而是讓懂工具的人跑得更快。你真正要練的不是追工具名單，而是把工作拆成能交給 AI 的流程。",
            "transcript_window": "AI is not about replacing people. It is about making people more productive and helping them do more work with better tools.",
            "virality_score": 8,
        }
        bad = {
            "start_seconds": 1,
            "end_seconds": 8,
            "hook": "很棒",
            "quote_zh": "大家好",
            "script_short": "短",
            "script_long": "太短",
            "transcript_window": "hello",
            "virality_score": 2,
        }

        good_score, good_reason = figure_segment_quality.score_segment(good)
        bad_score, bad_reason = figure_segment_quality.score_segment(bad)

        self.assertGreaterEqual(good_score, 80)
        self.assertLess(bad_score, 50)
        self.assertIn("duration_good", good_reason)
        self.assertIn("thin_transcript", bad_reason)


if __name__ == "__main__":
    unittest.main()
