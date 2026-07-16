#!/usr/bin/env python3
"""Media Ops Agent for AutoVideo.

The agent combines two signals:
1. Internal channel performance from AutoVideo's local video_stats table.
2. External trend radar from public sources already used by AutoVideo.

It writes:
- data/media_ops_report.json: human/UI readable editor report
- data/autopilot_strategy_weights.json: machine-readable strategy weights
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
REPORT_FILE = DATA_DIR / "media_ops_report.json"
WEIGHTS_FILE = DATA_DIR / "autopilot_strategy_weights.json"
DAILY_BRIEF_FILE = DATA_DIR / "media_ops_daily_briefing.json"
DAILY_BRIEF_MD_FILE = DATA_DIR / "media_ops_daily_briefing.md"
DAILY_BRIEF_STATE_FILE = DATA_DIR / "media_ops_daily_briefing_state.json"
FAILURE_ALERT_STATE_FILE = DATA_DIR / "media_ops_failure_alert_state.json"
PIPELINE_DIR = BASE_DIR / "pipeline"
UPLOAD_POST_BASE = "https://api.upload-post.com/api"

sys.path.insert(0, str(BASE_DIR))

from web import analytics_feedback  # noqa: E402
from web import media_ops_strategy  # noqa: E402
from web.db import get_all_settings, get_conn  # noqa: E402


TOPIC_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("ai_agent", ("agent", "agents", "ai agent", "代理", "智能體", "manus", "operator")),
    ("ai_model", ("gpt", "openai", "claude", "gemini", "llm", "模型", "大模型")),
    ("ai_tool", ("app", "tool", "工具", "prompt", "提示詞", "vibe coding", "vibecoding", "code")),
    ("semiconductor", ("nvidia", "jensen", "gpu", "晶片", "半導體", "黃仁勳", "輝達", "tsmc")),
    ("tech_leader", ("sam altman", "elon", "pichai", "satya", "zuckerberg", "karpathy", "名人", "ceo")),
    ("creator_ai", ("shorts", "reels", "tiktok", "剪輯", "字幕", "封面", "retention", "hook")),
    ("entertainment_kpop", ("mv", "kpop", "itzy", "aespa", "blackpink", "bts", "韓團", "演唱會")),
    ("internet_culture", ("meme", "迷因", "viral", "爆紅", "熱搜", "trend")),
]

STRATEGY_TOPICS = {
    "tech": {"ai_model", "ai_tool", "ai_agent", "semiconductor"},
    "tech_judgement": {"ai_agent", "ai_model", "ai_tool", "creator_ai"},
    "figure_tech": {"tech_leader", "semiconductor", "ai_model"},
    "business_finance": {"ai_agent", "ai_model", "semiconductor", "tech_leader", "creator_ai"},
    "entertainment": {"entertainment_kpop", "internet_culture"},
    "entertainment_storyboard": {"entertainment_kpop", "internet_culture", "creator_ai"},
}

TOPIC_SEARCH_TERMS = {
    "ai_agent": "AI agent",
    "ai_model": "AI model",
    "ai_tool": "AI tools",
    "semiconductor": "Nvidia",
    "tech_leader": "Sam Altman Jensen Huang",
    "creator_ai": "AI video editing",
    "entertainment_kpop": "Kpop",
    "internet_culture": "viral trend",
    "general": "AI",
}

CREATIVE_DIRECTIVE_BASE = {
    "tech": {
        "editing_style": "breaking_news_snap",
        "opening_label": "先看結論",
        "hook_patterns": ["specific_number", "contradiction", "cost_or_mistake"],
        "subtitle_bottom": 320,
        "visual_change_seconds": 1.5,
        "emotion": "curiosity",
        "scene_type": "tech",
        "layout_mode": "article_rotate",
        "thumbnail_brief": "image2: non-purple newsroom cover, one strong AI/business visual, large concise headline space, credible tech media feel",
        "new_format_opportunities": [
            "AI工具實測：同一任務用新工具跑一次，直接給結果與踩雷",
            "一張圖看懂：把新聞拆成原因、影響、誰會受傷",
            "工程師吐槽版：用更口語的角度說這新聞跟一般人有什麼關係",
        ],
    },
    "tech_judgement": {
        "editing_style": "doro_judgement_editorial",
        "opening_label": "發生什麼",
        "hook_patterns": ["contradiction", "why_it_matters", "future_risk"],
        "subtitle_bottom": 305,
        "visual_change_seconds": 1.7,
        "emotion": "curiosity",
        "scene_type": "robot",
        "layout_mode": "image2_editorial",
        "thumbnail_brief": "image2: premium AI explainer cover, realistic scene plus one symbolic object, no purple gradient, no readable text",
        "new_format_opportunities": [
            "DORO判讀：先講錯覺，再講真正影響",
            "三個後果：把科技新聞變成投資、工作、產品三層影響",
            "反直覺解讀：這不是功能更新，是產業位置變了",
        ],
    },
    "figure_tech": {
        "editing_style": "quote_context_breakdown",
        "opening_label": "他真正想說",
        "hook_patterns": ["quote_tension", "hidden_meaning", "specific_number"],
        "subtitle_bottom": 300,
        "visual_change_seconds": 1.8,
        "emotion": "curiosity",
        "scene_type": "speaker",
        "layout_mode": "visual",
        "thumbnail_brief": "cover frame should center the speaker and one topic phrase; keep top safe area clear for mobile UI",
        "new_format_opportunities": [
            "名人一句話拆解：原片金句 + 中文白話 + 對台灣科技圈影響",
            "CEO預言驗證：拿舊演講對照今天新聞",
            "三句話控全局：同一位名人的三個片段剪成一支主題片",
        ],
    },
    "business_finance": {
        "editing_style": "business_model_breakdown",
        "opening_label": "先看錢怎麼流",
        "hook_patterns": ["business_model", "hidden_cost", "risk_first"],
        "subtitle_bottom": 305,
        "visual_change_seconds": 1.6,
        "emotion": "curiosity",
        "scene_type": "business",
        "layout_mode": "image2_editorial",
        "thumbnail_brief": "image2: credible business explainer cover, company/product context, money flow or risk symbol, no stock price chart, no readable text",
        "new_format_opportunities": [
            "一家公司真正靠什麼賺錢：營收來源 + 成本壓力 + 誰買單",
            "別只看新聞標題：把商業模式拆成訂閱、企業合約、毛利與風險",
            "非投資建議：用公司故事解釋產業變化，不做買賣判斷",
        ],
    },
    "entertainment": {
        "editing_style": "fan_context_pop",
        "opening_label": "這段在紅什麼",
        "hook_patterns": ["fan_question", "controversy_timeline", "specific_number"],
        "subtitle_bottom": 330,
        "visual_change_seconds": 1.4,
        "emotion": "joy",
        "scene_type": "stage",
        "layout_mode": "image2_editorial",
        "thumbnail_brief": "image2: energetic entertainment cover, concert/media scene, bright contrast, no purple gradient, no celebrity likeness",
        "new_format_opportunities": [
            "MV彩蛋拆解：挑三個畫面講粉絲為什麼瘋",
            "飯圈時間線：事件從哪裡爆、誰回應、現在吵什麼",
            "舞台/造型評分：用排行榜和反差點提高留言率",
            "留言區反應：把粉絲留言變成下一支影片的開場",
        ],
    },
    "entertainment_storyboard": {
        "editing_style": "movie_language_pet_disaster",
        "opening_label": "奶烙出任務",
        "hook_patterns": ["classic_scene_grammar", "pet_daily_disaster", "visual_punchline"],
        "subtitle_bottom": 330,
        "visual_change_seconds": 1.0,
        "emotion": "surprise",
        "scene_type": "movie_language_pet_disaster",
        "layout_mode": "frame_first_storyboard_pool",
        "thumbnail_brief": "image2: cinematic pet disaster frame, one expressive cat and one daily-life conflict prop, no readable text, no celebrity likeness",
        "new_format_opportunities": [
            "每天挑一個電影或熱門影視片段的鏡頭語法，改寫成貓貓日常災難。",
            "一張圖只做一個 9:16 鏡頭；不產 storyboard sheet，批准後才送 Seedance。",
        ],
    },
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def today_key() -> str:
    try:
        from zoneinfo import ZoneInfo

        return datetime.now(ZoneInfo("Asia/Taipei")).date().isoformat()
    except Exception:
        return datetime.now().date().isoformat()


def read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default
    return default


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def as_int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def compact_text(*parts: Any) -> str:
    return re.sub(r"\s+", " ", " ".join(str(p or "") for p in parts)).strip()


def classify_topic(text: str) -> str:
    lower = (text or "").lower()
    for topic, needles in TOPIC_RULES:
        if any(needle.lower() in lower for needle in needles):
            return topic
    if re.search(r"ai|科技|人工智慧", lower, re.I):
        return "ai_model"
    return "general"


def format_topic(topic: str) -> str:
    return {
        "ai_agent": "AI Agent / 自動化",
        "ai_model": "AI 模型 / 大廠發布",
        "ai_tool": "AI 工具 / Vibe Coding",
        "semiconductor": "半導體 / NVIDIA",
        "tech_leader": "科技名人 / CEO 觀點",
        "creator_ai": "Shorts 製作 / AI 剪輯",
        "entertainment_kpop": "娛樂 / K-pop",
        "internet_culture": "網路熱搜 / 迷因",
        "general": "一般題材",
    }.get(topic, topic)


def detect_style_signals(text: str) -> list[str]:
    lower = (text or "").lower()
    signals = []
    if any(k in lower for k in ("hook", "前三秒", "3 second", "retention", "留存")):
        signals.append("hook_retention")
    if any(k in lower for k in ("caption", "subtitle", "字幕")):
        signals.append("large_captions")
    if any(k in lower for k in ("ai", "image", "生成", "sora", "veo", "image2")):
        signals.append("ai_visuals")
    if any(k in lower for k in ("thumbnail", "封面", "ctr")):
        signals.append("cover_ctr")
    if any(k in lower for k in ("template", "remix", "capcut", "剪輯")):
        signals.append("template_remix")
    return signals


def source_bonus(source_type: str) -> int:
    source_type = (source_type or "").lower()
    if source_type.startswith("youtube"):
        return 24
    if source_type.startswith("tiktok"):
        return 22
    if source_type.startswith("google_trends"):
        return 18
    if source_type in {"last30days", "reddit", "hackernews"}:
        return 14
    return 8


def score_external_item(item: dict[str, Any]) -> int:
    views = max(as_int(item.get("view_count")), as_int(item.get("tiktok_video_views")))
    comments = as_int(item.get("comment_count"))
    score = source_bonus(item.get("source_type", ""))
    if views:
        score += min(70, int(math.log10(views + 1) * 12))
    if comments:
        score += min(16, int(math.log10(comments + 1) * 5))
    if item.get("tiktok_rank"):
        rank = as_int(item.get("tiktok_rank"))
        score += max(0, 16 - min(rank, 16))
    if detect_style_signals(compact_text(item.get("title"), item.get("summary"))):
        score += 8
    return min(score, 100)


def normalize_external_item(item: dict[str, Any], source: str) -> dict[str, Any]:
    text = compact_text(item.get("title"), item.get("summary"), item.get("channel"), item.get("source"))
    topic = classify_topic(text)
    return {
        "source": item.get("source") or source,
        "source_type": item.get("source_type") or source,
        "title": item.get("title") or "",
        "summary": item.get("summary") or "",
        "url": item.get("url") or "",
        "channel": item.get("channel") or "",
        "views": max(as_int(item.get("view_count")), as_int(item.get("tiktok_video_views"))),
        "comments": as_int(item.get("comment_count")),
        "topic": topic,
        "topic_label": format_topic(topic),
        "style_signals": detect_style_signals(text),
        "score": score_external_item(item),
    }


def load_internal_performance(limit: int = 200) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT
                j.id AS job_id,
                j.date,
                j.topic,
                j.triggered_by,
                j.platforms AS requested_platforms,
                j.finished_at,
                COALESCE(SUM(vs.views), 0) AS total_views,
                COALESCE(SUM(vs.likes), 0) AS total_likes,
                COALESCE(SUM(vs.comments), 0) AS total_comments,
                COALESCE(SUM(vs.shares), 0) AS total_shares,
                COUNT(vs.id) AS stats_rows
            FROM jobs j
            LEFT JOIN video_stats vs ON vs.job_id = j.id
            WHERE j.status='done'
            GROUP BY j.id
            ORDER BY j.finished_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        job_ids = [int(row["job_id"]) for row in rows]
        stat_rows = []
        if job_ids:
            placeholders = ",".join("?" for _ in job_ids)
            stat_rows = conn.execute(
                f"""
                SELECT
                    job_id,
                    platform,
                    platform_video_id,
                    platform_url,
                    views,
                    likes,
                    comments,
                    shares,
                    fetched_at
                FROM video_stats
                WHERE job_id IN ({placeholders})
                """,
                job_ids,
            ).fetchall()
    stats_by_job: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for stat in stat_rows:
        stats_by_job[int(stat["job_id"])].append(dict(stat))
    out = []
    for row in rows:
        item = dict(row)
        schedule = _read_job_schedule(item.get("date") or "", int(item["job_id"]))
        item["latest_scheduled_at"] = latest_scheduled_at(schedule)
        meta = analytics_feedback.experiment_meta_for_job(item.get("date") or "", int(item["job_id"]))
        item["experiment_meta"] = meta
        item["strategy"] = meta.get("strategy") or "generic"
        item["topic_class"] = classify_topic(compact_text(item.get("topic"), meta.get("hook"), meta.get("figure_name")))
        item["story_cluster"] = meta.get("media_ops_cluster") or media_ops_strategy.story_cluster(
            {
                "title": meta.get("first_title") or item.get("topic") or meta.get("hook") or "",
                "summary": meta.get("first_summary") or meta.get("figure_name") or "",
                "source": meta.get("source_type") or "",
            }
        )
        item["source_key"] = (
            meta.get("media_ops_source_key")
            or media_ops_strategy.source_key({"source": meta.get("source_type") or ""})
        )
        item["topic_label"] = format_topic(item["topic_class"])
        item["total_views"] = as_int(item.get("total_views"))
        item["engagements"] = as_int(item.get("total_likes")) + as_int(item.get("total_comments")) + as_int(item.get("total_shares"))
        item["engagement_rate"] = round(item["engagements"] / item["total_views"] * 100, 2) if item["total_views"] else 0
        item["platform_stats"] = stats_by_job.get(int(item["job_id"]), [])
        out.append(item)
    return out


def parse_dt(value: str | None, tz_name: str = "UTC") -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc)
    try:
        local_tz = ZoneInfo(tz_name or "UTC")
    except Exception:
        local_tz = timezone.utc
    return dt.replace(tzinfo=local_tz).astimezone(timezone.utc)


def latest_scheduled_at(schedule: list[dict[str, Any]]) -> str:
    core_platforms = {"youtube", "facebook", "instagram", "threads", "x", "tiktok"}
    dates: list[datetime] = []
    for ent in schedule or []:
        platform = str(ent.get("platform") or "").lower()
        if platform not in core_platforms:
            continue
        dt = parse_dt(ent.get("scheduled_date"), ent.get("timezone") or "UTC")
        if dt:
            dates.append(dt)
    if not dates:
        return ""
    return max(dates).isoformat()


def summarize_internal(rows: list[dict[str, Any]]) -> dict[str, Any]:
    views = [r["total_views"] for r in rows if r.get("total_views")]
    baseline = median(views)
    mature_rows = [r for r in rows if _is_mature_row(r)]
    mature_views = [r["total_views"] for r in mature_rows if r.get("total_views")]
    mature_baseline = median(mature_views)
    by_strategy = group_metric(rows, "strategy")
    by_topic = group_metric(rows, "topic_class")
    by_cluster = group_metric(rows, "story_cluster")
    by_source_key = group_metric(rows, "source_key")
    by_hook = group_metric(rows, lambda r: (r.get("experiment_meta") or {}).get("hook_pattern") or "unknown")
    by_platform = group_platform_metric(rows, lambda row, stat: stat.get("platform") or "unknown")
    by_strategy_platform = group_platform_metric(
        rows,
        lambda row, stat: f"{row.get('strategy') or 'generic'}:{stat.get('platform') or 'unknown'}",
    )
    mature_by_strategy = group_metric(mature_rows, "strategy") if mature_rows else []
    mature_by_topic = group_metric(mature_rows, "topic_class") if mature_rows else []
    mature_by_cluster = group_metric(mature_rows, "story_cluster") if mature_rows else []
    mature_by_source_key = group_metric(mature_rows, "source_key") if mature_rows else []
    mature_by_hook = group_metric(mature_rows, lambda r: (r.get("experiment_meta") or {}).get("hook_pattern") or "unknown") if mature_rows else []
    mature_by_strategy_platform = group_platform_metric(
        mature_rows,
        lambda row, stat: f"{row.get('strategy') or 'generic'}:{stat.get('platform') or 'unknown'}",
    ) if mature_rows else []
    winners = sorted(rows, key=lambda r: r.get("total_views") or 0, reverse=True)[:5]
    return {
        "video_count": len(rows),
        "stats_count": len([r for r in rows if r.get("stats_rows")]),
        "baseline_views": baseline,
        "mature_video_count": len(mature_rows),
        "mature_baseline_views": mature_baseline,
        "total_views": sum(r.get("total_views") or 0 for r in rows),
        "by_strategy": by_strategy,
        "mature_by_strategy": mature_by_strategy,
        "by_topic": by_topic,
        "mature_by_topic": mature_by_topic,
        "by_cluster": by_cluster,
        "mature_by_cluster": mature_by_cluster,
        "by_source_key": by_source_key,
        "mature_by_source_key": mature_by_source_key,
        "by_hook_pattern": by_hook,
        "mature_by_hook_pattern": mature_by_hook,
        "by_platform": by_platform,
        "by_strategy_platform": by_strategy_platform,
        "mature_by_strategy_platform": mature_by_strategy_platform,
        "winners": [
            {
                "job_id": r["job_id"],
                "title": r.get("topic") or "",
                "strategy": r.get("strategy"),
                "topic": r.get("topic_label"),
                "views": r.get("total_views") or 0,
                "engagement_rate": r.get("engagement_rate") or 0,
            }
            for r in winners
        ],
    }


def _is_mature_row(row: dict[str, Any], min_hours: int = 36, min_after_schedule_hours: int = 24) -> bool:
    finished_at = parse_dt(str(row.get("finished_at") or ""))
    if not finished_at:
        return False
    now = datetime.now(timezone.utc)
    if now - finished_at < timedelta(hours=min_hours):
        return False
    latest_schedule = parse_dt(str(row.get("latest_scheduled_at") or ""))
    if latest_schedule and now - latest_schedule < timedelta(hours=min_after_schedule_hours):
        return False
    return True


def median(values: list[int]) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return round((ordered[mid - 1] + ordered[mid]) / 2)


def group_metric(rows: list[dict[str, Any]], key: str | Any) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = defaultdict(lambda: {"videos": 0, "views": 0, "engagements": 0, "best_job_id": None, "best_views": -1})
    for row in rows:
        name = key(row) if callable(key) else row.get(key)
        name = str(name or "unknown")
        g = groups[name]
        views = as_int(row.get("total_views"))
        g["videos"] += 1
        g["views"] += views
        g["engagements"] += as_int(row.get("engagements"))
        if views > g["best_views"]:
            g["best_views"] = views
            g["best_job_id"] = row.get("job_id")
    out = []
    for name, value in groups.items():
        videos = value["videos"] or 1
        out.append({
            "key": name,
            "label": format_topic(name) if name in {t for t, _ in TOPIC_RULES} or name == "general" else name,
            "videos": value["videos"],
            "views": value["views"],
            "avg_views": round(value["views"] / videos),
            "engagement_rate": round(value["engagements"] / value["views"] * 100, 2) if value["views"] else 0,
            "best_job_id": value["best_job_id"],
            "best_views": max(0, value["best_views"]),
        })
    return sorted(out, key=lambda x: (x["avg_views"], x["views"]), reverse=True)


def group_platform_metric(rows: list[dict[str, Any]], key: Any) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = defaultdict(lambda: {"videos": 0, "views": 0, "engagements": 0, "best_job_id": None, "best_views": -1})
    for row in rows:
        for stat in row.get("platform_stats") or []:
            name = key(row, stat) if callable(key) else stat.get(key)
            name = str(name or "unknown")
            views = as_int(stat.get("views"))
            engagements = as_int(stat.get("likes")) + as_int(stat.get("comments")) + as_int(stat.get("shares"))
            g = groups[name]
            g["videos"] += 1
            g["views"] += views
            g["engagements"] += engagements
            if views > g["best_views"]:
                g["best_views"] = views
                g["best_job_id"] = row.get("job_id")
    out = []
    for name, value in groups.items():
        videos = value["videos"] or 1
        out.append({
            "key": name,
            "label": name,
            "videos": value["videos"],
            "views": value["views"],
            "avg_views": round(value["views"] / videos),
            "engagement_rate": round(value["engagements"] / value["views"] * 100, 2) if value["views"] else 0,
            "best_job_id": value["best_job_id"],
            "best_views": max(0, value["best_views"]),
        })
    return sorted(out, key=lambda x: (x["avg_views"], x["views"]), reverse=True)


def fetch_upload_post_profile_analytics(settings: dict[str, str]) -> dict[str, Any]:
    api_key = os.getenv("UPLOAD_POST_KEY") or settings.get("upload_post_key") or ""
    if not api_key:
        return {"available": False, "reason": "missing UPLOAD_POST_KEY", "profiles": []}

    profile_keys = [
        "autopilot_news_profile",
        "autopilot_tech_judgement_profile",
        "autopilot_business_finance_profile",
        "autopilot_trending_profile",
        "autopilot_figure_tech_profile",
        "autopilot_figure_entertainment_profile",
    ]
    profiles = sorted({settings.get(k, "").strip() for k in profile_keys if settings.get(k, "").strip()})
    platforms = settings.get("autopilot_platforms") or "youtube,instagram,facebook,threads,x"
    page_id = settings.get("meta_fb_page_id") or os.getenv("META_FB_PAGE_ID") or ""
    results = []
    for profile in profiles:
        params = {"platforms": platforms}
        if page_id:
            params["page_id"] = page_id
        url = f"{UPLOAD_POST_BASE}/analytics/{urllib.parse.quote(profile)}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(
            url,
            headers={"Authorization": f"Apikey {api_key}", "User-Agent": "AutoVideo-MediaOps/1.0"},
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            results.append({"profile": profile, "ok": True, "analytics": data})
        except Exception as exc:
            results.append({"profile": profile, "ok": False, "error": str(exc)[:240]})
    return {"available": True, "profiles": results}


def collect_external_trends(limit_per_source: int = 12) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    def add(source: str, values: list[dict[str, Any]]) -> None:
        for item in values or []:
            items.append(normalize_external_item(item, source))

    try:
        from web.routes import news as news_routes

        add("youtube_tw", news_routes._fetch_youtube_trending(None, "TW", limit_per_source))
        add("youtube_us", news_routes._fetch_youtube_trending(None, "US", limit_per_source))
        add("google_trends_tw", news_routes._fetch_google_trends_tw(None, limit_per_source))
        add("tiktok_tw", news_routes._fetch_tiktok_tw(None, limit_per_source, lang="zh-TW"))
        add("tiktok_viral", news_routes._fetch_tiktok_viral(None, limit_per_source, region="TW"))
        add("last30days_ai", news_routes._fetch_last30days("AI", limit_per_source))
        add("last30days_vibe", news_routes._fetch_last30days("vibe coding", max(6, limit_per_source // 2)))
    except Exception as exc:
        items.append({
            "source": "agent",
            "source_type": "error",
            "title": "external trend fetch failed",
            "summary": str(exc)[:240],
            "url": "",
            "channel": "",
            "views": 0,
            "comments": 0,
            "topic": "general",
            "topic_label": format_topic("general"),
            "style_signals": [],
            "score": 0,
        })

    try:
        from scripts import shorts_trend_calibrator

        for query in shorts_trend_calibrator.TREND_QUERIES:
            add("creator_trend_news", shorts_trend_calibrator.fetch_google_news(query, limit=3))
    except Exception:
        pass

    deduped: dict[str, dict[str, Any]] = {}
    for item in items:
        key = item.get("url") or item.get("title")
        if not key:
            continue
        current = deduped.get(key)
        if not current or item.get("score", 0) > current.get("score", 0):
            deduped[key] = item
    return sorted(deduped.values(), key=lambda x: x.get("score", 0), reverse=True)[:80]


def summarize_external(items: list[dict[str, Any]]) -> dict[str, Any]:
    topic_groups: dict[str, dict[str, Any]] = defaultdict(lambda: {"items": 0, "score": 0, "views": 0, "examples": []})
    style_groups: dict[str, int] = defaultdict(int)
    channel_groups: dict[str, dict[str, Any]] = defaultdict(lambda: {"items": 0, "views": 0, "score": 0})
    for item in items:
        topic = item.get("topic") or "general"
        g = topic_groups[topic]
        g["items"] += 1
        g["score"] += as_int(item.get("score"))
        g["views"] += as_int(item.get("views"))
        if len(g["examples"]) < 3:
            g["examples"].append({"title": item.get("title"), "source": item.get("source"), "url": item.get("url"), "score": item.get("score")})
        for signal in item.get("style_signals") or []:
            style_groups[signal] += 1
        channel = item.get("channel")
        if channel:
            c = channel_groups[channel]
            c["items"] += 1
            c["views"] += as_int(item.get("views"))
            c["score"] += as_int(item.get("score"))

    topics = [
        {
            "key": key,
            "label": format_topic(key),
            "items": val["items"],
            "score": val["score"],
            "avg_score": round(val["score"] / val["items"]) if val["items"] else 0,
            "views": val["views"],
            "examples": val["examples"],
        }
        for key, val in topic_groups.items()
    ]
    topics.sort(key=lambda x: (x["score"], x["views"]), reverse=True)
    channels = [
        {"channel": key, **val, "avg_score": round(val["score"] / val["items"]) if val["items"] else 0}
        for key, val in channel_groups.items()
    ]
    channels.sort(key=lambda x: (x["score"], x["views"]), reverse=True)
    return {
        "item_count": len(items),
        "top_items": items[:12],
        "topics": topics[:10],
        "channels": channels[:10],
        "style_signals": sorted(
            [{"key": key, "count": count} for key, count in style_groups.items()],
            key=lambda x: x["count"],
            reverse=True,
        ),
    }


def _metric_map(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("key") or ""): row for row in rows if row.get("key")}


def build_creative_directives(internal: dict[str, Any], external: dict[str, Any], weights: dict[str, Any]) -> dict[str, Any]:
    """Build machine-readable editorial instructions for render/audio scripts."""
    baseline = as_int(internal.get("mature_baseline_views")) or as_int(internal.get("baseline_views"))
    by_strategy = _metric_map(internal.get("mature_by_strategy") or internal.get("by_strategy") or [])
    style_signals = {str(row.get("key")) for row in external.get("style_signals") or []}
    topic_weights = weights.get("topic_weights") or {}

    def is_weak(strategy: str) -> bool:
        row = by_strategy.get(strategy) or {}
        if not baseline or not row.get("videos"):
            return False
        return as_int(row.get("avg_views")) < baseline * 0.8

    directives: dict[str, Any] = {}
    for strategy, base in CREATIVE_DIRECTIVE_BASE.items():
        directive = dict(base)
        focus_topics = [
            {"topic": topic, "label": format_topic(topic), "weight": topic_weights.get(topic, 1.0)}
            for topic in STRATEGY_TOPICS.get(strategy, set())
        ]
        focus_topics.sort(key=lambda x: x["weight"], reverse=True)
        directive["focus_topics"] = focus_topics[:3]
        directive["decision_source"] = "internal_performance + external_trend_radar"

        if is_weak(strategy):
            directive["risk_mode"] = "aggressive_hook_test"
            directive["hook_patterns"] = list(dict.fromkeys(["problem_first", "contradiction", *directive["hook_patterns"]]))
            directive["visual_change_seconds"] = min(float(directive["visual_change_seconds"]), 1.35)
            directive["opening_label"] = "先別滑走" if strategy != "figure_tech" else "這句很關鍵"

        if "large_captions" in style_signals:
            directive["subtitle_scale"] = "large"
            directive["subtitle_bottom"] = min(int(directive["subtitle_bottom"]), 315)
        if "hook_retention" in style_signals:
            directive["first_second_rule"] = "show payoff or conflict in first second; no logo intro"
        if "cover_ctr" in style_signals:
            directive["thumbnail_brief"] += "; stronger face/object contrast, readable at grid size"
        if "ai_visuals" in style_signals and strategy in {"tech", "tech_judgement", "entertainment"}:
            directive["image2_scene_count"] = 3
            directive["image2_usage"] = "generate multiple concrete visuals from the script, then cut between them instead of using one static cover"
        if "template_remix" in style_signals:
            directive["format_test"] = "keep the topic, remix the pacing/title-card pattern weekly"

        directives[strategy] = directive

    directives["new_content_type_backlog"] = [
        {
            "lane": "tech",
            "type": "ai_tool_teardown",
            "why": "Uses existing GPT + image2; easier than needing customer footage, and naturally creates before/after proof.",
            "pilot": "同一個任務：GPT-5.5 vs 新AI工具，30秒看結果差在哪",
        },
        {
            "lane": "tech",
            "type": "trend_receipt",
            "why": "Turns abstract tech news into receipts: screenshot, source, consequence. Stronger credibility than generic commentary.",
            "pilot": "一張截圖證明：這個AI更新會改掉誰的工作流",
        },
        {
            "lane": "entertainment",
            "type": "fan_comment_react",
            "why": "Entertainment needs comment/share mechanics; fan language can become the hook and CTA.",
            "pilot": "留言區都在問的那個畫面，到底暗示什麼？",
        },
        {
            "lane": "entertainment",
            "type": "mv_easter_egg",
            "why": "Does not require original footage if using generated editorial visuals plus source screenshots; easy to batch.",
            "pilot": "新MV三個彩蛋，粉絲第一眼通常會漏掉",
        },
    ]
    return directives


def build_lane_actions(internal: dict[str, Any], strategy_weights: dict[str, float]) -> dict[str, dict[str, Any]]:
    """Decide which lanes should be pushed, tested, or held back tomorrow.

    Strategy weights alone only rank candidates inside each lane.  These actions
    are the stronger lever: they let the scheduler reduce repeat exposure to a
    lane that has enough evidence of weak views, while still keeping core lanes
    alive when the sample is small.
    """
    baseline = as_int(internal.get("mature_baseline_views")) or as_int(internal.get("baseline_views"))
    by_strategy = _metric_map(internal.get("mature_by_strategy") or internal.get("by_strategy") or [])
    actions: dict[str, dict[str, Any]] = {}
    core_lanes = {"tech", "figure_tech"}

    for strategy in STRATEGY_TOPICS:
        row = by_strategy.get(strategy) or {}
        videos = as_int(row.get("videos"))
        avg_views = as_int(row.get("avg_views"))
        best_views = as_int(row.get("best_views"))
        weight = float(strategy_weights.get(strategy) or 1.0)
        action = "keep"
        cadence_days = 1
        quota = 1
        reason = "not enough performance history; keep one controlled run"

        if baseline and videos >= 3:
            ratio = avg_views / baseline if baseline else 1.0
            best_ratio = best_views / baseline if baseline else 0
            reason = f"avg={avg_views}, baseline={baseline}, best={best_views}, weight={weight:.2f}"
            if ratio >= 1.15 or (best_ratio >= 1.8 and ratio >= 0.85) or weight >= 1.25:
                action = "boost"
                quota = 2 if strategy in core_lanes else 1
                reason += "; outperforming baseline"
            elif ratio < 0.55 and videos >= 5 and strategy not in core_lanes:
                action = "pause"
                cadence_days = 0
                quota = 0
                reason += "; repeated underperformance"
            elif ratio < 0.8 or weight < 0.85:
                action = "experiment"
                cadence_days = 2
                quota = 1
                reason += "; only run every other day with aggressive hook tests"

        if strategy in core_lanes and action == "pause":
            action = "experiment"
            cadence_days = 2
            quota = 1
            reason += "; core lane protected from full pause"

        actions[strategy] = {
            "action": action,
            "cadence_days": cadence_days,
            "daily_quota": quota,
            "avg_views": avg_views,
            "baseline_views": baseline,
            "best_views": best_views,
            "sample_videos": videos,
            "strategy_weight": round(weight, 2),
            "reason": reason,
        }

    return actions


def build_platform_actions(internal: dict[str, Any]) -> dict[str, dict[str, dict[str, Any]]]:
    """Decide per-lane platform fan-out from observed Upload-Post analytics."""
    actions: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    always_keep = {"youtube", "facebook"}
    for row in internal.get("mature_by_strategy_platform") or internal.get("by_strategy_platform") or []:
        key = str(row.get("key") or "")
        if ":" not in key:
            continue
        strategy, platform = key.split(":", 1)
        strategy = strategy.strip().lower()
        platform = platform.strip().lower()
        videos = as_int(row.get("videos"))
        avg_views = as_int(row.get("avg_views"))
        best_views = as_int(row.get("best_views"))
        action = "keep"
        reason = f"avg={avg_views}, best={best_views}, videos={videos}"

        if platform in always_keep:
            reason += "; core distribution platform"
        elif videos >= 2 and platform == "tiktok" and avg_views <= 1:
            action = "pause"
            reason += "; repeated zero-view TikTok delivery"
        elif videos >= 3 and avg_views < 5:
            action = "pause"
            reason += "; repeated near-zero reach"
        elif videos >= 3 and avg_views < 15:
            action = "experiment"
            reason += "; low reach, keep only when manually requested or during recovery tests"
        elif videos >= 3 and avg_views >= 50:
            action = "boost"
            reason += "; platform is carrying meaningful incremental reach"

        actions[strategy][platform] = {
            "action": action,
            "avg_views": avg_views,
            "best_views": best_views,
            "sample_videos": videos,
            "reason": reason,
        }

    return {strategy: dict(platforms) for strategy, platforms in actions.items()}


def build_strategy_weights(internal: dict[str, Any], external: dict[str, Any]) -> dict[str, Any]:
    baseline = as_int(internal.get("mature_baseline_views")) or as_int(internal.get("baseline_views"))
    internal_topic_score = {
        row["key"]: (row["avg_views"] / baseline if baseline else 1.0)
        for row in (internal.get("mature_by_topic") or internal.get("by_topic") or [])
    }
    external_topic_score = {
        row["key"]: min(2.0, (row["avg_score"] or 0) / 50)
        for row in external.get("topics", [])
    }

    strategy_weights = {}
    for strategy, topics in STRATEGY_TOPICS.items():
        score = 1.0
        internal_hits = [internal_topic_score.get(topic) for topic in topics if topic in internal_topic_score]
        external_hits = [external_topic_score.get(topic) for topic in topics if topic in external_topic_score]
        if internal_hits:
            avg_internal = sum(internal_hits) / len(internal_hits)
            score += max(-0.35, min(0.6, (avg_internal - 1.0) * 0.45))
        if external_hits:
            score += max(0, min(0.55, sum(external_hits) / len(external_hits) * 0.3))
        strategy_weights[strategy] = round(max(0.35, min(2.2, score)), 2)

    ranked = sorted(strategy_weights.items(), key=lambda x: x[1], reverse=True)
    topic_weights = {}
    all_topics = set(internal_topic_score) | set(external_topic_score)
    for topic in all_topics:
        topic_weights[topic] = round(
            max(0.25, min(2.5, 0.8 * internal_topic_score.get(topic, 1.0) + 0.35 * external_topic_score.get(topic, 0))),
            2,
        )
    sorted_topic_weights = dict(sorted(topic_weights.items(), key=lambda x: x[1], reverse=True))
    cluster_weights = build_cluster_weights(internal)
    source_weights = build_source_weights(internal)
    partial_weights = {
        "strategy_weights": strategy_weights,
        "topic_weights": sorted_topic_weights,
        "cluster_weights": cluster_weights,
        "source_weights": source_weights,
    }
    direction = build_direction_plan(strategy_weights, sorted_topic_weights, external)
    creative_directives = build_creative_directives(internal, external, {**partial_weights, "direction": direction})
    lane_actions = build_lane_actions(internal, strategy_weights)
    platform_actions = build_platform_actions(internal)

    return {
        "generated_at": now_iso(),
        "strategy_weights": strategy_weights,
        "topic_weights": sorted_topic_weights,
        "cluster_weights": cluster_weights,
        "source_weights": source_weights,
        "recommended_mix": [{"strategy": s, "weight": w} for s, w in ranked],
        "direction": direction,
        "creative_directives": creative_directives,
        "lane_actions": lane_actions,
        "platform_actions": platform_actions,
    }


def build_cluster_weights(internal: dict[str, Any]) -> dict[str, float]:
    baseline = as_int(internal.get("mature_baseline_views")) or as_int(internal.get("baseline_views"))
    if not baseline:
        return {}
    weights: dict[str, float] = {}
    for row in internal.get("mature_by_cluster") or internal.get("by_cluster") or []:
        key = str(row.get("key") or "")
        videos = as_int(row.get("videos"))
        avg_views = as_int(row.get("avg_views"))
        if not key or key == "unknown" or videos < 2:
            continue
        ratio = avg_views / baseline
        weights[key] = round(max(0.55, min(1.55, 0.85 + (ratio - 1.0) * 0.45)), 2)
    return dict(sorted(weights.items(), key=lambda x: x[1], reverse=True))


def build_source_weights(internal: dict[str, Any]) -> dict[str, float]:
    baseline = as_int(internal.get("mature_baseline_views")) or as_int(internal.get("baseline_views"))
    if not baseline:
        return {}
    weights: dict[str, float] = {}
    for row in internal.get("mature_by_source_key") or internal.get("by_source_key") or []:
        key = str(row.get("key") or "")
        videos = as_int(row.get("videos"))
        avg_views = as_int(row.get("avg_views"))
        if not key or key == "unknown" or videos < 2:
            continue
        ratio = avg_views / baseline
        weights[key] = round(max(0.7, min(1.35, 0.9 + (ratio - 1.0) * 0.35)), 2)
    return dict(sorted(weights.items(), key=lambda x: x[1], reverse=True))


def build_direction_plan(strategy_weights: dict[str, float], topic_weights: dict[str, float], external: dict[str, Any]) -> dict[str, Any]:
    """Build machine-readable instructions for tomorrow's autopilot selection."""
    lane_keywords = {}
    lane_focus_topics = {}
    for strategy, allowed_topics in STRATEGY_TOPICS.items():
        candidates = [(topic, topic_weights.get(topic, 0)) for topic in allowed_topics if topic in TOPIC_SEARCH_TERMS]
        candidates.sort(key=lambda x: x[1], reverse=True)
        focus = [topic for topic, score in candidates if score > 0][:3]
        lane_focus_topics[strategy] = focus
        lane_keywords[strategy] = TOPIC_SEARCH_TERMS.get(focus[0], "AI") if focus else "AI"

    hot_topics = [
        {
            "topic": row.get("key"),
            "label": row.get("label"),
            "score": row.get("score"),
            "search_term": TOPIC_SEARCH_TERMS.get(row.get("key"), row.get("label") or ""),
        }
        for row in (external.get("topics") or [])[:6]
    ]
    weak_topics = [
        {"topic": topic, "weight": weight, "label": format_topic(topic)}
        for topic, weight in topic_weights.items()
        if weight <= 0.55
    ][:6]
    return {
        "lane_keywords": lane_keywords,
        "lane_focus_topics": lane_focus_topics,
        "hot_external_topics": hot_topics,
        "low_priority_topics": weak_topics,
        "candidate_scoring": {
            "topic_weight": "multiply candidate relevance by topic_weights[topic]",
            "strategy_weight": "multiply lane priority by strategy_weights[strategy]",
            "external_velocity": "add view/comment/source bonus for YouTube, TikTok, Google Trends and social sources",
            "lane_guardrail": "do not let entertainment topics override tech lanes unless the lane itself is entertainment",
        },
    }


def build_editor_recommendations(internal: dict[str, Any], external: dict[str, Any], weights: dict[str, Any]) -> list[dict[str, Any]]:
    recs: list[dict[str, Any]] = []
    top_external = external.get("topics", [])[:4]
    top_internal = internal.get("by_topic", [])[:4]
    weak_internal = [row for row in internal.get("by_topic", []) if internal.get("baseline_views") and row.get("avg_views", 0) < internal["baseline_views"] * 0.55]
    best_strategy = (weights.get("recommended_mix") or [{}])[0].get("strategy")

    if best_strategy:
        recs.append({
            "type": "mix",
            "title": f"明日主軸先押 {best_strategy}",
            "reason": "綜合自己的影片表現與外部熱度後，這個 strategy 目前權重最高。",
            "action": f"autopilot 選題時提高 {best_strategy} 的優先序。",
        })
    if top_external:
        labels = "、".join(row["label"] for row in top_external[:3])
        recs.append({
            "type": "trend",
            "title": f"外部正在升溫：{labels}",
            "reason": "YouTube/TikTok/Google/社群訊號集中在這些題材。",
            "action": "科技新聞與科技判讀優先找能連到這些題材的角度。",
        })
    if top_internal:
        winner = top_internal[0]
        recs.append({
            "type": "internal",
            "title": f"自己的帳號目前最吃：{winner['label']}",
            "reason": f"近期平均 {winner['avg_views']} views，樣本 {winner['videos']} 支。",
            "action": "保留同類題材，但換 hook / 封面做變體，不要只重複同一個句型。",
        })
    if weak_internal:
        weak = weak_internal[0]
        recs.append({
            "type": "risk",
            "title": f"減量觀察：{weak['label']}",
            "reason": f"平均 views 低於近期 baseline 太多，目前是 {weak['avg_views']} views。",
            "action": "除非外部趨勢很強，否則少排或改成判讀型/名人型包裝。",
        })

    style_signals = external.get("style_signals") or []
    if style_signals:
        names = ", ".join(s["key"] for s in style_signals[:3])
        recs.append({
            "type": "style",
            "title": "剪輯手法雷達有新訊號",
            "reason": f"外部內容反覆提到：{names}。",
            "action": "下一支樣片優先測：大標題更明確、字幕更靠中、每 1.5-2 秒視覺變化。",
        })
    return recs


def _read_job_news(date: str, job_id: int) -> dict[str, Any]:
    return read_json(PIPELINE_DIR / (date or "").replace("\\", "/").strip("/") / f"job_{job_id}" / "news.json", {})


def _read_job_schedule(date: str, job_id: int) -> list[dict[str, Any]]:
    data = read_json(PIPELINE_DIR / (date or "").replace("\\", "/").strip("/") / f"job_{job_id}" / "schedule_log.json", [])
    return data if isinstance(data, list) else []


def _daily_job_rows(date_key: str) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id AS job_id, date, topic, status, triggered_by, platforms,
                   step_upload, created_at, finished_at, error
            FROM jobs
            WHERE date=?
            ORDER BY id
            """,
            (date_key,),
        ).fetchall()
        stats = conn.execute(
            """
            SELECT job_id, platform, views, likes, comments, shares, platform_url
            FROM video_stats
            WHERE job_id IN (
                SELECT id FROM jobs WHERE date=?
            )
            """,
            (date_key,),
        ).fetchall()
    stats_by_job: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in stats:
        stats_by_job[int(row["job_id"])].append(dict(row))
    out = []
    for row in rows:
        item = dict(row)
        item["stats"] = stats_by_job.get(int(row["job_id"]), [])
        out.append(item)
    return out


def collect_daily_briefing(
    internal: dict[str, Any],
    external: dict[str, Any],
    weights: dict[str, Any],
    recommendations: list[dict[str, Any]],
    settings: dict[str, str],
    *,
    date_key: str | None = None,
) -> dict[str, Any]:
    date_key = date_key or today_key()
    jobs = []
    failed_jobs = []
    platform_summary: dict[str, dict[str, Any]] = defaultdict(lambda: {"scheduled": 0, "uploaded": 0, "views": 0, "jobs": []})

    for row in _daily_job_rows(date_key):
        news = _read_job_news(row.get("date") or date_key, int(row["job_id"]))
        items = news.get("items") if isinstance(news.get("items"), list) else []
        first = items[0] if items and isinstance(items[0], dict) else {}
        directive = news.get("media_ops_creative_directive") if isinstance(news.get("media_ops_creative_directive"), dict) else {}
        schedule = _read_job_schedule(row.get("date") or date_key, int(row["job_id"]))
        stats = row.get("stats") or []
        stats_by_platform = {s.get("platform"): s for s in stats}

        platform_entries = []
        if schedule:
            for ent in schedule:
                platform = ent.get("platform") or "unknown"
                stat = stats_by_platform.get(platform) or {}
                views = as_int(stat.get("views"))
                platform_entries.append({
                    "platform": platform,
                    "profile": ent.get("profile") or news.get("account_profile") or "",
                    "scheduled_date": ent.get("scheduled_date") or "",
                    "video_version": ent.get("video_version") or "",
                    "status": ent.get("status") or "",
                    "request_id": ent.get("request_id") or "",
                    "views": views,
                    "likes": as_int(stat.get("likes")),
                    "comments": as_int(stat.get("comments")),
                    "shares": as_int(stat.get("shares")),
                    "url": stat.get("platform_url") or "",
                })
                platform_summary[platform]["scheduled"] += 1
                if ent.get("status") == "uploaded":
                    platform_summary[platform]["uploaded"] += 1
                platform_summary[platform]["views"] += views
                platform_summary[platform]["jobs"].append(int(row["job_id"]))
        else:
            for platform in [p.strip() for p in str(row.get("platforms") or "").split(",") if p.strip()]:
                platform_entries.append({
                    "platform": platform,
                    "profile": news.get("account_profile") or "",
                    "scheduled_date": "",
                    "video_version": "",
                    "status": "not_scheduled",
                    "request_id": "",
                    "views": 0,
                    "likes": 0,
                    "comments": 0,
                    "shares": 0,
                    "url": "",
                })

        job_entry = {
            "job_id": int(row["job_id"]),
            "date": row.get("date") or date_key,
            "title": first.get("title") or row.get("topic") or "(untitled)",
            "hook": first.get("hook") or "",
            "strategy": (news.get("strategy") or "generic").lower(),
            "account_profile": news.get("account_profile") or "",
            "status": row.get("status") or "",
            "triggered_by": row.get("triggered_by") or "",
            "editing_style": first.get("media_ops_editing_style") or news.get("editing_style") or directive.get("editing_style") or "",
            "hook_pattern": first.get("hook_pattern") or "",
            "bgm_emotion": first.get("emotion") or "",
            "decision_reason": _job_decision_reason(news, directive, weights),
            "platforms": platform_entries,
            "total_views": sum(as_int(s.get("views")) for s in stats),
            "total_engagements": sum(as_int(s.get("likes")) + as_int(s.get("comments")) + as_int(s.get("shares")) for s in stats),
            "error": row.get("error") or "",
        }
        jobs.append(job_entry)
        if str(row.get("status") or "").lower() == "failed":
            failed_jobs.append({
                "job_id": int(row["job_id"]),
                "date": row.get("date") or date_key,
                "title": job_entry["title"],
                "strategy": job_entry["strategy"],
                "triggered_by": row.get("triggered_by") or "",
                "error": row.get("error") or "",
            })

    platform_rows = [
        {"platform": platform, **value, "jobs": sorted(set(value["jobs"]))}
        for platform, value in sorted(platform_summary.items())
    ]
    decisions = build_daily_decisions(weights, recommendations, internal, external)
    brief = {
        "date": date_key,
        "generated_at": now_iso(),
        "jobs": jobs,
        "failed_jobs": failed_jobs,
        "platform_summary": platform_rows,
        "decisions": decisions,
        "guardrails": [
            "科技新聞暫不發 TikTok，避免恢復期被判 AI 快訊號。",
            "科技判讀與娛樂可發 TikTok，用原創評論/娛樂語境測復健。",
            "科技名人解析不發 LinkedIn/TikTok，避免像搬運剪輯號。",
            "Media Ops 可放行 missing screenshot 這類軟性問題，但 paywall/login/popup 仍擋。"
        ],
        "next_actions": [rec.get("action") for rec in recommendations[:4] if rec.get("action")],
        "markdown": "",
    }
    brief["markdown"] = render_daily_briefing_markdown(brief)
    write_json(DAILY_BRIEF_FILE, brief)
    DAILY_BRIEF_MD_FILE.write_text(brief["markdown"], encoding="utf-8")
    return brief


def _job_decision_reason(news: dict[str, Any], directive: dict[str, Any], weights: dict[str, Any]) -> str:
    strategy = (news.get("strategy") or "generic").lower()
    topics = (weights.get("direction") or {}).get("lane_focus_topics", {}).get(strategy) or []
    style = directive.get("editing_style") or news.get("editing_style") or ""
    if topics:
        return f"Media Ops focus={', '.join(topics[:3])}; style={style or 'default'}"
    return f"Media Ops style={style or 'default'}; lane guardrails applied"


def build_daily_decisions(weights: dict[str, Any], recommendations: list[dict[str, Any]], internal: dict[str, Any], external: dict[str, Any]) -> list[dict[str, Any]]:
    decisions: list[dict[str, Any]] = []
    for lane, item in (weights.get("lane_actions") or {}).items():
        if not isinstance(item, dict):
            continue
        action = item.get("action") or "keep"
        decisions.append({
            "type": "lane_action",
            "title": f"{lane}: {action}",
            "reason": item.get("reason") or "",
            "action": f"cadence_days={item.get('cadence_days', 1)}; daily_quota={item.get('daily_quota', 1)}",
        })
    for lane, platforms in (weights.get("platform_actions") or {}).items():
        if not isinstance(platforms, dict):
            continue
        paused = sorted(
            platform
            for platform, item in platforms.items()
            if isinstance(item, dict) and str(item.get("action") or "").lower() == "pause"
        )
        boosted = sorted(
            platform
            for platform, item in platforms.items()
            if isinstance(item, dict) and str(item.get("action") or "").lower() == "boost"
        )
        if paused or boosted:
            decisions.append({
                "type": "platform_action",
                "title": f"{lane}: platform fan-out",
                "reason": f"pause={', '.join(paused) or '-'}; boost={', '.join(boosted) or '-'}",
                "action": "autopilot removes paused platforms before publishing",
            })
    for rec in recommendations[:5]:
        decisions.append({
            "type": rec.get("type") or "recommendation",
            "title": rec.get("title") or "",
            "reason": rec.get("reason") or "",
            "action": rec.get("action") or "",
        })
    directives = (weights.get("creative_directives") or {})
    for lane in ("tech", "tech_judgement", "figure_tech", "business_finance", "entertainment", "entertainment_storyboard"):
        d = directives.get(lane) or {}
        if not d:
            continue
        decisions.append({
            "type": "creative",
            "title": f"{lane}: {d.get('editing_style') or 'default'}",
            "reason": f"hook={', '.join((d.get('hook_patterns') or [])[:3])}; bgm={d.get('emotion') or 'default'}; cut={d.get('visual_change_seconds') or '-'}s",
            "action": d.get("thumbnail_brief") or "",
        })
    platform_rows = internal.get("by_platform") or []
    if platform_rows:
        best = platform_rows[0]
        decisions.append({
            "type": "platform",
            "title": f"目前最佳平台：{best.get('key')}",
            "reason": f"avg_views={best.get('avg_views')} / videos={best.get('videos')}",
            "action": "平台權重會分開看，不把 TikTok/YouTube/IG 混成同一個表現。",
        })
    return decisions


def render_daily_briefing_markdown(brief: dict[str, Any]) -> str:
    lines = [f"# Media Ops Daily Briefing - {brief.get('date')}", ""]
    jobs = brief.get("jobs") or []
    failed_jobs = brief.get("failed_jobs") or []
    lines.append(f"今天產出/追蹤：{len(jobs)} 支")
    if failed_jobs:
        lines.append(f"失敗需處理：{len(failed_jobs)} 支")
        for job in failed_jobs:
            error = compact_text(job.get("error"))[:180]
            lines.append(f"- Job #{job.get('job_id')} {job.get('strategy')}：{job.get('title')} | {error}")
        lines.append("")
    lines.append("")
    if jobs:
        lines.append("## 發布進度")
        for job in jobs:
            lines.append(f"- Job #{job['job_id']} [{job.get('strategy')}] {job.get('title')} - {job.get('status')}")
            lines.append(f"  - 為什麼：{job.get('decision_reason')}")
            plats = job.get("platforms") or []
            if plats:
                desc = ", ".join(
                    f"{p.get('platform')}:{p.get('status')}"
                    + (f"@{p.get('scheduled_date')}" if p.get("scheduled_date") else "")
                    for p in plats
                )
                lines.append(f"  - 平台：{desc}")
    lines.append("")
    lines.append("## 平台總覽")
    for row in brief.get("platform_summary") or []:
        lines.append(f"- {row.get('platform')}: uploaded {row.get('uploaded')}/{row.get('scheduled')}, views {row.get('views')}")
    lines.append("")
    lines.append("## 今日調整理由")
    for item in brief.get("decisions") or []:
        lines.append(f"- {item.get('title')}: {item.get('reason')}")
        if item.get("action"):
            lines.append(f"  - action: {item.get('action')}")
    lines.append("")
    lines.append("## Guardrails")
    for item in brief.get("guardrails") or []:
        lines.append(f"- {item}")
    return "\n".join(lines).strip() + "\n"


def maybe_send_daily_briefing(settings: dict[str, str], brief: dict[str, Any], *, force: bool = False) -> bool:
    if str(settings.get("media_ops_daily_report_telegram", "true")).lower() != "true":
        return False
    token = os.getenv("TELEGRAM_BOT_TOKEN") or settings.get("telegram_bot_token") or ""
    chat_ids = [c.strip() for c in (settings.get("telegram_chat_ids") or "").split(",") if c.strip()]
    if not token or not chat_ids:
        return False
    state = read_json(DAILY_BRIEF_STATE_FILE, {})
    date_key = brief.get("date") or today_key()
    if not force and state.get("last_sent_date") == date_key:
        return False
    text = _telegram_brief_text(brief)
    ok_any = False
    for chat_id in chat_ids:
        ok_any = _send_telegram_message(token, chat_id, text) or ok_any
    if ok_any:
        write_json(DAILY_BRIEF_STATE_FILE, {"last_sent_date": date_key, "sent_at": now_iso()})
    return ok_any


def maybe_send_failure_alerts(settings: dict[str, str], brief: dict[str, Any], *, force: bool = False) -> bool:
    failed_jobs = brief.get("failed_jobs") or []
    if not failed_jobs:
        return False
    if str(settings.get("media_ops_failure_alert_telegram", "true")).lower() != "true":
        return False
    token = os.getenv("TELEGRAM_BOT_TOKEN") or settings.get("telegram_bot_token") or ""
    chat_ids = [c.strip() for c in (settings.get("telegram_chat_ids") or "").split(",") if c.strip()]
    if not token or not chat_ids:
        return False

    state = read_json(FAILURE_ALERT_STATE_FILE, {})
    sent = set(state.get("sent_failed_job_ids") or [])
    pending = [j for j in failed_jobs if force or int(j.get("job_id") or 0) not in sent]
    if not pending:
        return False

    lines = [f"Media Ops failure alert {brief.get('date')}", ""]
    for job in pending[:8]:
        error = compact_text(job.get("error"))[:280]
        lines.append(f"Job #{job.get('job_id')} {job.get('strategy')} - {job.get('title')}")
        lines.append(error or "No error text recorded.")
        lines.append("")
    text = "\n".join(lines).strip()[:3900]
    ok_any = False
    for chat_id in chat_ids:
        ok_any = _send_telegram_message(token, chat_id, text) or ok_any
    if ok_any:
        sent.update(int(j.get("job_id") or 0) for j in pending)
        write_json(FAILURE_ALERT_STATE_FILE, {"sent_failed_job_ids": sorted(sent), "sent_at": now_iso()})
    return ok_any


def _telegram_brief_text(brief: dict[str, Any]) -> str:
    lines = [f"Media Ops 日報 {brief.get('date')}", ""]
    for job in (brief.get("jobs") or [])[:8]:
        plats = ", ".join(p.get("platform") for p in job.get("platforms", []) if p.get("status") == "uploaded")
        lines.append(f"Job #{job.get('job_id')} {job.get('strategy')}｜{job.get('title')}")
        lines.append(f"平台：{plats or '尚未上傳'}")
        lines.append(f"原因：{job.get('decision_reason')}")
        lines.append("")
    if brief.get("decisions"):
        lines.append("調整理由：")
        for item in brief["decisions"][:5]:
            lines.append(f"- {item.get('title')}: {item.get('reason')}")
    return "\n".join(lines)[:3900]


def _send_telegram_message(token: str, chat_id: str, text: str) -> bool:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        return bool(result.get("ok"))
    except Exception:
        return False


def run_agent(
    refresh_trends: bool = True,
    refresh_analytics: bool = True,
    internal_limit: int = 200,
    trend_limit: int = 12,
    notify_daily_report: bool = False,
    force_notify_daily_report: bool = False,
    notify_failures: bool = False,
    force_notify_failures: bool = False,
) -> dict[str, Any]:
    settings = get_all_settings()
    analytics_refresh = refresh_smart_analytics() if refresh_analytics else {"ok": False, "skipped": True}
    internal_rows = load_internal_performance(limit=internal_limit)
    internal = summarize_internal(internal_rows)
    external_items = collect_external_trends(limit_per_source=trend_limit) if refresh_trends else read_json(REPORT_FILE, {}).get("external", {}).get("top_items", [])
    external = summarize_external(external_items)
    profile_analytics = fetch_upload_post_profile_analytics(settings)
    weights = build_strategy_weights(internal, external)
    recommendations = build_editor_recommendations(internal, external, weights)
    daily_briefing = collect_daily_briefing(internal, external, weights, recommendations, settings)
    daily_report_sent = maybe_send_daily_briefing(settings, daily_briefing, force=force_notify_daily_report) if notify_daily_report else False
    failure_alert_sent = maybe_send_failure_alerts(settings, daily_briefing, force=force_notify_failures) if notify_failures else False

    report = {
        "generated_at": now_iso(),
        "version": 1,
        "scope": "internal_performance + external_trend_radar + strategy_weights + creative_directives",
        "internal": internal,
        "analytics_refresh": analytics_refresh,
        "external": external,
        "profile_analytics": profile_analytics,
        "strategy": weights,
        "recommendations": recommendations,
        "daily_briefing": daily_briefing,
        "daily_report_sent": daily_report_sent,
        "failure_alert_sent": failure_alert_sent,
        "sources": [
            {"name": "Upload-Post Analytics", "url": "https://docs.upload-post.com/api/get-analytics/"},
            {"name": "YouTube Data API mostPopular", "url": "https://developers.google.com/youtube/v3/guides/implementation/videos"},
            {"name": "TikTok Creative Center Trends", "url": "https://ads.tiktok.com/help/article/how-to-use-trends?lang=en"},
            {"name": "Google Trends RSS", "url": "https://support.google.com/trends/answer/3076011?hl=en"},
        ],
    }
    write_json(REPORT_FILE, report)
    write_json(WEIGHTS_FILE, weights)
    return report


def refresh_smart_analytics(limit: int = 30, recent_days: int = 3, stale_hours: float = 4.0) -> dict[str, Any]:
    script = BASE_DIR / "scripts" / "analytics_fetcher.py"
    if not script.exists():
        return {"ok": False, "error": "analytics_fetcher.py missing"}
    args = [
        sys.executable,
        "-X",
        "utf8",
        str(script),
        "--smart",
        "--limit",
        str(limit),
        "--recent-days",
        str(recent_days),
        "--stale-hours",
        str(stale_hours),
    ]
    start = time.time()
    try:
        proc = subprocess.run(
            args,
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            timeout=420,
        )
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "seconds": round(time.time() - start, 1),
            "stdout_tail": (proc.stdout or "")[-500:],
            "stderr_tail": (proc.stderr or "")[-500:],
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout", "seconds": round(time.time() - start, 1)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:240], "seconds": round(time.time() - start, 1)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-refresh-trends", action="store_true", help="reuse cached external items when possible")
    parser.add_argument("--no-refresh-analytics", action="store_true", help="do not run smart analytics refresh before strategy calculation")
    parser.add_argument("--internal-limit", type=int, default=200)
    parser.add_argument("--trend-limit", type=int, default=12)
    parser.add_argument("--notify-daily-report", action="store_true")
    parser.add_argument("--force-notify-daily-report", action="store_true")
    parser.add_argument("--notify-failures", action="store_true")
    parser.add_argument("--force-notify-failures", action="store_true")
    args = parser.parse_args()
    start = time.time()
    report = run_agent(
        refresh_trends=not args.no_refresh_trends,
        refresh_analytics=not args.no_refresh_analytics,
        internal_limit=args.internal_limit,
        trend_limit=args.trend_limit,
        notify_daily_report=args.notify_daily_report,
        force_notify_daily_report=args.force_notify_daily_report,
        notify_failures=args.notify_failures,
        force_notify_failures=args.force_notify_failures,
    )
    print(json.dumps({
        "ok": True,
        "report": str(REPORT_FILE),
        "weights": str(WEIGHTS_FILE),
        "recommendations": len(report.get("recommendations") or []),
        "external_items": report.get("external", {}).get("item_count", 0),
        "daily_report_sent": report.get("daily_report_sent", False),
        "failure_alert_sent": report.get("failure_alert_sent", False),
        "seconds": round(time.time() - start, 1),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
