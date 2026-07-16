"""APScheduler wiring for AutoVideo autopilot.

The active daily flow is intentionally small:
1. news autopilot
2. entertainment/trending autopilot
3. tech figure source-video analysis

Older strategy metadata such as ``figure_entertainment`` remains available in
routes and publisher metadata for historical jobs, but the scheduler no longer
creates entertainment figure jobs automatically.
"""

from __future__ import annotations

import logging
import re
import subprocess
import sys
from datetime import date as date_cls
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler

from web import job_runner, media_ops_strategy
from web.db import create_job, get_setting, count_jobs_for_date_trigger

log = logging.getLogger("scheduler_service")

_scheduler = BackgroundScheduler()

_DEFAULT_PLATFORMS = "youtube,instagram,facebook,threads,x"
_AUTOPILOT_EXCLUDED_PLATFORMS = {"linkedin", "tiktok"}
_TECH_NEWS_EXCLUDED_PLATFORMS = {"tiktok"}
_FIGURE_TECH_EXCLUDED_PLATFORMS = {"linkedin", "tiktok"}
_DEFAULT_NEWS_SOURCES = "google,bing,hackernews,ithome,last30days"
_DEFAULT_NEWS_KEYWORDS = (
    "AI,ChatGPT,Claude,Gemini,LLM,agent,agents,GPU,Nvidia,OpenAI,"
    "Anthropic,Meta,Google,Microsoft"
)
_DEFAULT_BUSINESS_FINANCE_SOURCES = "google,bing,hackernews,ithome,last30days"
_DEFAULT_BUSINESS_FINANCE_KEYWORDS = "AI business model,科技財經,商業模式,企業合約,訂閱制"
_BASE_DIR = Path(__file__).resolve().parents[1]
_MEDIA_OPS_SCRIPT = _BASE_DIR / "scripts" / "media_ops_agent.py"
_STORYBOARD_SCRIPT = _BASE_DIR / "scripts" / "entertainment_storyboard_agent.py"


def _bool_setting(key: str, default: bool) -> bool:
    return str(get_setting(key, str(default).lower())).lower() == "true"


def _csv_setting(key: str, default: str) -> list[str]:
    raw = get_setting(key, default) or default
    return [item.strip() for item in raw.split(",") if item.strip()]


def _without_figure_excluded_platforms(platforms: list[str]) -> list[str]:
    return [p for p in platforms if p not in _FIGURE_TECH_EXCLUDED_PLATFORMS]


def _platforms_for_lane(platforms: list[str], lane: str) -> list[str]:
    lane = (lane or "").lower()
    strategy = "tech" if lane in {"news", "autopilot_news", "generic"} else lane
    platforms = [p for p in platforms if p not in _AUTOPILOT_EXCLUDED_PLATFORMS]
    if lane in {"tech", "news", "autopilot_news"}:
        platforms = [p for p in platforms if p not in _TECH_NEWS_EXCLUDED_PLATFORMS]
    elif lane == "figure_tech":
        platforms = _without_figure_excluded_platforms(platforms)
    weights = media_ops_strategy.load_weights()
    filtered = media_ops_strategy.filter_platforms(strategy, platforms, weights)
    if filtered != platforms:
        log.info("[media-ops] platforms lane=%s before=%s after=%s", lane, platforms, filtered)
    return filtered


def _media_ops_enabled() -> bool:
    return _bool_setting("media_ops_agent_enabled", True)


def _lane_count(today: str, triggered_by: str) -> int:
    return count_jobs_for_date_trigger(today, triggered_by)


def _lane_already_created(today: str, triggered_by: str) -> bool:
    return _lane_count(today, triggered_by) > 0


def _run_media_ops_agent_background(*, notify_daily_report: bool = False, notify_failures: bool = False) -> None:
    if not _media_ops_enabled():
        return
    if not _MEDIA_OPS_SCRIPT.exists():
        log.warning("[media-ops] script missing: %s", _MEDIA_OPS_SCRIPT)
        return
    try:
        args = [sys.executable, "-X", "utf8", str(_MEDIA_OPS_SCRIPT), "--trend-limit", "8", "--internal-limit", "200"]
        if notify_daily_report:
            args.extend(["--no-refresh-trends", "--notify-daily-report"])
        if notify_failures:
            args.extend(["--no-refresh-trends", "--no-refresh-analytics", "--notify-failures"])
        subprocess.Popen(
            args,
            cwd=str(_BASE_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        log.info("[media-ops] background analysis started")
    except Exception as exc:
        log.warning("[media-ops] start failed: %s", exc)


def _run_media_ops_daily_report_background() -> None:
    _run_media_ops_agent_background(notify_daily_report=True)


def _run_media_ops_failure_watchdog_background() -> None:
    _run_media_ops_agent_background(notify_failures=True)


def _run_storyboard_agent_background() -> None:
    if not _bool_setting("autopilot_enabled", False):
        return
    if not _bool_setting("autopilot_storyboard_enabled", True):
        return
    if not _STORYBOARD_SCRIPT.exists():
        log.warning("[storyboard] script missing: %s", _STORYBOARD_SCRIPT)
        return
    limit = get_setting("autopilot_storyboard_daily_candidates", "5") or "5"
    try:
        subprocess.Popen(
            [sys.executable, "-X", "utf8", str(_STORYBOARD_SCRIPT), "--limit", str(limit), "--no-images"],
            cwd=str(_BASE_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        log.info("[storyboard] background source search started limit=%s", limit)
    except Exception as exc:
        log.warning("[storyboard] start failed: %s", exc)


def _keyword_matcher(keywords: list[str]):
    english = [k for k in keywords if re.fullmatch(r"[A-Za-z0-9]+", k)]
    non_english = [k for k in keywords if k not in english]
    pattern = (
        re.compile(r"\b(" + "|".join(re.escape(k) for k in english) + r")\b", re.IGNORECASE)
        if english
        else None
    )

    def _matches(text: str) -> bool:
        if not text:
            return False
        if any(k in text for k in non_english):
            return True
        return bool(pattern and pattern.search(text))

    return _matches


def _pick_news_items(
    n: int = 3,
    strategy: str = "tech",
    skip_urls: set[str] | None = None,
    skip_clusters: set[str] | None = None,
) -> list[dict]:
    """Fetch multi-source AI news, filter weak matches, and skip used URLs."""
    try:
        from web.routes.news import _fetch_all, _load_used_urls
    except Exception as exc:
        log.warning("[autopilot] news fetch import failed: %s", exc)
        return []

    sources = _csv_setting("autopilot_news_sources", _DEFAULT_NEWS_SOURCES)
    keywords = _csv_setting("autopilot_news_keywords", _DEFAULT_NEWS_KEYWORDS)
    weights = media_ops_strategy.load_weights()
    search_keywords = media_ops_strategy.candidate_keywords(keywords[0] if keywords else "AI", strategy, weights, limit=3)
    raw: list[dict] = []
    seen_raw_urls: set[str] = set()
    for keyword in search_keywords:
        try:
            batch = _fetch_all(keyword=keyword, lang="zh-TW", sources=sources)
        except Exception as exc:
            log.warning("[autopilot] _fetch_all failed keyword=%s: %s", keyword, exc)
            continue
        for item in batch or []:
            url = item.get("url", "")
            if url and url not in seen_raw_urls:
                seen_raw_urls.add(url)
                raw.append(item)
    if not raw:
        return []

    matches = _keyword_matcher(keywords)
    used_urls = _load_used_urls()
    skip_urls = skip_urls or set()
    seen_urls: set[str] = set()
    candidates: list[dict] = []

    max_candidates = max(n * 20, 60)
    for item in raw:
        url = item.get("url", "")
        if not url or url in used_urls or url in skip_urls or url in seen_urls:
            continue
        haystack = f"{item.get('title', '')} {item.get('summary', '')}"
        if keywords and not matches(haystack):
            continue
        seen_urls.add(url)
        candidates.append(
            {
                "title": item.get("title", ""),
                "summary": item.get("summary", "") or item.get("title", ""),
                "url": url,
                "source": item.get("source", ""),
                "source_type": item.get("source_type", "google"),
                "view_count": item.get("view_count"),
                "comment_count": item.get("comment_count"),
            }
        )
        if len(candidates) >= max_candidates:
            break

    filtered = media_ops_strategy.select_diverse_candidates(candidates, strategy, n, weights, skip_clusters=skip_clusters)
    if not filtered:
        threshold = media_ops_strategy.candidate_threshold(strategy, weights)
        log.info(
            "[media-ops] no %s candidates passed quality gate threshold=%.1f candidates=%d skip_clusters=%s",
            strategy,
            threshold,
            len(candidates),
            sorted(skip_clusters or []),
        )
    return filtered[:n]


def _fire_news_autopilot(
    today: str,
    platforms: list[str],
    dry_run: bool,
    *,
    skip_urls: set[str] | None = None,
    skip_clusters: set[str] | None = None,
    triggered_by: str = "autopilot_news",
    schedule_offset_hours: int = 0,
) -> list[str]:
    strategy = get_setting("autopilot_news_strategy", "generic") or "generic"
    profile = get_setting("autopilot_news_profile", "pet") or "pet"
    platforms = _platforms_for_lane(platforms, strategy)
    items = _pick_news_items(n=3, strategy=strategy, skip_urls=skip_urls, skip_clusters=skip_clusters)
    if schedule_offset_hours and items:
        for item in items:
            item["media_ops_schedule_offset_hours"] = schedule_offset_hours
    if skip_clusters is not None:
        skip_clusters.update(str(item.get("media_ops_cluster") or "") for item in items if item.get("media_ops_cluster"))

    if items:
        job_id = create_job(date=today, triggered_by=triggered_by, platforms=",".join(platforms))
        log.info(
            "[autopilot] news job %s multi-source (%d items) strategy=%s profile=%s dry_run=%s",
            job_id,
            len(items),
            strategy,
            profile,
            dry_run,
        )
        pre_news = items
    else:
        log.info("[media-ops] skip %s: no candidates passed quality gate", triggered_by)
        return []

    job_runner.trigger_job(
        job_id=job_id,
        date=today,
        topic=None,
        platforms=platforms,
        dry_run=dry_run,
        pre_news=pre_news,
        account_profile=profile,
        strategy=strategy,
        autopilot=True,
    )
    return [item.get("url", "") for item in items if item.get("url")]


def _fire_news_autopilot_with_quota(today: str, platforms: list[str], dry_run: bool, strategy: str) -> None:
    weights = media_ops_strategy.load_weights()
    quota = media_ops_strategy.daily_quota(strategy, weights)
    if quota <= 0:
        log.info("[media-ops] news quota is 0; skipping strategy=%s", strategy)
        return
    existing_main = _lane_count(today, "autopilot_news")
    existing_boost = _lane_count(today, "autopilot_news_boost")
    if existing_main >= 1 and existing_boost >= max(0, quota - 1):
        log.info("[autopilot] news quota already filled for %s (main=%d boost=%d quota=%d)", today, existing_main, existing_boost, quota)
        return
    used_in_run: set[str] = set()
    used_clusters: set[str] = set()
    for idx in range(quota):
        triggered_by = "autopilot_news" if idx == 0 else "autopilot_news_boost"
        if idx == 0 and existing_main >= 1:
            log.info("[autopilot] skip duplicate %s for %s", triggered_by, today)
            continue
        if idx > 0 and existing_boost >= idx:
            log.info("[autopilot] skip duplicate %s #%d for %s", triggered_by, idx, today)
            continue
        urls = _fire_news_autopilot(
            today,
            platforms,
            dry_run,
            skip_urls=used_in_run,
            skip_clusters=used_clusters,
            triggered_by=triggered_by,
            schedule_offset_hours=idx,
        )
        if not urls:
            if idx > 0:
                log.info("[media-ops] news boost stopped; no more unique candidates")
            break
        used_in_run.update(urls)


def _fire_tech_judgement_autopilot(today: str, platforms: list[str], dry_run: bool) -> None:
    """Create one DORO tech-judgement job from the current news candidate pool."""
    if _lane_already_created(today, "autopilot_tech_judgement"):
        log.info("[autopilot] skip duplicate tech judgement for %s", today)
        return
    items = _pick_news_items(n=8, strategy="tech_judgement")
    if not items:
        log.info("[autopilot] tech judgement candidates empty; skipping")
        return

    profile = get_setting("autopilot_tech_judgement_profile", "yt") or "yt"
    platforms = _platforms_for_lane(platforms, "tech_judgement")
    job_id = create_job(
        date=today,
        triggered_by="autopilot_tech_judgement",
        topic="DORO 科技判讀",
        platforms=",".join(platforms),
    )
    log.info(
        "[autopilot] tech judgement job %s candidates=%d profile=%s dry_run=%s",
        job_id,
        len(items),
        profile,
        dry_run,
    )
    job_runner.trigger_job(
        job_id=job_id,
        date=today,
        topic="DORO 科技判讀",
        platforms=platforms,
        dry_run=dry_run,
        pre_news=items,
        account_profile=profile,
        strategy="tech_judgement",
        autopilot=True,
    )


def _pick_trending_items(n: int = 1) -> list[dict]:
    """Pick top trending items by view count across configured sources."""
    try:
        from web.routes.news import _fetch_all, _load_used_urls
    except Exception as exc:
        log.warning("[autopilot] trending fetch import failed: %s", exc)
        return []

    sources = _csv_setting("autopilot_trending_sources", "youtube_tw,youtube_us") or ["youtube_tw"]
    used_urls = _load_used_urls()
    seen_urls: set[str] = set()
    merged: list[dict] = []

    for source in sources:
        try:
            raw = _fetch_all(keyword="", lang="zh-TW", sources=[source])
        except Exception as exc:
            log.warning("[autopilot] trending fetch %s failed: %s", source, exc)
            continue
        for item in raw or []:
            url = item.get("url", "")
            if not url or url in used_urls or url in seen_urls:
                continue
            seen_urls.add(url)
            merged.append(item)

    weights = media_ops_strategy.load_weights()
    ranked = media_ops_strategy.filter_candidates(merged, "entertainment", weights)
    if not ranked:
        threshold = media_ops_strategy.candidate_threshold("entertainment", weights)
        log.info("[media-ops] no entertainment candidates passed quality gate threshold=%.1f candidates=%d", threshold, len(merged))
    return [
        {
            "title": item.get("title", ""),
            "summary": item.get("summary", "") or item.get("title", ""),
            "url": item.get("url", ""),
            "source": item.get("source", "YouTube"),
            "source_type": item.get("source_type", "youtube"),
            "view_count": item.get("view_count"),
            "media_ops_topic": item.get("media_ops_topic"),
            "media_ops_score": item.get("media_ops_score"),
            "media_ops_virality_score": item.get("media_ops_virality_score"),
        }
        for item in ranked[:n]
    ]


def _fire_trending_autopilot(today: str, platforms: list[str], dry_run: bool) -> None:
    if _lane_already_created(today, "autopilot_trending"):
        log.info("[autopilot] skip duplicate trending for %s", today)
        return
    items = _pick_trending_items(n=1)
    if not items:
        log.info("[autopilot] all configured trends already used; skipping trending job")
        return

    strategy = get_setting("autopilot_trending_strategy", "entertainment") or "entertainment"
    profile = get_setting("autopilot_trending_profile", "pet") or "pet"
    platforms = _platforms_for_lane(platforms, strategy)
    job_id = create_job(date=today, triggered_by="autopilot_trending", platforms=",".join(platforms))
    log.info(
        "[autopilot] trending job %s item=%s strategy=%s profile=%s dry_run=%s",
        job_id,
        items[0]["title"][:50],
        strategy,
        profile,
        dry_run,
    )
    job_runner.trigger_job(
        job_id=job_id,
        date=today,
        topic=None,
        platforms=platforms,
        dry_run=dry_run,
        pre_news=items,
        account_profile=profile,
        strategy=strategy,
        autopilot=True,
    )


def _fire_figure_autopilot(today: str, platforms: list[str], dry_run: bool) -> None:
    """Create one tech figure source-video quote-analysis job."""
    if _lane_already_created(today, "autopilot_figure_tech"):
        log.info("[autopilot] skip duplicate figure tech for %s", today)
        return
    strategy = "figure_tech"
    profile = get_setting("autopilot_figure_tech_profile", "yt") or "yt"
    platforms = _platforms_for_lane(platforms, strategy)
    topic = "科技大咖"
    job_id = create_job(
        date=today,
        triggered_by="autopilot_figure_tech",
        topic=topic,
        platforms=",".join(platforms),
    )
    log.info(
        "[autopilot] figure job %s strategy=%s profile=%s dry_run=%s",
        job_id,
        strategy,
        profile,
        dry_run,
    )
    job_runner.trigger_job(
        job_id=job_id,
        date=today,
        topic=topic,
        platforms=platforms,
        dry_run=dry_run,
        pre_news=None,
        account_profile=profile,
        strategy=strategy,
        autopilot=True,
    )


def _fire_business_finance_autopilot(today: str, platforms: list[str], dry_run: bool) -> None:
    """Create one business-model / market-risk analysis job."""
    if _lane_already_created(today, "autopilot_business_finance"):
        log.info("[autopilot] skip duplicate business finance for %s", today)
        return
    try:
        from scripts import business_finance_collector
    except Exception as exc:
        log.warning("[business_finance] collector import failed: %s", exc)
        return

    sources = _csv_setting("autopilot_business_finance_sources", _DEFAULT_BUSINESS_FINANCE_SOURCES)
    keywords = _csv_setting("autopilot_business_finance_keywords", _DEFAULT_BUSINESS_FINANCE_KEYWORDS)
    items = business_finance_collector.collect_candidates(keywords=keywords, sources=sources, limit=3)
    if not items:
        log.info("[business_finance] no candidates passed guardrails")
        return

    strategy = "business_finance"
    profile = get_setting("autopilot_business_finance_profile", "business") or "business"
    platforms = _platforms_for_lane(platforms, strategy)
    job_id = create_job(date=today, triggered_by="autopilot_business_finance", platforms=",".join(platforms))
    log.info(
        "[autopilot] business finance job %s candidates=%d profile=%s dry_run=%s",
        job_id,
        len(items),
        profile,
        dry_run,
    )
    job_runner.trigger_job(
        job_id=job_id,
        date=today,
        topic=None,
        platforms=platforms,
        dry_run=dry_run,
        pre_news=items,
        account_profile=profile,
        strategy=strategy,
        autopilot=True,
    )


def _read_autopilot_runtime_settings() -> tuple[str, list[str], bool]:
    today = date_cls.today().isoformat()
    platforms = _csv_setting("autopilot_platforms", _DEFAULT_PLATFORMS)
    dry_run = _bool_setting("autopilot_dry_run", True)
    return today, platforms, dry_run


def _media_ops_allows_lane(lane: str, today: str) -> bool:
    strategy = "tech" if lane in {"generic", "news", "autopilot_news"} else lane
    weights = media_ops_strategy.load_weights()
    allowed, reason = media_ops_strategy.should_run_lane(strategy, weights, today=today)
    if not allowed:
        log.info("[media-ops] skip lane=%s strategy=%s: %s", lane, strategy, reason)
    return allowed


def _news_cron_job() -> None:
    if not _bool_setting("autopilot_enabled", False):
        _legacy_daily()
        return
    if not _bool_setting("autopilot_news_enabled", True):
        return
    today, platforms, dry_run = _read_autopilot_runtime_settings()
    strategy = get_setting("autopilot_news_strategy", "generic") or "generic"
    if not _media_ops_allows_lane(strategy, today):
        return
    _fire_news_autopilot_with_quota(today, platforms, dry_run, strategy)


def _trending_cron_job() -> None:
    if not _bool_setting("autopilot_enabled", False):
        return
    if not _bool_setting("autopilot_trending_enabled", True):
        return
    today, platforms, dry_run = _read_autopilot_runtime_settings()
    if not _media_ops_allows_lane("entertainment", today):
        return
    _fire_trending_autopilot(today, platforms, dry_run)


def _tech_judgement_cron_job() -> None:
    if not _bool_setting("autopilot_enabled", False):
        return
    if not _bool_setting("autopilot_tech_judgement_enabled", False):
        return
    today, platforms, dry_run = _read_autopilot_runtime_settings()
    if not _media_ops_allows_lane("tech_judgement", today):
        return
    _fire_tech_judgement_autopilot(today, platforms, dry_run)


def _figure_tech_cron_job() -> None:
    if not _bool_setting("autopilot_enabled", False):
        return
    if not _bool_setting("autopilot_figure_enabled", True):
        return
    today, platforms, dry_run = _read_autopilot_runtime_settings()
    if not _media_ops_allows_lane("figure_tech", today):
        return
    _fire_figure_autopilot(today, platforms, dry_run)


def _business_finance_cron_job() -> None:
    if not _bool_setting("autopilot_enabled", False):
        return
    if not _bool_setting("autopilot_business_finance_enabled", False):
        return
    today, platforms, dry_run = _read_autopilot_runtime_settings()
    if not _media_ops_allows_lane("business_finance", today):
        return
    _fire_business_finance_autopilot(today, platforms, dry_run)


def _daily_job() -> None:
    """Manual "run autopilot now" path used by the UI."""
    _run_media_ops_agent_background()
    _run_storyboard_agent_background()
    if not _bool_setting("autopilot_enabled", False):
        _legacy_daily()
        return

    today, platforms, dry_run = _read_autopilot_runtime_settings()
    news_strategy = get_setting("autopilot_news_strategy", "generic") or "generic"
    if _bool_setting("autopilot_news_enabled", True) and _media_ops_allows_lane(news_strategy, today):
        _fire_news_autopilot_with_quota(today, platforms, dry_run, news_strategy)
    if _bool_setting("autopilot_tech_judgement_enabled", False) and _media_ops_allows_lane("tech_judgement", today):
        _fire_tech_judgement_autopilot(today, platforms, dry_run)
    if _bool_setting("autopilot_trending_enabled", True) and _media_ops_allows_lane("entertainment", today):
        _fire_trending_autopilot(today, platforms, dry_run)
    if _bool_setting("autopilot_figure_enabled", True) and _media_ops_allows_lane("figure_tech", today):
        _fire_figure_autopilot(today, platforms, dry_run)
    if _bool_setting("autopilot_business_finance_enabled", False) and _media_ops_allows_lane("business_finance", today):
        _fire_business_finance_autopilot(today, platforms, dry_run)


def _legacy_daily() -> None:
    """Pre-autopilot behavior: create one job and let the normal pipeline run."""
    today = date_cls.today().isoformat()
    platforms = _csv_setting("platforms", "youtube,instagram")
    dry_run = get_setting("dry_run", "false") == "true"
    job_id = create_job(date=today, triggered_by="schedule", platforms=",".join(platforms))
    job_runner.trigger_job(job_id=job_id, date=today, platforms=platforms, dry_run=dry_run)


def _offset_hours_setting(key: str, default: int) -> int:
    try:
        return max(0, min(23, int(get_setting(key, str(default)))))
    except (TypeError, ValueError):
        return default


def _trending_offset_hours() -> int:
    return _offset_hours_setting("autopilot_trending_offset_hours", 4)


def _tech_judgement_offset_hours() -> int:
    return _offset_hours_setting("autopilot_tech_judgement_offset_hours", 1)


def _figure_tech_offset_hours() -> int:
    return _offset_hours_setting("autopilot_figure_tech_offset_hours", 8)


def _business_finance_offset_hours() -> int:
    return _offset_hours_setting("autopilot_business_finance_offset_hours", 2)


def _remove_disabled_jobs() -> None:
    for job_id in ("autopilot_figure_entertainment",):
        if _scheduler.get_job(job_id):
            _scheduler.remove_job(job_id)


def start(hour: int = 8, minute: int = 0) -> None:
    trending_offset = _trending_offset_hours()
    tech_judgement_offset = _tech_judgement_offset_hours()
    figure_tech_offset = _figure_tech_offset_hours()
    business_finance_offset = _business_finance_offset_hours()
    trending_hour = (hour + trending_offset) % 24
    tech_judgement_hour = (hour + tech_judgement_offset) % 24
    figure_tech_hour = (hour + figure_tech_offset) % 24
    business_finance_hour = (hour + business_finance_offset) % 24
    media_ops_hour = (hour - 1) % 24 if minute < 30 else hour
    media_ops_minute = minute + 30 if minute < 30 else minute - 30
    report_hour = (hour + max(trending_offset, tech_judgement_offset, figure_tech_offset, business_finance_offset) + 1) % 24

    _scheduler.add_job(_run_media_ops_agent_background, "cron", hour=media_ops_hour, minute=media_ops_minute, id="media_ops_agent", replace_existing=True)
    _scheduler.add_job(_run_storyboard_agent_background, "cron", hour=media_ops_hour, minute=(media_ops_minute + 10) % 60, id="autopilot_storyboards", replace_existing=True)
    _scheduler.add_job(_run_media_ops_daily_report_background, "cron", hour=report_hour, minute=minute, id="media_ops_daily_report", replace_existing=True)
    _scheduler.add_job(_run_media_ops_failure_watchdog_background, "interval", minutes=30, id="media_ops_failure_watchdog", replace_existing=True)
    _scheduler.add_job(_news_cron_job, "cron", hour=hour, minute=minute, id="autopilot_news", replace_existing=True)
    _scheduler.add_job(
        _trending_cron_job,
        "cron",
        hour=trending_hour,
        minute=minute,
        id="autopilot_trending",
        replace_existing=True,
    )
    _scheduler.add_job(
        _tech_judgement_cron_job,
        "cron",
        hour=tech_judgement_hour,
        minute=minute,
        id="autopilot_tech_judgement",
        replace_existing=True,
    )
    _scheduler.add_job(
        _figure_tech_cron_job,
        "cron",
        hour=figure_tech_hour,
        minute=minute,
        id="autopilot_figure_tech",
        replace_existing=True,
    )
    _scheduler.add_job(
        _business_finance_cron_job,
        "cron",
        hour=business_finance_hour,
        minute=minute,
        id="autopilot_business_finance",
        replace_existing=True,
    )
    _remove_disabled_jobs()
    log.info(
        "[autopilot] schedule registered media_ops=%02d:%02d report=%02d:%02d news=%02d:%02d tech_judgement=%02d:%02d (+%dh) trending=%02d:%02d (+%dh) "
        "figure_tech=%02d:%02d (+%dh) business_finance=%02d:%02d (+%dh)",
        media_ops_hour,
        media_ops_minute,
        report_hour,
        minute,
        hour,
        minute,
        tech_judgement_hour,
        minute,
        tech_judgement_offset,
        trending_hour,
        minute,
        trending_offset,
        figure_tech_hour,
        minute,
        figure_tech_offset,
        business_finance_hour,
        minute,
        business_finance_offset,
    )
    if not _scheduler.running:
        _scheduler.start()


def update_schedule(hour: int, minute: int) -> None:
    if not _scheduler.running:
        return
    trending_offset = _trending_offset_hours()
    tech_judgement_offset = _tech_judgement_offset_hours()
    figure_tech_offset = _figure_tech_offset_hours()
    business_finance_offset = _business_finance_offset_hours()
    trending_hour = (hour + trending_offset) % 24
    tech_judgement_hour = (hour + tech_judgement_offset) % 24
    figure_tech_hour = (hour + figure_tech_offset) % 24
    business_finance_hour = (hour + business_finance_offset) % 24
    media_ops_hour = (hour - 1) % 24 if minute < 30 else hour
    media_ops_minute = minute + 30 if minute < 30 else minute - 30
    report_hour = (hour + max(trending_offset, tech_judgement_offset, figure_tech_offset, business_finance_offset) + 1) % 24

    _scheduler.add_job(_run_media_ops_agent_background, "cron", hour=media_ops_hour, minute=media_ops_minute, id="media_ops_agent", replace_existing=True)
    _scheduler.add_job(_run_storyboard_agent_background, "cron", hour=media_ops_hour, minute=(media_ops_minute + 10) % 60, id="autopilot_storyboards", replace_existing=True)
    _scheduler.add_job(_run_media_ops_daily_report_background, "cron", hour=report_hour, minute=minute, id="media_ops_daily_report", replace_existing=True)
    _scheduler.add_job(_run_media_ops_failure_watchdog_background, "interval", minutes=30, id="media_ops_failure_watchdog", replace_existing=True)
    _scheduler.add_job(_news_cron_job, "cron", hour=hour, minute=minute, id="autopilot_news", replace_existing=True)
    _scheduler.add_job(
        _trending_cron_job,
        "cron",
        hour=trending_hour,
        minute=minute,
        id="autopilot_trending",
        replace_existing=True,
    )
    _scheduler.add_job(
        _tech_judgement_cron_job,
        "cron",
        hour=tech_judgement_hour,
        minute=minute,
        id="autopilot_tech_judgement",
        replace_existing=True,
    )
    _scheduler.add_job(
        _figure_tech_cron_job,
        "cron",
        hour=figure_tech_hour,
        minute=minute,
        id="autopilot_figure_tech",
        replace_existing=True,
    )
    _scheduler.add_job(
        _business_finance_cron_job,
        "cron",
        hour=business_finance_hour,
        minute=minute,
        id="autopilot_business_finance",
        replace_existing=True,
    )
    _remove_disabled_jobs()
    log.info(
        "[autopilot] reschedule media_ops=%02d:%02d report=%02d:%02d news=%02d:%02d tech_judgement=%02d:%02d (+%dh) trending=%02d:%02d (+%dh) "
        "figure_tech=%02d:%02d (+%dh) business_finance=%02d:%02d (+%dh)",
        media_ops_hour,
        media_ops_minute,
        report_hour,
        minute,
        hour,
        minute,
        tech_judgement_hour,
        minute,
        tech_judgement_offset,
        trending_hour,
        minute,
        trending_offset,
        figure_tech_hour,
        minute,
        figure_tech_offset,
        business_finance_hour,
        minute,
        business_finance_offset,
    )


def run_now() -> None:
    _daily_job()


def shutdown() -> None:
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
