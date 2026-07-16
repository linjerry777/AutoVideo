#!/usr/bin/env python3
"""Editorial thumbnail generation for news/trending Shorts.

Pipeline:
1. Try image2 for a clean cover visual with no text/logo.
2. If image2 fails, grab a frame from the rendered video.
3. If that fails, create a non-purple editorial fallback.
4. Overlay controlled title/source/brand text with Pillow.
"""
from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
PIPELINE_DIR = Path(os.environ.get("PIPELINE_DIR", BASE_DIR / "pipeline")).resolve()
W, H = 1080, 1920
EDITORIAL_STRATEGIES = {"tech", "entertainment", "tech_judgement"}
IMAGE2_COVER_SIZES = ("1024x1792", "1024x1536", "1024x1024")


def _clean(text: str) -> str:
    return " ".join(str(text or "").split()).strip()


def should_use_editorial_cover(news: dict) -> bool:
    if (news.get("content_type") or "").lower() == "figure_quote":
        return False
    strategy = (news.get("strategy") or "").lower()
    return strategy in EDITORIAL_STRATEGIES


def palette_for_strategy(strategy: str) -> dict[str, str]:
    strategy = (strategy or "").lower()
    if strategy == "entertainment":
        return {
            "bg": "#090909",
            "accent": "#ffcf33",
            "accent2": "#ff4d6d",
            "panel": "#111111",
            "text": "#ffffff",
        }
    return {
        "bg": "#061014",
        "accent": "#27e0b3",
        "accent2": "#fff238",
        "panel": "#08181f",
        "text": "#ffffff",
    }


def build_image_prompt(news: dict, item: dict) -> str:
    strategy = (news.get("strategy") or "").lower()
    title = _clean(item.get("title") or item.get("hook") or "daily story")
    summary = _clean(item.get("summary") or item.get("script") or "")
    source = _clean(item.get("source_name") or item.get("source") or "")
    creative_brief = _clean(item.get("thumbnail_brief") or item.get("image2_brief") or news.get("thumbnail_brief") or "")
    if strategy == "entertainment":
        style = (
            "vertical 9:16 entertainment news cover visual, cinematic concert "
            "stage, crowd light sticks, spotlight beams, energetic lighting, "
            "premium editorial layout, no recognizable people, no human faces, "
            "no specific celebrity likeness"
        )
    else:
        style = (
            "vertical 9:16 technology news cover visual, premium editorial magazine "
            "photography, cinematic but realistic, modern Taiwan/AI/business context"
        )
    return (
        f"{style}, strong central subject, high contrast, clean composition, "
        f"no readable text, no logos, no watermark. Story: {title}. "
        f"Context: {summary[:260]}. Source cue: {source}. "
        f"Creative direction: {creative_brief[:260]}."
    )


def _load_font(size: int, bold: bool = True):
    from PIL import ImageFont

    candidates = [
        "C:/Windows/Fonts/msjhbd.ttc" if bold else "C:/Windows/Fonts/msjh.ttc",
        "C:/Windows/Fonts/NotoSansTC-Bold.otf" if bold else "C:/Windows/Fonts/NotoSansTC-Regular.otf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for path in candidates:
        try:
            if Path(path).exists():
                return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()


def _wrap_zh(text: str, max_chars: int) -> list[str]:
    text = _clean(text)
    if not text:
        return []
    lines: list[str] = []
    line = ""
    for ch in text:
        line += ch
        if len(line) >= max_chars or ch in "，。！？：:|｜":
            lines.append(line.strip(" |｜"))
            line = ""
    if line:
        lines.append(line.strip(" |｜"))
    return [ln for ln in lines if ln][:3]


def _find_ffmpeg() -> str | None:
    if shutil.which("ffmpeg"):
        return "ffmpeg"
    for root in (Path("C:/ffmpeg"), Path("C:/Program Files"), Path("C:/tools")):
        if root.exists():
            found = next(root.rglob("ffmpeg.exe"), None)
            if found:
                return str(found)
    return None


def _extract_video_frame(job_dir: Path, output: Path) -> Path | None:
    video = job_dir / "short" / "output.mp4"
    if not video.exists():
        video = job_dir / "output.mp4"
    ffmpeg = _find_ffmpeg()
    if not video.exists() or not ffmpeg:
        return None
    output.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg,
        "-y",
        "-ss",
        "2.0",
        "-i",
        str(video),
        "-frames:v",
        "1",
        "-vf",
        "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
        str(output),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return output if result.returncode == 0 and output.exists() else None


def image2_cover_sizes() -> tuple[str, ...]:
    raw = os.getenv("IMAGE2_COVER_SIZES", "")
    sizes = tuple(s.strip() for s in raw.split(",") if s.strip())
    return sizes or IMAGE2_COVER_SIZES


def _generate_image2(prompt: str, output: Path) -> Path | None:
    try:
        from web.claude_client import generate_image
    except Exception as exc:
        print(f"[thumbnail] image2 import failed: {exc}", file=sys.stderr)
        return None
    last_error: Exception | None = None
    for size in image2_cover_sizes():
        try:
            generated = generate_image(prompt, output, size=size, timeout=240)
            if generated and generated.exists():
                return generated
        except Exception as exc:
            last_error = exc
            print(f"[thumbnail] image2 failed size={size}: {exc}", file=sys.stderr)
    if last_error:
        print(f"[thumbnail] image2 exhausted cover sizes: {last_error}", file=sys.stderr)
    return None


def _fallback_visual(path: Path, strategy: str) -> Path:
    from PIL import Image, ImageDraw

    palette = palette_for_strategy(strategy)
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (W, H), palette["bg"])
    draw = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        r = int(6 + 18 * t)
        g = int(16 + (45 if strategy != "entertainment" else 10) * t)
        b = int(20 + (40 if strategy != "entertainment" else 8) * t)
        draw.line((0, y, W, y), fill=(r, g, b))
    for i in range(18):
        x = int((i * 157) % W)
        y = int((i * 281) % H)
        radius = 160 + (i % 4) * 40
        color = palette["accent"] if i % 2 == 0 else palette["accent2"]
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), outline=color, width=3)
    img.save(path)
    return path


def _cover_source(job_dir: Path, news: dict, item: dict) -> Path:
    assets = job_dir / "assets"
    image2_path = assets / "cover_image2.png"
    prompt_path = assets / "cover_prompt.txt"
    prompt = build_image_prompt(news, item)
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(prompt, encoding="utf-8")
    if not image2_path.exists():
        generated = _generate_image2(prompt, image2_path)
        if generated and generated.exists():
            return generated
    elif image2_path.stat().st_size > 0:
        return image2_path

    frame = _extract_video_frame(job_dir, assets / "cover_frame.png")
    if frame:
        return frame

    return _fallback_visual(assets / "cover_fallback.png", news.get("strategy") or "tech")


def render_editorial_cover(job_dir: Path, news: dict, item: dict, output: Path) -> Path:
    from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps

    strategy = (news.get("strategy") or "").lower()
    palette = palette_for_strategy(strategy)
    src = _cover_source(job_dir, news, item)
    base = Image.open(src).convert("RGB")
    base = ImageOps.fit(base, (W, H), method=Image.Resampling.LANCZOS, centering=(0.5, 0.45))
    base = ImageEnhance.Contrast(base).enhance(1.08)
    base = ImageEnhance.Color(base).enhance(1.05)

    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for y in range(H):
        top = max(0, 190 - y) / 190
        bottom = max(0, y - 940) / 980
        alpha = int(min(215, top * 120 + bottom * 210))
        if alpha:
            draw.line((0, y, W, y), fill=(0, 0, 0, alpha))
    draw.rectangle((0, 0, W, H), outline=(255, 255, 255, 18), width=1)

    img = Image.alpha_composite(base.convert("RGBA"), overlay)
    draw = ImageDraw.Draw(img)
    title = _clean(item.get("title") or item.get("hook") or "今日重點")
    hook = _clean(item.get("hook") or ("3點看懂" if strategy != "entertainment" else "今天熱點"))
    source = _clean(item.get("source_name") or item.get("source") or "")

    badge_font = _load_font(42)
    title_font = _load_font(96 if len(title) <= 12 else 82)
    source_font = _load_font(34, bold=False)
    brand_font = _load_font(40)

    badge = hook[:10]
    bbox = draw.textbbox((0, 0), badge, font=badge_font)
    badge_w = max(152, bbox[2] - bbox[0] + 42)
    draw.rounded_rectangle((58, 78, 58 + badge_w, 140), radius=8, fill=palette["accent"])
    draw.text((78, 87), badge, font=badge_font, fill="#061014")

    lines = _wrap_zh(title, 9 if len(title) <= 16 else 10)
    y = 182
    for line in lines:
        draw.text((60, y), line, font=title_font, fill=palette["text"], stroke_width=5, stroke_fill="#000000")
        y += int(title_font.size * 1.05)

    footer_top = 1608
    draw.rounded_rectangle((52, footer_top, W - 52, H - 96), radius=26, fill=(0, 0, 0, 185))
    if source:
        draw.text((76, footer_top + 34), f"Sources: {source[:32]}", font=source_font, fill="#d9e7ea")
    draw.text((76, H - 172), "DORO", font=_load_font(58), fill=palette["accent2"])
    draw.text((248, H - 158), "每日短影音", font=brand_font, fill="#ffffff")

    output.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(output, quality=94)
    return output


def generate_editorial_thumbnail(job_dir: Path, output: Path | None = None) -> Path | None:
    news_file = job_dir / "news.json"
    if not news_file.exists():
        return None
    news = json.loads(news_file.read_text(encoding="utf-8"))
    if not should_use_editorial_cover(news):
        return None
    items = news.get("items") or []
    if not items:
        return None
    output = output or (job_dir / "thumbnail.png")
    return render_editorial_cover(job_dir, news, items[0], output)
