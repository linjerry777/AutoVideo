#!/usr/bin/env python3
"""Generate image2 scene stills for a DORO tech-judgement Short.

The script reads ``news.json`` from a pipeline job and writes:

- assets/scene_01.png
- assets/scene_02.png
- assets/scene_03.png
- assets/manifest.json

If image2 is temporarily unavailable, it creates simple fallback stills so the
job can still render a preview instead of blocking the whole autopilot queue.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
PIPELINE_DIR = BASE_DIR / "pipeline"
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _job_dir(job_key: str) -> Path:
    path = PIPELINE_DIR / job_key
    if not path.exists():
        raise FileNotFoundError(path)
    return path


def _read_item(job_dir: Path) -> dict:
    news_file = job_dir / "news.json"
    data = json.loads(news_file.read_text(encoding="utf-8"))
    items = data.get("items") or []
    if not items:
        raise ValueError(f"news.json has no items: {news_file}")
    return items[0]


def _default_prompts(item: dict) -> list[str]:
    title = _clean(item.get("title") or item.get("hook") or "AI industry shift")
    summary = _clean(item.get("summary") or item.get("script") or "")
    base = (
        "Vertical 9:16 editorial technology news illustration, premium magazine "
        "cover style, cinematic lighting, high contrast black background, clean "
        "composition, no readable text, no logos, no watermark."
    )
    return [
        f"{base} Scene 1: what happened in this story: {title}. {summary[:220]}",
        f"{base} Scene 2: why this matters for platforms, AI agents, developers, and users: {title}.",
        f"{base} Scene 3: downstream impact, winners and losers, strategic judgement: {title}.",
    ]


def _normalise_prompts(item: dict) -> list[str]:
    raw = item.get("visual_prompts") or item.get("image_prompts") or []
    prompts: list[str] = []
    if isinstance(raw, list):
        prompts = [_clean(p) for p in raw if _clean(p)]
    elif isinstance(raw, str):
        prompts = [_clean(p) for p in re.split(r"\n+|\|\|\|", raw) if _clean(p)]
    prompts = prompts[:3]
    if len(prompts) < 3:
        prompts.extend(_default_prompts(item)[len(prompts):])
    return prompts[:3]


def _fallback_image(path: Path, title: str, label: str) -> None:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception as exc:  # pragma: no cover - only for broken local envs
        raise RuntimeError(f"image2 failed and Pillow fallback is unavailable: {exc}") from exc

    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (1024, 1024), "#06080f")
    draw = ImageDraw.Draw(img)
    try:
        font_big = ImageFont.truetype("C:/Windows/Fonts/msjhbd.ttc", 72)
        font_mid = ImageFont.truetype("C:/Windows/Fonts/msjhbd.ttc", 46)
    except Exception:
        font_big = ImageFont.load_default()
        font_mid = ImageFont.load_default()

    draw.rectangle((48, 48, 976, 976), outline="#fff238", width=8)
    draw.rectangle((80, 650, 944, 890), fill="#111827")
    draw.text((90, 94), "DORO", fill="#fff238", font=font_big)
    draw.text((90, 190), label, fill="#ffffff", font=font_big)

    wrapped = []
    line = ""
    for ch in title:
        line += ch
        if len(line) >= 12:
            wrapped.append(line)
            line = ""
    if line:
        wrapped.append(line)
    y = 690
    for row in wrapped[:3]:
        draw.text((115, y), row, fill="#f8fafc", font=font_mid)
        y += 62
    img.save(path)


def generate(job_key: str, force: bool = False) -> list[Path]:
    job_dir = _job_dir(job_key)
    item = _read_item(job_dir)
    assets_dir = job_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    prompts = _normalise_prompts(item)
    title = _clean(item.get("title") or item.get("hook") or "DORO 科技判讀")
    labels = ["發生什麼", "為什麼重要", "影響誰"]
    outputs: list[Path] = []
    manifest_items: list[dict] = []

    from web.claude_client import generate_image

    for idx, prompt in enumerate(prompts, 1):
        out = assets_dir / f"scene_{idx:02d}.png"
        if out.exists() and not force:
            outputs.append(out)
            manifest_items.append({"index": idx, "path": str(out), "prompt": prompt, "reused": True})
            continue
        last_error: Exception | None = None
        for attempt in range(1, 4):
            try:
                generate_image(prompt, out, size="1024x1024", timeout=240)
                manifest_items.append({
                    "index": idx,
                    "path": str(out),
                    "prompt": prompt,
                    "fallback": False,
                    "attempt": attempt,
                })
                last_error = None
                break
            except Exception as exc:
                last_error = exc
                if attempt < 3:
                    time.sleep(3 * attempt)
        if last_error is not None:
            _fallback_image(out, title, labels[idx - 1])
            manifest_items.append({
                "index": idx,
                "path": str(out),
                "prompt": prompt,
                "fallback": True,
                "error": str(last_error)[-500:],
            })
        outputs.append(out)

    (assets_dir / "manifest.json").write_text(
        json.dumps({"kind": "tech_judgement_images", "items": manifest_items}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("job_key", help="e.g. 2026-05-19/job_180")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    for path in generate(args.job_key, force=args.force):
        print(path)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"tech_judgement_image_generator failed: {exc}", file=sys.stderr)
        raise
