# AutoVideo Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Make AutoVideo easier to reason about while improving short-video quality feedback loops.

**Architecture:** Keep the current FastAPI/static UI and standalone script pipeline. Add focused modules around content strategy, figure segment quality, analytics experiments, pipeline steps, render templates, and static dashboard helpers without deleting local `data/` or `pipeline/`.

**Tech Stack:** Python 3.12, FastAPI, SQLite, Remotion/TypeScript, static Alpine dashboard.

---

### Task 1: Content Strategy Module

**Files:**
- Create: `web/content_strategy.py`
- Modify: `web/routes/jobs.py`
- Modify: `scripts/publisher.py`
- Test: `tests/test_content_strategy.py`

- [x] Centralize strategy labels, title formulas, AIGC policy, CTA groups, platform tags, signoff, and default platform metadata.
- [x] Route `/platform_meta` through the shared module.
- [x] Make publisher fallback metadata use the same strategy module.
- [x] Add tests covering figure tech metadata and publisher fallback metadata.

### Task 2: Figure Segment Quality Gate

**Files:**
- Create: `scripts/figure_segment_quality.py`
- Modify: `scripts/figure_segment_pool.py`
- Modify: `web/db.py`
- Test: `tests/test_figure_segment_quality.py`

- [x] Score normalized quote segments for duration, transcript density, hook length, script quality, quote integrity, and visual/source hints.
- [x] Persist `quality_score` and `quality_reason`.
- [x] Filter low-quality segments before insert and prefer high-quality segments when picking.

### Task 3: Analytics Feedback Loop

**Files:**
- Create: `web/analytics_feedback.py`
- Modify: `web/routes/analytics.py`
- Modify: `scripts/analytics_fetcher.py`
- Test: `tests/test_analytics_feedback.py`

- [x] Extract experiment metadata from `news.json` and `platform_meta.json`.
- [x] Attach experiment metadata to analytics overview rows.
- [x] Write daily aggregate feedback to `data/analytics_feedback.json`.

### Task 4: Pipeline Step Structure

**Files:**
- Create: `web/pipeline_steps.py`
- Modify: `web/job_runner.py`
- Test: `tests/test_pipeline_steps.py`

- [x] Add a small `PipelineContext`/`PipelineStepRunner` module for logging, script execution, and nonfatal script handling.
- [x] Keep public `job_runner._call_script` compatible.
- [x] Use the runner for trend calibration and add unit coverage.

### Task 5: Render Template Spec

**Files:**
- Create: `web/render_templates.py`
- Create: `data/render_template_spec.default.json`
- Modify: `scripts/remotion_renderer.py`
- Modify: `scripts/insight_quote_composer.py`
- Test: `tests/test_render_templates.py`

- [x] Define shared safe zones and caption positions.
- [x] Let renderers read the same spec with stable fallbacks.
- [x] Add tests for defaults and override loading.

### Task 6: Dashboard Static Split

**Files:**
- Create: `web/static/js/autovideo-ui.js`
- Modify: `web/static/index.html`

- [x] Move reusable tiny UI helpers out of the monolithic static page without changing the app boot path.
- [x] Keep the dashboard served at `/ui`.

### Task 7: Verification

**Commands:**
- [x] `python -m py_compile ...`
- [x] `python -m unittest discover -s tests`
- [x] `npx tsc --noEmit`

