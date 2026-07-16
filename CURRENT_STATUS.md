# AutoVideo Current Status

Last updated: 2026-07-16

## 2026-07-16 Delivery Verification

- Delivery branch: `codex/autovideo-optimization`.
- Local UI: `http://127.0.0.1:9000/ui` (FastAPI + static Alpine/Tailwind dashboard).
- Python suite: 93 tests passed; changed/new Python modules also pass `py_compile`.
- Browser verification: desktop 1440px and mobile 390px, no horizontal page overflow and no console errors.
- Core read APIs verified with HTTP 200: stats, jobs, settings, storyboards, schedule, and analytics.
- Mobile now uses a dedicated sticky navigation bar; the desktop sidebar is hidden below the `md` breakpoint.
- Storyboard Seedance pair mode now submits first/last frame pairs and is covered by a mock-only test; no generation request was made during verification.
- Settings API treats credentials as write-only. Browser responses expose only `*_set` flags and never return stored key values.
- Portfolio-safe screenshots are under `verification/portfolio/`.

Runtime safety state after verification:

- `autopilot_enabled=false`
- `autopilot_dry_run=true`
- No video was generated, uploaded, scheduled, or republished in this delivery pass.
- Re-enable production autopilot only after Jerry explicitly approves a live publishing check.

## Active Shape

- Active UI: `http://localhost:9000/ui`, served by `web/static/index.html`.
- Active backend: FastAPI in `web/`.
- Active pipeline: Python scripts in `scripts/`, orchestrated by `web/job_runner.py`.
- Old `frontend/` Next/Vercel dashboard has been removed from this repo.
- Generated outputs remain local under `pipeline/` and are ignored by git.
- Local SQLite state remains under `data/` and is ignored by git.

## Autopilot

The lanes below remain implemented, but the global autopilot is currently paused
for delivery review.

Current automatic lanes:

1. News
2. Entertainment/trending
3. Tech figure source-video analysis
4. Media Ops / storyboard review support for experimental pet video ideas

Entertainment figure analysis is intentionally not scheduled. Historical
`figure_entertainment` metadata still exists for older jobs and manual uploads,
but autopilot should only create `figure_tech` jobs.

Current intended schedule:

- News: 18:00
- Entertainment/trending: 19:00
- Tech figure analysis: 20:00

Do not re-enable TikTok autopilot without explicit approval.

Pet / entertainment storyboard videos are not a blind daily autopilot lane yet.
They should stay in a storyboard pool first, then be approved before spending
Seedance video tokens or publishing.

## Recent Work

- Analytics UI and backend now focus on per-video performance recovery.
- Upload-Post scheduling and retry behavior were hardened.
- Figure source/segment pool exists for tech figures.
- Figure quote composer has a safer top area for mobile platform chrome.
- Repository cleanup removed generated pipeline output from git tracking and
  removed the stale `frontend` gitlink.
- Media Ops Agent direction exists: it should monitor platform performance and
  steer topics/editing, not only collect our own views.
- Tech account currently has three main formats: news, DORO tech judgement, and
  tech figure quote analysis.
- Pet lane is now testing "Nailao vlog" style: human-like cats as equal city
  residents, no owner-pet framing, no pet food, real-life Taipei/Taiwan scenes.
- Storyboard candidate #95 ("奶烙 Vlog：夜市貓友會玩瘋了") rendered and was
  manually uploaded on 2026-06-03 via
  `pipeline/2026-06-03/job_pet95_reupload_entertainment_yt`.
  Use Upload-Post profile `entertainment_yt` for this Nailao account group.
  YouTube / Instagram / TikTok / Facebook / X completed successfully.

## Current Product Direction

The useful work is improving retention, not adding more broad automation:

- Stronger first-frame hook/cover.
- Better tech figure source selection.
- More reliable per-platform analytics.
- Cleaner scheduling and upload recovery.
- Keep code paths small enough that autopilot behavior is easy to reason about.
- For pet videos, prioritize frame continuity and camera language over simply
  generating cute cat images. If a scene needs continuity, generate a multi-frame
  sheet or linked reference frames first, then split/use the frames downstream.
- Keep pet upload captions manually controlled through `platform_meta.json`.
  Do not let the fallback "3 things" / ManyChat-style captions leak into pet,
  entertainment, or storyboard uploads.
- For Nailao uploads, use profile `entertainment_yt`, not `pet`.

## Do Not Do

- Do not delete `data/` or `pipeline/` without explicit user approval.
- Do not restart/steal active ports unless requested.
- Do not publish/repost scheduled videos without confirming when it affects live platforms.
- Do not revive the old Next.js frontend unless the user explicitly asks.
- Do not use ManyChat CTA on pet or entertainment captions. ManyChat is for the
  Doro tech account only.
