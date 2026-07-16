# TikTok Viral Fetcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a TikTok high-view video candidate collector that feeds AutoVideo's trend radar with metadata-only viral video references.

**Architecture:** Create a standalone `scripts/tiktok_viral_fetcher.py` that scrapes/normalizes Creative Center trend video metadata and exposes a CLI. Wire it into `web.routes.news` as an optional source named `tiktok_viral` without downloading or republishing source videos. If TikTok's public page does not expose single-video rows, fall back to Creative Center high-view hashtag/topic rows and label them as `tiktok_viral_topic`.

**Tech Stack:** Python stdlib, TikTok Creative Center server-rendered `__NEXT_DATA__` / `__MODERN_*` JSON blobs, unittest.

## Global Constraints

- Do not implement white-border, mirror, or reupload-bypass processing.
- Collector output must mark candidates as `external_reference_only`.
- Keep implementation dependency-light and runnable as a standalone CLI.
- Do not delete or modify generated `data/` or `pipeline/` output.

---

### Task 1: TikTok Viral Collector

**Files:**
- Create: `tests/test_tiktok_viral_fetcher.py`
- Create: `scripts/tiktok_viral_fetcher.py`

**Interfaces:**
- Produces: `extract_video_rows(data: dict) -> list[dict]`
- Produces: `normalize_video(row: dict, rank: int, region: str, period: str) -> dict`
- Produces: `rank_videos(rows: list[dict], limit: int, min_views: int, region: str, period: str) -> list[dict]`
- Produces: `collect_viral_videos(region: str = "TW", period: str = "7", limit: int = 20, min_views: int = 100000, fetch_html: Callable[[str], str] | None = None) -> list[dict]`

- [x] **Step 1: Write the failing test**

Create tests that feed nested Creative Center-like JSON into `extract_video_rows`, verify high-view rows rank first, and verify normalized candidates include source metadata plus `rights_status="external_reference_only"`.

- [x] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_tiktok_viral_fetcher`
Expected: import failure because `scripts.tiktok_viral_fetcher` does not exist.

- [x] **Step 3: Write minimal implementation**

Create the collector with recursive row extraction, flexible metric parsing, CLI JSON output, and no source-video downloading.

- [x] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_tiktok_viral_fetcher`
Expected: PASS.

### Task 2: News Source Integration

**Files:**
- Modify: `web/routes/news.py`
- Modify: `tests/test_tiktok_viral_fetcher.py`

**Interfaces:**
- Produces: `_fetch_tiktok_viral(keyword: str | None = None, limit: int = 25, region: str = "TW") -> list[dict]`
- Consumes: `scripts.tiktok_viral_fetcher.collect_viral_videos`

- [x] **Step 1: Write the failing test**

Add a test patching `collect_viral_videos` and assert `_fetch_all("", "zh-TW", ["tiktok_viral"], limit_per=3)` returns TikTok viral candidates.

- [x] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_tiktok_viral_fetcher`
Expected: `tiktok_viral` source is not wired.

- [x] **Step 3: Wire source**

Add `tiktok_viral` to `ALL_SOURCES`, `_fetch_all`, and trending source handling.

- [x] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_tiktok_viral_fetcher`
Expected: PASS.

### Task 3: Verification

**Files:**
- Test only.

- [x] **Step 1: Run targeted tests**

Run: `python -m unittest tests.test_tiktok_viral_fetcher tests.test_media_ops_strategy tests.test_media_ops_agent`
Expected: PASS.

- [x] **Step 2: Compile changed Python**

Run: `python -m py_compile scripts/tiktok_viral_fetcher.py web/routes/news.py`
Expected: exit code 0.
