# Business Finance Lane Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a first working `business_finance` lane for a business analysis account without disrupting existing tech, entertainment, and pet lanes.

**Architecture:** Reuse AutoVideo's existing FastAPI/static UI, scheduler, LLM enrichment, renderer, Upload-Post publisher, and Media Ops feedback loop. Add one focused collector/researcher script that produces pre-enriched business-analysis `news.json` items, then route it through the existing job runner with a dedicated strategy and profile setting.

**Tech Stack:** Python 3.12, FastAPI, SQLite settings, existing static dashboard, existing Upload-Post publisher.

---

### Task 1: Register `business_finance` Strategy

**Files:**
- Modify: `web/content_strategy.py`
- Modify: `web/routes/jobs.py`
- Modify: `web/routes/schedule.py`
- Modify: `web/routes/settings.py`
- Modify: `web/telegram_bot.py`
- Modify: `scripts/publisher.py`
- Modify: `web/claude_client.py`
- Test: `tests/test_business_finance_strategy.py`

- [x] Write a failing test asserting `business_finance` is registered across pipeline metadata maps, uses AIGC metadata, has business-analysis tags/hashtags, uses the configured business profile, and includes a non-investment-advice disclaimer.
- [x] Run `python -m unittest tests.test_business_finance_strategy` and confirm it fails because the strategy is missing.
- [x] Add minimal `business_finance` entries to strategy labels, CTA group, AIGC map, title/signoff/tags/hashtags, and fallback metadata.
- [x] Run `python -m unittest tests.test_business_finance_strategy` and confirm it passes.

### Task 2: Add Business Finance Candidate Research

**Files:**
- Create: `scripts/business_finance_collector.py`
- Test: `tests/test_business_finance_collector.py`

- [x] Write a failing test for ranking finance/business candidates while rejecting explicit buy/sell advice.
- [x] Run `python -m unittest tests.test_business_finance_collector` and confirm it fails because the script/module is missing.
- [x] Implement a dependency-light collector that normalizes business news candidates, scores company/business-model/risk topics, adds guardrails, and builds AutoVideo-ready items.
- [x] Run `python -m unittest tests.test_business_finance_collector` and confirm it passes.

### Task 3: Wire Scheduler Lane

**Files:**
- Modify: `web/db.py`
- Modify: `web/scheduler_service.py`
- Test: `tests/test_scheduler_service.py`

- [x] Write a failing scheduler test proving the business lane creates a job using the business profile and `business_finance` strategy.
- [x] Run the targeted scheduler test and confirm it fails because the lane does not exist.
- [x] Add settings for `autopilot_business_finance_enabled`, `autopilot_business_finance_profile`, sources, keywords, and offset.
- [x] Add `_fire_business_finance_autopilot` and hook it into cron/manual fan-out after existing lanes.
- [x] Run the targeted scheduler tests and confirm they pass.

### Task 4: Static UI Exposure

**Files:**
- Modify: `web/static/index.html`

- [x] Add the strategy option and setting rows for the business finance lane using existing UI patterns.
- [x] Keep visible wording concise and avoid changing unrelated layout.

### Task 5: Verification

**Commands:**
- [x] `python -m unittest tests.test_business_finance_strategy tests.test_business_finance_collector tests.test_scheduler_service`
- [x] `python -m py_compile web/content_strategy.py web/routes/jobs.py web/routes/schedule.py web/routes/settings.py web/scheduler_service.py scripts/publisher.py scripts/business_finance_collector.py`
