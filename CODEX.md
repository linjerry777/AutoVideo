# AutoVideo Codex Handoff

Last updated: 2026-06-03

Read `AGENTS.md` first. The active app is the FastAPI backend plus
`web/static/index.html` at `http://localhost:9000/ui`; the old `frontend/`
dashboard is not used.

## Current Live Publish

Manual Nailao upload job:

- Job folder: `pipeline/2026-06-03/job_pet95_reupload_entertainment_yt`
- Source video: `pipeline/storyboards/2026-06-02/candidate_95/output_with_bgm.mp4`
- Published file: `pipeline/2026-06-03/job_pet95_reupload_entertainment_yt/output.mp4`
- Profile: `entertainment_yt`
- Caption used:

```text
今天逛夜市
#奶烙出任務 #貓咪日常 #貓咪Vlog #夜市 #台灣夜市 #橘貓 #cat #cats #catvlog #cutecat
```

Upload-Post request status:

- YouTube: completed, `2788f87515134878ba4e1dc5ed4de1d3`
- Instagram: completed, `aaf3d0d9f92c4768bc409e02cdc8f334`
- TikTok: completed, `f05f393858524dd8a953289bae626b29`
- Facebook: completed, `4c3ae5e04586409290803254ac9ad85e`
- X: completed, `5b845bb2389e49d1bae80788e187f416`

Correct Nailao Upload-Post profile is `entertainment_yt`, not `pet`.
Connected accounts observed from Upload-Post:

- TikTok: `user1883696907819`
- Instagram: `_nailao1998`
- YouTube: `奶烙出任務`
- X: `_nailao1998`
- Facebook page: `奶烙出任務`, page id `1181556318367016`

`scripts/publisher.py` must not redirect `entertainment_yt` Facebook uploads to
`pet`; that old redirect was removed.

## Pet Storyboard Lane

Current creative direction:

- Not generic pet videos.
- Use vlog / movie / meme camera grammar, but convert it into Nailao daily life.
- Cats are equal city residents, not pets.
- No owner framing, no pet food, no canned-food default.
- For Nailao vlog, use real human contexts: night markets, department-store food
  courts, commute, friends meeting, group photos, payments, food queues.

Important candidate:

- Candidate #95: `奶烙 Vlog：夜市貓友會玩瘋了`
- Status: `video_ready`
- Output: `storyboards/2026-06-02/candidate_95/output_with_bgm.mp4`
- Final format: 1080x1920, 9:16, BGM mixed from `hagimi.mp3`

Generation notes:

- `seedance-1-0-pro-250528` and `seedance-1-5-pro-251215` can hit BytePlus safe
  experience / inference limits.
- `seedance-1-0-pro-fast-251015` worked for recent rerenders.
- Seedance returns 4 second clips; user prefers keeping 4 seconds instead of
  over-trimming unless a specific segment is broken.
- If a sequence needs continuity, make the storyboard frames connected first.
  Example: night-market ring toss should not have 10 and 11 nearly identical;
  change camera angle and time beat, such as a prize-side reverse shot watching
  cats throw rings.

## Pending UI / Workflow Cleanup

Storyboard pool UI still needs practical polish:

- Remove the top controls the user marked as unused.
- Make storyboard / video display higher and larger.
- Add a segment-video tab next to storyboard and final video.
- Modal needs previous / next buttons.
- Modal needs "regenerate this frame" and "regenerate this segment video".
- Candidate list needs add/delete controls.
- Keep horizontal scrolling for many storyboard frames; do not force a fixed
  frame count.
- Avoid raw `?????` in prompts. It can leak from encoding issues and should be
  sanitized before image/video generation.

## Upload Rules

- For pet / entertainment manual uploads, always write explicit `platform_meta.json`.
- Do not let fallback captions generate "三件事", "1 個萌寵時刻", or ManyChat CTA.
- ManyChat CTA is only for Doro tech strategies.
- Nailao manual fan-out should use `--profile entertainment_yt` with YouTube,
  Instagram, TikTok, Facebook, and X. Do not use `--profile pet` for Nailao.

## Do Not Touch Casually

- Do not delete `data/` or `pipeline/`.
- Do not restart or steal port 9000 unless the user asks.
- Do not re-enable TikTok autopilot casually; manual uploads are okay when the
  user requests them.
- Do not commit `.env`, generated outputs, or Upload-Post/R2/API secrets.
