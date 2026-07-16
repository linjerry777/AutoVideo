#!/usr/bin/env python3
"""Daily short-form trend calibration for AutoVideo.

The script does two things:
1. Refreshes a lightweight daily trend profile from public web sources.
2. Applies that profile to a job's news.json before audio/render steps.

It intentionally avoids paid search APIs. Google News RSS gives fresh trend
headlines, while the baked-in baseline captures stable 2026 Shorts/Reels rules
from current creator and platform guidance.
"""

from __future__ import annotations

import argparse
import email.utils
import html
import json
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parents[1]
PIPELINE_ROOT = BASE_DIR / "pipeline"
PROFILE_FILE = BASE_DIR / "data" / "shorts_trend_profile.json"
MEDIA_OPS_WEIGHTS_FILE = BASE_DIR / "data" / "autopilot_strategy_weights.json"

TREND_QUERIES = [
    "YouTube Shorts retention hook 2026",
    "Instagram Reels retention hook 2026",
    "TikTok 2026 curiosity short video trends",
    "short form video hooks visual change 2026",
]

STATIC_EVIDENCE = [
    {
        "source": "TikTok Next 2026",
        "url": "https://ads.tiktok.com/business/en-US/next",
        "title": "Curiosity Detours and Reali-Tea",
        "summary": "TikTok's 2026 trend report emphasizes curiosity, real process, comments, and real-time audience language.",
    },
    {
        "source": "Instagram algorithm 2026",
        "url": "https://sproutsocial.com/insights/instagram-algorithm/",
        "title": "Reels ranking uses retention, sends, shares, originality",
        "summary": "Reels need viewers to pass the three-second mark and avoid watermarked or unoriginal content.",
    },
    {
        "source": "Reels retention 2026",
        "url": "https://retensis.com/blog/good-instagram-reels-retention-rate",
        "title": "First three seconds are the highest-leverage retention point",
        "summary": "Avoid logos and slow intros; start with motion, direct value, or an unexpected visual.",
    },
    {
        "source": "Shorts retention curve 2026",
        "url": "https://aibrify.com/blog/youtube-shorts-retention-curve-playbook",
        "title": "Open within one second and change visuals every 1.5-2 seconds",
        "summary": "Front-load payoff and create loop-friendly endings to improve retention curves.",
    },
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today_key() -> str:
    return datetime.now().date().isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_media_ops_directives() -> dict[str, Any]:
    try:
        if MEDIA_OPS_WEIGHTS_FILE.exists():
            data = _read_json(MEDIA_OPS_WEIGHTS_FILE)
            directives = data.get("creative_directives") or {}
            return directives if isinstance(directives, dict) else {}
    except Exception:
        return {}
    return {}


def _strip_html(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value or "")
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def _fetch_url(url: str, timeout: int = 12) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "AutoVideoTrendCalibrator/1.0 (+local)",
            "Accept": "application/rss+xml,text/xml,text/html;q=0.8,*/*;q=0.5",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def fetch_google_news(query: str, limit: int = 4) -> list[dict[str, str]]:
    params = urllib.parse.urlencode({
        "q": query,
        "hl": "en-US",
        "gl": "US",
        "ceid": "US:en",
    })
    url = f"https://news.google.com/rss/search?{params}"
    try:
        root = ET.fromstring(_fetch_url(url))
    except Exception as exc:
        return [{
            "source": "Google News RSS",
            "url": url,
            "title": f"fetch failed: {query}",
            "summary": str(exc)[:180],
        }]

    items: list[dict[str, str]] = []
    for node in root.findall(".//item")[:limit]:
        title = _strip_html(node.findtext("title", ""))
        link = _strip_html(node.findtext("link", ""))
        desc = _strip_html(node.findtext("description", ""))
        pub = _strip_html(node.findtext("pubDate", ""))
        try:
            published_at = email.utils.parsedate_to_datetime(pub).isoformat() if pub else ""
        except Exception:
            published_at = pub
        items.append({
            "source": "Google News RSS",
            "query": query,
            "url": link,
            "title": title,
            "summary": desc[:260],
            "published_at": published_at,
        })
    return items


def build_profile(refresh: bool = False) -> dict[str, Any]:
    if not refresh and PROFILE_FILE.exists():
        try:
            cached = _read_json(PROFILE_FILE)
            if cached.get("date") == _today_key():
                return cached
        except Exception:
            pass

    evidence: list[dict[str, Any]] = list(STATIC_EVIDENCE)
    for query in TREND_QUERIES:
        evidence.extend(fetch_google_news(query, limit=3))

    profile = {
        "date": _today_key(),
        "generated_at": _now_iso(),
        "version": 1,
        "evidence": evidence[:20],
        "rules": {
            "hook_window_seconds": 1.0,
            "critical_retention_seconds": 3.0,
            "target_short_seconds": [12, 25],
            "visual_change_seconds": 1.8,
            "opening_label": "先看這個重點",
            "subtitle_bottom": 340,
            "hook_max_chars": 11,
            "hook_patterns": [
                "specific_number",
                "contradiction",
                "curiosity_gap",
                "cost_or_mistake",
            ],
            "avoid": ["logo_intro", "black_screen", "slow_setup", "watermark_repost"],
        },
    }
    _write_json(PROFILE_FILE, profile)
    return profile


def _has_cjk(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text or ""))


def _compact(text: str, max_chars: int) -> str:
    text = re.sub(r"\s+", "", str(text or "").strip())
    if not _has_cjk(text):
        words = text.split()
        text = "".join(words) if words else text
    return text[:max_chars]


def _score_hook(text: str) -> int:
    text = str(text or "").strip()
    if not text:
        return -10
    score = 0
    if len(_compact(text, 99)) <= 8:
        score += 2
    if re.search(r"\d|一|二|三|3|5|10", text):
        score += 3
    if any(k in text for k in ("不是", "別", "錯", "少看", "真相", "其實", "原來")):
        score += 3
    if any(k in text for k in ("為何", "怎麼", "誰", "嗎", "？", "?")):
        score += 2
    if any(k in text for k in ("爆", "狠", "危險", "翻車", "警訊", "大事")):
        score += 1
    return score


def _topic_word(item: dict[str, Any]) -> str:
    text = f"{item.get('title','')} {item.get('hook','')} {item.get('summary','')}"
    if "AI" in text or "Gemini" in text or "ChatGPT" in text:
        return "AI"
    if "黃仁勳" in text or "NVIDIA" in text or "Nvidia" in text:
        return "AI"
    if "演唱" in text or "MV" in text or "偶像" in text:
        return "娛樂"
    return "重點"


def _directive_hook_variants(patterns: list[str]) -> list[str]:
    variants: list[str] = []
    for pattern in patterns:
        variants.extend({
            "problem_first": ["先別滑走", "你可能想錯"],
            "specific_number": ["3個重點", "三件事"],
            "contradiction": ["其實不是", "先別被騙"],
            "cost_or_mistake": ["代價很大", "別犯這錯"],
            "curiosity_gap": ["關鍵在這", "重點不是它"],
            "why_it_matters": ["跟你有關", "影響很大"],
            "future_risk": ["下一波來了", "風險在後面"],
            "quote_tension": ["這句很關鍵", "他話中有話"],
            "hidden_meaning": ["他沒明說", "真正意思"],
            "fan_question": ["粉絲在問", "這段在紅"],
            "controversy_timeline": ["時間線來了", "怎麼吵起來"],
        }.get(pattern, []))
    return variants


def _build_hook_variants(item: dict[str, Any], idx: int, total: int, max_chars: int, patterns: list[str] | None = None) -> list[str]:
    existing = [str(x).strip() for x in item.get("hook_variants") or [] if str(x).strip()]
    title = str(item.get("title") or "")
    topic = _topic_word(item)
    variants: list[str] = []
    variants.extend(_directive_hook_variants(patterns or []))
    if idx == 0 and total >= 3:
        variants.append(f"{total}件{topic}大事")
    if item.get("bullets"):
        variants.append("3點看懂")
    if existing:
        variants.extend(existing)
    if "不是" not in "".join(variants):
        variants.append("不是你想的")
    if title:
        variants.append(f"{_compact(title, 5)}怎麼了")

    seen: set[str] = set()
    cleaned: list[str] = []
    for value in variants:
        compact = _compact(value, max_chars)
        if compact and compact not in seen:
            cleaned.append(compact)
            seen.add(compact)
    cleaned.sort(key=_score_hook, reverse=True)
    return cleaned[:3] or [_compact(str(item.get("hook") or title or "先看這個"), max_chars)]


def _tighten_script(script: str, item: dict[str, Any], *, first: bool) -> str:
    script = re.sub(r"\s+", " ", str(script or "").strip())
    if not script:
        return script
    if first and not script.startswith(("先別", "先看", "這不是")):
        return f"先別滑走，{script}"
    if not first and len(script) > 48 and "。" in script[:28]:
        return script
    return script


def apply_profile_to_news(news_file: Path, profile: dict[str, Any]) -> dict[str, Any]:
    data = _read_json(news_file)
    rules = profile.get("rules", {})
    max_chars = int(rules.get("hook_max_chars") or 11)
    total = len(data.get("items") or [])
    strategy = str(data.get("strategy") or "tech").lower()
    directives = _load_media_ops_directives()
    directive = directives.get(strategy) or directives.get("tech") or {}
    if not isinstance(directive, dict):
        directive = {}
    hook_patterns = directive.get("hook_patterns") or rules.get("hook_patterns") or []
    if not isinstance(hook_patterns, list):
        hook_patterns = []
    opening_label = directive.get("opening_label") or rules.get("opening_label") or "先看重點"
    subtitle_bottom = int(directive.get("subtitle_bottom") or rules.get("subtitle_bottom") or 340)
    visual_change_seconds = float(directive.get("visual_change_seconds") or rules.get("visual_change_seconds") or 1.8)

    data["shorts_trend_profile"] = {
        "date": profile.get("date"),
        "generated_at": profile.get("generated_at"),
        "source_count": len(profile.get("evidence") or []),
        "rules": rules,
    }
    if directive:
        data["media_ops_creative_directive"] = directive
        if directive.get("layout_mode"):
            data["layout_mode"] = directive["layout_mode"]
        if directive.get("editing_style"):
            data["editing_style"] = directive["editing_style"]

    for idx, item in enumerate(data.get("items") or []):
        if "hook_original" not in item:
            item["hook_original"] = item.get("hook", "")
        variants = _build_hook_variants(item, idx, total, max_chars, hook_patterns)
        item["hook_variants"] = variants
        item["hook"] = variants[0]
        item["opening_label"] = rules.get("opening_label") or "先看這個重點"
        item["opening_label"] = opening_label
        item["subtitle_bottom"] = subtitle_bottom
        item["visual_change_seconds"] = visual_change_seconds
        if directive.get("editing_style"):
            item["media_ops_editing_style"] = directive["editing_style"]
        if directive.get("thumbnail_brief"):
            item["thumbnail_brief"] = directive["thumbnail_brief"]
            item["image2_brief"] = directive["thumbnail_brief"]
        if directive.get("scene_type"):
            item["scene_type"] = directive["scene_type"]
        if directive.get("emotion"):
            if "emotion_original" not in item:
                item["emotion_original"] = item.get("emotion", "")
            item["emotion"] = directive["emotion"]
        item["hook_pattern"] = (
            "specific_number" if re.search(r"\d|一|二|三|3", item["hook"])
            else "contradiction" if any(k in item["hook"] for k in ("不是", "別", "錯"))
            else "curiosity_gap"
        )
        if hook_patterns:
            item["hook_pattern"] = str(hook_patterns[0])
        if item.get("script_short"):
            item["script_short"] = _tighten_script(item["script_short"], item, first=idx == 0)
        if item.get("script_long") and idx == 0:
            item["script_long"] = _tighten_script(item["script_long"], item, first=True)
            item["script"] = item["script_long"]

    _write_json(news_file, data)
    return data


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("job_key", nargs="?", help="pipeline job key, e.g. 2026-05-19/job_180")
    parser.add_argument("--apply", action="store_true", help="apply the daily profile to the job news.json")
    parser.add_argument("--refresh", action="store_true", help="force refresh the trend profile")
    parser.add_argument("--profile-only", action="store_true", help="only refresh/cache the profile")
    args = parser.parse_args()

    profile = build_profile(refresh=args.refresh)
    print(f"[shorts-trend] profile date={profile.get('date')} evidence={len(profile.get('evidence') or [])}")

    if args.profile_only:
        print(PROFILE_FILE)
        return

    if args.apply:
        if not args.job_key:
            raise SystemExit("--apply requires job_key")
        news_file = PIPELINE_ROOT / args.job_key / "news.json"
        if not news_file.exists():
            raise FileNotFoundError(news_file)
        data = apply_profile_to_news(news_file, profile)
        hooks = [it.get("hook") for it in data.get("items", [])]
        print(f"[shorts-trend] applied hooks={hooks}")


if __name__ == "__main__":
    main()
