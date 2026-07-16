"""Quality gate for reusable figure quote segments."""
from __future__ import annotations

import re


def _word_count(text: str) -> int:
    ascii_words = re.findall(r"[A-Za-z0-9]+", text or "")
    cjk_chars = re.findall(r"[\u4e00-\u9fff]", text or "")
    return len(ascii_words) + len(cjk_chars)


def score_segment(segment: dict) -> tuple[int, str]:
    """Return a 0-100 quality score and compact reason string.

    The gate is deliberately deterministic and cheap. LLM scoring can come
    later, but this catches the common failures: too short/long, incomplete
    script, weak hook, empty transcript, and non-quote clips.
    """
    reasons: list[str] = []
    score = 100

    start = float(segment.get("start_seconds") or 0)
    end = float(segment.get("end_seconds") or 0)
    duration = end - start
    if duration < 18 or duration > 45:
        score -= 22
        reasons.append(f"duration={duration:.1f}s")
    elif 22 <= duration <= 38:
        reasons.append("duration_good")

    hook = str(segment.get("hook") or "").strip()
    if not (3 <= len(hook) <= 14):
        score -= 12
        reasons.append("hook_len")

    quote = str(segment.get("quote_zh") or segment.get("quote_original") or "").strip()
    if _word_count(quote) < 8:
        score -= 18
        reasons.append("weak_quote")

    script_short = str(segment.get("script_short") or "").strip()
    script_long = str(segment.get("script_long") or "").strip()
    if _word_count(script_short) < 25:
        score -= 14
        reasons.append("short_script_thin")
    if _word_count(script_long) < 45:
        score -= 12
        reasons.append("long_script_thin")
    if quote and quote[:10] not in script_long and str(segment.get("figure_name") or "") not in script_long:
        score -= 8
        reasons.append("analysis_not_anchored")

    transcript_window = str(segment.get("transcript_window") or "").strip()
    transcript_words = _word_count(transcript_window)
    if transcript_words < 35:
        score -= 15
        reasons.append("thin_transcript")
    elif transcript_words > 260:
        score -= 6
        reasons.append("wide_transcript")

    virality = int(segment.get("virality_score") or 0)
    if virality >= 7:
        score += 4
        reasons.append("high_virality")
    elif virality <= 3:
        score -= 8
        reasons.append("low_virality")

    score = max(0, min(100, score))
    if not reasons:
        reasons.append("ok")
    return score, ",".join(reasons[:6])


def accept_segment(segment: dict, min_score: int = 68) -> bool:
    score, _reason = score_segment(segment)
    return score >= min_score
