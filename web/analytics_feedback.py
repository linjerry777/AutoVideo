"""Experiment metadata and feedback summaries for video performance."""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
PIPELINE_DIR = BASE_DIR / "pipeline"
FEEDBACK_FILE = BASE_DIR / "data" / "analytics_feedback.json"


def _read_json(path: Path) -> dict:
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}
    return {}


def job_dir(date: str, job_id: int) -> Path:
    return PIPELINE_DIR / (date or "").replace("\\", "/").strip("/") / f"job_{job_id}"


def thumbnail_source(directory: Path) -> str:
    if not (directory / "thumbnail.png").exists():
        return "platform_frame"
    assets = directory / "assets"
    if (assets / "cover_image2.png").exists():
        return "image2"
    if (assets / "cover_frame.png").exists():
        return "video_frame"
    if (assets / "cover_fallback.png").exists():
        return "fallback"
    return "custom"


def experiment_meta_for_job(date: str, job_id: int) -> dict:
    directory = job_dir(date, job_id)
    news = _read_json(directory / "news.json")
    platform_meta = _read_json(directory / "platform_meta.json")
    items = news.get("items") or []
    first = items[0] if items and isinstance(items[0], dict) else {}
    trend_profile = news.get("shorts_trend_profile") or {}
    trend_rules = trend_profile.get("rules") if isinstance(trend_profile, dict) else {}
    if not isinstance(trend_rules, dict):
        trend_rules = {}
    youtube_meta = platform_meta.get("youtube") if isinstance(platform_meta.get("youtube"), dict) else {}
    instagram_meta = platform_meta.get("instagram") if isinstance(platform_meta.get("instagram"), dict) else {}

    return {
        "strategy": (news.get("strategy") or "generic").lower(),
        "first_title": first.get("title") or "",
        "first_summary": first.get("summary") or "",
        "media_ops_cluster": first.get("media_ops_cluster") or "",
        "media_ops_source_key": first.get("media_ops_source_key") or "",
        "media_ops_score": first.get("media_ops_score") or "",
        "media_ops_virality_score": first.get("media_ops_virality_score") or "",
        "layout_mode": news.get("layout_mode") or "",
        "editing_style": first.get("media_ops_editing_style") or news.get("editing_style") or "",
        "emotion": first.get("emotion") or "",
        "scene_type": first.get("scene_type") or "",
        "hook": first.get("hook") or "",
        "hook_pattern": first.get("hook_pattern") or "",
        "opening_label": first.get("opening_label") or "",
        "subtitle_bottom": first.get("subtitle_bottom") or "",
        "visual_change_seconds": first.get("visual_change_seconds") or trend_rules.get("visual_change_seconds") or "",
        "figure_name": first.get("figure_name") or news.get("figure_name") or "",
        "source_type": first.get("source_type") or first.get("source_name") or "",
        "thumbnail_style": "custom" if (directory / "thumbnail.png").exists() else "platform_frame",
        "thumbnail_source": thumbnail_source(directory),
        "youtube_custom_cover": bool(youtube_meta.get("use_auto_thumbnail", True)),
        "instagram_custom_cover": bool(instagram_meta.get("use_auto_thumbnail", True)),
        "youtube_title": youtube_meta.get("title", ""),
        "instagram_first_comment": instagram_meta.get("first_comment", ""),
    }


def write_feedback(rows: list[dict], output_path: Path = FEEDBACK_FILE) -> dict:
    """Write aggregate performance grouped by experiment dimensions."""
    groups: dict[str, dict] = defaultdict(lambda: {"videos": 0, "views": 0, "best_job_id": None, "best_views": -1})
    for row in rows:
        meta = row.get("experiment_meta") or {}
        views = int(row.get("total_views") or 0)
        keys = [
            f"strategy:{meta.get('strategy') or 'generic'}",
            f"hook_pattern:{meta.get('hook_pattern') or 'unknown'}",
            f"layout:{meta.get('layout_mode') or 'unknown'}",
            f"editing_style:{meta.get('editing_style') or 'unknown'}",
            f"emotion:{meta.get('emotion') or 'unknown'}",
            f"scene_type:{meta.get('scene_type') or 'unknown'}",
            f"thumbnail:{meta.get('thumbnail_style') or 'unknown'}",
            f"thumbnail_source:{meta.get('thumbnail_source') or 'unknown'}",
            f"cluster:{meta.get('media_ops_cluster') or 'unknown'}",
            f"source:{meta.get('media_ops_source_key') or meta.get('source_type') or 'unknown'}",
        ]
        for key in keys:
            item = groups[key]
            item["videos"] += 1
            item["views"] += views
            if views > item["best_views"]:
                item["best_views"] = views
                item["best_job_id"] = row.get("job_id")

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "groups": {
            key: {
                **value,
                "avg_views": round(value["views"] / value["videos"]) if value["videos"] else 0,
            }
            for key, value in sorted(groups.items())
        },
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def load_feedback(path: Path = FEEDBACK_FILE) -> dict:
    return _read_json(path)
