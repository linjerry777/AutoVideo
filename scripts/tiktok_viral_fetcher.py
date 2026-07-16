#!/usr/bin/env python3
"""Fetch high-view TikTok video candidates for AutoVideo trend research.

This module collects metadata only. It deliberately does not download, mirror,
frame, or transform source TikTok videos. Downstream lanes can use these rows as
trend signals for commentary, original remakes, or licensed workflows.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
from pathlib import Path
from typing import Any, Callable
from urllib.request import Request, urlopen


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_URL = "https://ads.tiktok.com/business/creativecenter/inspiration/popular/pc/en"
TRENDING_HASHTAG_URL = "https://ads.tiktok.com/creative/creativeCenter/trends/hashtag"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

VIEW_KEYS = ("play_count", "playCount", "view_count", "viewCount", "views", "videoViews", "showCnt", "playCnt")
LIKE_KEYS = ("digg_count", "diggCount", "like_count", "likeCount", "likes", "liked", "likeCnt")
COMMENT_KEYS = ("comment_count", "commentCount", "comments", "commentCnt")
SHARE_KEYS = ("share_count", "shareCount", "shares", "shareCnt")
ID_KEYS = ("item_id", "itemId", "video_id", "videoId", "aweme_id", "awemeId", "id")
TITLE_KEYS = ("desc", "title", "description", "video_title", "videoTitle", "ad_title", "adTitle")
URL_KEYS = ("share_url", "shareUrl", "item_url", "itemUrl", "url", "link", "webVideoUrl", "videoUrl")
COVER_KEYS = ("cover", "cover_url", "coverUrl", "cover_image_url", "thumbnail", "thumbnail_url", "imageUrl")
HASHTAG_ID_KEYS = ("hashtagID", "hashtagId", "hashtag_id")
HASHTAG_NAME_KEYS = ("hashtagName", "hashtag_name", "challengeName", "challenge_name")
POST_KEYS = ("publishCnt", "publish_count", "post_count", "postCount")


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _as_int(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip().lower().replace(",", "")
    if not text:
        return 0
    multiplier = 1
    if text.endswith("k"):
        multiplier = 1_000
        text = text[:-1]
    elif text.endswith("m"):
        multiplier = 1_000_000
        text = text[:-1]
    elif text.endswith("b"):
        multiplier = 1_000_000_000
        text = text[:-1]
    match = re.search(r"\d+(?:\.\d+)?", text)
    if not match:
        return 0
    return int(float(match.group(0)) * multiplier)


def _first(row: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in row and row.get(key) not in (None, ""):
            return row.get(key)
    return None


def _nested_first(value: Any, keys: tuple[str, ...]) -> Any:
    if isinstance(value, dict):
        direct = _first(value, keys)
        if direct not in (None, ""):
            return direct
        for child in value.values():
            found = _nested_first(child, keys)
            if found not in (None, ""):
                return found
    elif isinstance(value, list):
        for child in value:
            found = _nested_first(child, keys)
            if found not in (None, ""):
                return found
    return None


def _creator(row: dict[str, Any]) -> str:
    for key in ("nickname", "creator", "author_name", "authorName", "user_name", "username"):
        value = row.get(key)
        if value:
            return str(value)
    for key in ("author", "user", "account"):
        value = row.get(key)
        if isinstance(value, dict):
            nested = _creator(value)
            if nested:
                return nested
    return ""


def _cover(row: dict[str, Any]) -> str:
    value = _nested_first(row, COVER_KEYS)
    if isinstance(value, dict):
        value = _nested_first(value, ("url", "uri", "coverUrl"))
    if isinstance(value, list):
        value = value[0] if value else ""
    return str(value or "")


def _video_url(row: dict[str, Any], video_id: str) -> str:
    value = _nested_first(row, URL_KEYS)
    if isinstance(value, list):
        value = value[0] if value else ""
    url = str(value or "")
    if url.startswith("http"):
        return url
    author = _creator(row).strip("@")
    if video_id and author:
        return f"https://www.tiktok.com/@{author}/video/{video_id}"
    if video_id:
        return f"https://www.tiktok.com/@unknown/video/{video_id}"
    return ""


def _is_video_row(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    has_title = _first(value, TITLE_KEYS) not in (None, "")
    has_id = _first(value, ID_KEYS) not in (None, "")
    has_views = _nested_first(value, VIEW_KEYS) not in (None, "")
    has_social = any(_nested_first(value, keys) not in (None, "") for keys in (LIKE_KEYS, COMMENT_KEYS, SHARE_KEYS))
    return bool((has_id or has_title) and (has_views or has_social))


def extract_video_rows(data: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            if _is_video_row(value):
                rows.append(value)
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(data)
    deduped: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(_first(row, ID_KEYS) or _first(row, URL_KEYS) or _first(row, TITLE_KEYS) or id(row))
        deduped.setdefault(key, row)
    return list(deduped.values())


def _is_hashtag_row(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    has_name = _first(value, HASHTAG_NAME_KEYS) not in (None, "")
    has_id = _first(value, HASHTAG_ID_KEYS) not in (None, "")
    has_views = _nested_first(value, ("vv", *VIEW_KEYS)) not in (None, "")
    return bool((has_name or has_id) and has_views)


def extract_hashtag_rows(data: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            if _is_hashtag_row(value):
                rows.append(value)
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(data)
    deduped: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(_first(row, HASHTAG_ID_KEYS) or _first(row, HASHTAG_NAME_KEYS) or id(row))
        deduped.setdefault(key, row)
    return list(deduped.values())


def normalize_video(row: dict[str, Any], rank: int, region: str, period: str) -> dict[str, Any]:
    video_id = str(_first(row, ID_KEYS) or "").strip()
    title = str(_first(row, TITLE_KEYS) or "TikTok viral video").strip()
    views = _as_int(_nested_first(row, VIEW_KEYS))
    likes = _as_int(_nested_first(row, LIKE_KEYS))
    comments = _as_int(_nested_first(row, COMMENT_KEYS))
    shares = _as_int(_nested_first(row, SHARE_KEYS))
    engagement = likes + comments * 3 + shares * 4
    virality = min(100, int(math.log10(max(views, 10)) * 12 + math.log10(max(engagement, 10)) * 8))
    url = _video_url(row, video_id)
    creator = _creator(row)
    summary = f"TikTok high-view candidate: {views:,} views"
    if creator:
        summary += f" by {creator}"
    return {
        "title": title[:160],
        "summary": summary,
        "url": url,
        "source_url": url,
        "source": f"TikTok viral video ({region}, {period}d)",
        "source_name": "TikTok Creative Center",
        "source_type": "tiktok_viral",
        "platform": "tiktok",
        "tiktok_video_id": video_id,
        "tiktok_creator": creator,
        "tiktok_rank": rank,
        "tiktok_region": region,
        "tiktok_period_days": period,
        "view_count": views,
        "like_count": likes,
        "comment_count": comments,
        "share_count": shares,
        "cover_url": _cover(row),
        "media_ops_topic": "internet_culture",
        "media_ops_cluster": f"tiktok_viral:{creator.lower() or 'unknown'}",
        "media_ops_source_key": "tiktok_viral",
        "media_ops_virality_score": virality,
        "rights_status": "external_reference_only",
        "reuse_policy": "metadata_only_no_reupload",
    }


def rank_videos(
    rows: list[dict[str, Any]],
    *,
    limit: int,
    min_views: int,
    region: str,
    period: str,
) -> list[dict[str, Any]]:
    normalized = [
        normalize_video(row, rank=idx, region=region, period=period)
        for idx, row in enumerate(rows, start=1)
    ]
    filtered = [item for item in normalized if int(item.get("view_count") or 0) >= min_views]
    filtered.sort(
        key=lambda item: (
            int(item.get("view_count") or 0),
            int(item.get("like_count") or 0) + int(item.get("share_count") or 0) * 4,
        ),
        reverse=True,
    )
    for idx, item in enumerate(filtered, start=1):
        item["tiktok_rank"] = idx
    return filtered[:limit]


def normalize_hashtag_topic(row: dict[str, Any], rank: int, region: str, period: str) -> dict[str, Any]:
    hashtag_id = str(_first(row, HASHTAG_ID_KEYS) or "").strip()
    hashtag_name = str(_first(row, HASHTAG_NAME_KEYS) or "tiktok").strip().lstrip("#")
    views = _as_int(_nested_first(row, ("vv", *VIEW_KEYS)))
    posts = _as_int(_nested_first(row, POST_KEYS))
    top_creators = row.get("topCreators") if isinstance(row.get("topCreators"), list) else []
    creator_names = [
        str(creator.get("handleName") or creator.get("nickname") or "").strip()
        for creator in top_creators
        if isinstance(creator, dict)
    ]
    creator_names = [name for name in creator_names if name][:3]
    title = f"#{hashtag_name} is trending on TikTok"
    summary = f"TikTok high-view topic: {views:,} views"
    if posts:
        summary += f", {posts:,} posts"
    if creator_names:
        summary += f"; top creators: {', '.join(creator_names)}"
    url = f"{TRENDING_HASHTAG_URL}/{hashtag_name}?countryCode={region}&period={period}"
    virality = min(100, int(math.log10(max(views, 10)) * 14 + math.log10(max(posts, 10)) * 6))
    return {
        "title": title[:160],
        "summary": summary,
        "url": url,
        "source_url": url,
        "source": f"TikTok viral topic ({region}, {period}d)",
        "source_name": "TikTok Creative Center",
        "source_type": "tiktok_viral_topic",
        "platform": "tiktok",
        "tiktok_hashtag_id": hashtag_id,
        "tiktok_hashtag": hashtag_name,
        "tiktok_rank": rank,
        "tiktok_region": region,
        "tiktok_period_days": period,
        "view_count": views,
        "post_count": posts,
        "tiktok_top_creators": creator_names,
        "media_ops_topic": "internet_culture",
        "media_ops_cluster": f"tiktok_viral_topic:{hashtag_name.lower()}",
        "media_ops_source_key": "tiktok_viral",
        "media_ops_virality_score": virality,
        "rights_status": "external_reference_only",
        "reuse_policy": "metadata_only_no_reupload",
    }


def rank_hashtag_topics(
    rows: list[dict[str, Any]],
    *,
    limit: int,
    min_views: int,
    region: str,
    period: str,
) -> list[dict[str, Any]]:
    normalized = [
        normalize_hashtag_topic(row, rank=idx, region=region, period=period)
        for idx, row in enumerate(rows, start=1)
    ]
    filtered = [item for item in normalized if int(item.get("view_count") or 0) >= min_views]
    filtered.sort(
        key=lambda item: (
            int(item.get("view_count") or 0),
            int(item.get("post_count") or 0),
        ),
        reverse=True,
    )
    for idx, item in enumerate(filtered, start=1):
        item["tiktok_rank"] = idx
    return filtered[:limit]


def _fetch_html(url: str) -> str:
    req = Request(url, headers={"User-Agent": UA})
    with urlopen(req, timeout=35) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _extract_json_script(html: str, script_id: str) -> Any | None:
    pattern = rf'<script[^>]+id="{re.escape(script_id)}"[^>]*>(.*?)</script>'
    match = re.search(pattern, html, re.S)
    if not match:
        return None
    body = match.group(1).strip()
    if not body:
        return None
    return json.loads(body)


def _extract_page_data(html: str) -> dict[str, Any]:
    """Return every known server-rendered data blob from TikTok's page shell."""
    data: dict[str, Any] = {}
    for script_id in ("__NEXT_DATA__", "__MODERN_ROUTER_DATA__", "__MODERN_SSR_DATA__"):
        value = _extract_json_script(html, script_id)
        if value is not None:
            data[script_id] = value
    return data


def collect_viral_videos(
    *,
    region: str = "TW",
    period: str = "7",
    limit: int = 20,
    min_views: int = 100_000,
    fetch_html: Callable[[str], str] | None = None,
) -> list[dict[str, Any]]:
    fetch = fetch_html or _fetch_html
    url = f"{DEFAULT_URL}?countryCode={region}&period={period}"
    html = fetch(url)
    data = _extract_page_data(html)
    rows = extract_video_rows(data)
    if rows:
        return rank_videos(rows, limit=limit, min_views=min_views, region=region, period=period)

    topics = rank_hashtag_topics(
        extract_hashtag_rows(data),
        limit=limit,
        min_views=min_views,
        region=region,
        period=period,
    )
    if topics:
        return topics

    hashtag_url = f"{TRENDING_HASHTAG_URL}?countryCode={region}&period={period}"
    try:
        hashtag_data = _extract_page_data(fetch(hashtag_url))
    except Exception:
        return []
    hashtag_video_rows = extract_video_rows(hashtag_data)
    if hashtag_video_rows:
        return rank_videos(hashtag_video_rows, limit=limit, min_views=min_views, region=region, period=period)
    return rank_hashtag_topics(
        extract_hashtag_rows(hashtag_data),
        limit=limit,
        min_views=min_views,
        region=region,
        period=period,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", default="TW")
    parser.add_argument("--period", default="7", help="Creative Center period in days, usually 7/30/120")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--min-views", type=int, default=100_000)
    parser.add_argument("--save", action="store_true", help="write data/tiktok_viral_candidates.json")
    args = parser.parse_args()

    items = collect_viral_videos(
        region=args.region,
        period=args.period,
        limit=args.limit,
        min_views=args.min_views,
    )
    payload = {
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "source": "TikTok Creative Center high-traffic signals",
        "region": args.region,
        "period": args.period,
        "items": items,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if args.save:
        out = BASE_DIR / "data" / "tiktok_viral_candidates.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
