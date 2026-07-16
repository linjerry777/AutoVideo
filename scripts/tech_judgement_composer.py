#!/usr/bin/env python3
"""Render a DORO tech-judgement Short from image2 scene stills."""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
PIPELINE_DIR = BASE_DIR / "pipeline"
W, H = 1080, 1920
FONT_ZH = Path("C:/Windows/Fonts/msjhbd.ttc")
FONT_LATIN = Path("C:/Windows/Fonts/arialbd.ttf")
DORO_LOGO = BASE_DIR / "assets" / "brand" / "doro_insight_logo.png"


def _ffmpeg() -> str:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found")
    return ffmpeg


def _ffprobe() -> str:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise RuntimeError("ffprobe not found")
    return ffprobe


def ff_path(path: Path | str) -> str:
    return str(path).replace("\\", "/").replace(":", "\\:")


def output_is_valid(path: Path, expected_duration: float | None = None) -> bool:
    if not path.exists() or path.stat().st_size < 100_000:
        return False
    try:
        duration = probe_duration(path)
    except Exception:
        return False
    if duration <= 1:
        return False
    if expected_duration and duration < expected_duration * 0.85:
        return False
    return True


def run(cmd: list[str], *, output_path: Path | None = None, expected_duration: float | None = None) -> None:
    result = subprocess.run(cmd, text=True, encoding="utf-8", errors="replace", capture_output=True)
    if result.returncode != 0:
        # Some Windows ffmpeg builds can return ENOMEM during final filtergraph
        # teardown even after writing a complete MP4. Accept the render if
        # ffprobe confirms a playable video, so one warning does not fail the job.
        if output_path and output_is_valid(output_path, expected_duration):
            print(f"[tech_judgement] ffmpeg returned {result.returncode}, but output is valid; keeping {output_path}")
            return
        raise RuntimeError(result.stderr[-1800:] or result.stdout[-1800:])


def read_json(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8", errors="replace"))


def probe_duration(path: Path) -> float:
    result = subprocess.run(
        [_ffprobe(), "-v", "error", "-show_entries", "format=duration", "-of", "default=nk=1:nw=1", str(path)],
        text=True,
        capture_output=True,
    )
    return float((result.stdout or "0").strip() or 0)


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def split_zh(text: str, max_chars: int = 15) -> str:
    text = clean_text(text)
    if len(text) <= max_chars:
        return text
    cut = max_chars
    for mark in "，、；：。！？ ":
        idx = text.rfind(mark, 0, max_chars + 1)
        if idx >= 6:
            cut = idx + (0 if mark == " " else 1)
            break
    return text[:cut].strip() + r"\N" + text[cut:].strip()


def ass_time(seconds: float) -> str:
    centis = int(round(max(0, seconds) * 100))
    h, rem = divmod(centis, 360000)
    m, rem = divmod(rem, 6000)
    s, c = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{c:02d}"


def write_caption_ass(timing_file: Path, duration: float, path: Path) -> None:
    rows = read_json(timing_file) if timing_file.exists() else []
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: CAP,Microsoft JhengHei,74,&H00FFFFFF,&H000000FF,&H00000000,&HAA000000,-1,0,0,0,100,100,0,0,1,7,0,2,70,70,520,1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""
    lines = [header]
    for row in rows:
        start = float(row.get("start") or 0)
        end = min(duration, max(start + 0.65, float(row.get("end") or duration)))
        text = split_zh(row.get("text") or "", 15)
        if text:
            lines.append(f"Dialogue: 0,{ass_time(start)},{ass_time(end)},CAP,,0,0,0,,{text}\n")
    path.write_text("".join(lines), encoding="utf-8")


def scene_images(job_dir: Path) -> list[Path]:
    images = sorted((job_dir / "assets").glob("scene_*.png"))
    legacy = job_dir / "assets" / "apple_agent_store_main.png"
    if not images and legacy.exists():
        images = [legacy]
    return images[:3]


def title_lines(item: dict) -> tuple[str, str]:
    line_1 = clean_text(item.get("judgement_title_1") or item.get("title") or "DORO 科技判讀")
    line_2 = clean_text(item.get("judgement_title_2") or item.get("hook") or "看懂這件事的下一步")
    if len(line_1) > 18 and not item.get("judgement_title_2"):
        line_1, line_2 = line_1[:18], line_1[18:]
    return line_1[:24], line_2[:24]


def render(job_key: str, output_name: str = "output.mp4") -> Path:
    job_dir = PIPELINE_DIR / job_key
    data = read_json(job_dir / "news.json")
    item = (data.get("items") or [{}])[0]
    images = scene_images(job_dir)
    audio = job_dir / "short" / "audio" / "audio_01.mp3"
    timing = job_dir / "short" / "audio" / "audio_01_timing.json"
    if not images:
        raise FileNotFoundError(job_dir / "assets" / "scene_01.png")
    if not audio.exists():
        raise FileNotFoundError(audio)

    out_dir = job_dir / "short"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / output_name
    duration = probe_duration(audio)
    break_1 = max(6.0, duration * 0.28)
    break_2 = max(break_1 + 6.0, duration * 0.64)

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        ass = tmp / "captions.ass"
        write_caption_ass(timing, duration, ass)

        title_1 = tmp / "title_1.txt"
        title_2 = tmp / "title_2.txt"
        source = tmp / "source.txt"
        brand = tmp / "brand.txt"
        badge_fact = tmp / "badge_fact.txt"
        badge_why = tmp / "badge_why.txt"
        badge_impact = tmp / "badge_impact.txt"

        line_1, line_2 = title_lines(item)
        title_1.write_text(line_1, encoding="utf-8")
        title_2.write_text(line_2, encoding="utf-8")
        source_name = clean_text(item.get("source_name") or item.get("source") or "Tech press")
        source.write_text(f"Sources: {source_name}", encoding="utf-8")
        brand.write_text("DORO 科技判讀", encoding="utf-8")
        badge_fact.write_text("發生什麼", encoding="utf-8")
        badge_why.write_text("為什麼重要", encoding="utf-8")
        badge_impact.write_text("影響誰", encoding="utf-8")

        inputs: list[str] = []
        for image in images:
            inputs += ["-loop", "1", "-i", str(image)]
        audio_input = len(images)
        inputs += ["-i", str(audio)]

        logo_input = None
        if DORO_LOGO.exists():
            logo_input = audio_input + 1
            inputs += ["-loop", "1", "-i", str(DORO_LOGO)]

        filters: list[str] = [f"color=c=#05070B:s={W}x{H}:r=30:d={duration:.3f}[canvas]"]
        for idx in range(len(images)):
            filters.append(
                f"[{idx}:v]scale=1180:1180:force_original_aspect_ratio=increase,"
                f"crop=1080:1080,eq=contrast=1.08:saturation=1.08[hero{idx}]"
            )

        filters.append(f"[canvas][hero0]overlay=0:370:enable='between(t,0,{break_1:.3f})'[scene0]")
        last = "scene0"
        if len(images) >= 2:
            filters.append(f"[{last}][hero1]overlay=0:370:enable='between(t,{break_1:.3f},{break_2:.3f})'[scene1]")
            last = "scene1"
        if len(images) >= 3:
            filters.append(f"[{last}][hero2]overlay=0:370:enable='gte(t,{break_2:.3f})'[scene2]")
            last = "scene2"

        filters += [
            f"[{last}]drawtext=fontfile='{ff_path(FONT_ZH)}':textfile='{ff_path(title_1)}':fontsize=80:fontcolor=#FFF238:x=(w-text_w)/2:y=88:borderw=7:bordercolor=black[v1]",
            f"[v1]drawtext=fontfile='{ff_path(FONT_ZH)}':textfile='{ff_path(title_2)}':fontsize=92:fontcolor=white:x=(w-text_w)/2:y=184:borderw=7:bordercolor=black[v2]",
            f"[v2]drawbox=x=62:y=302:w=330:h=70:color=#FFF238@0.92:t=fill[v3]",
            f"[v3]drawtext=fontfile='{ff_path(FONT_ZH)}':textfile='{ff_path(badge_fact)}':fontsize=42:fontcolor=black:x=88:y=312:enable='between(t,0,8)'[v4a]",
            f"[v4a]drawtext=fontfile='{ff_path(FONT_ZH)}':textfile='{ff_path(badge_why)}':fontsize=42:fontcolor=black:x=78:y=312:enable='between(t,8,22)'[v4b]",
            f"[v4b]drawtext=fontfile='{ff_path(FONT_ZH)}':textfile='{ff_path(badge_impact)}':fontsize=42:fontcolor=black:x=112:y=312:enable='gte(t,22)'[v4]",
            f"[v4]subtitles='{ff_path(ass)}':fontsdir='{ff_path('C:/Windows/Fonts')}'[v5]",
            f"[v5]drawtext=fontfile='{ff_path(FONT_LATIN)}':textfile='{ff_path(source)}':fontsize=36:fontcolor=white:x=62:y=1472:borderw=3:bordercolor=black[v6]",
        ]

        last = "v6"
        if logo_input is not None:
            filters += [
                f"[{logo_input}:v]scale=145:145,format=rgba[logo]",
                f"[{last}][logo]overlay=58:1588[vlogo]",
            ]
            last = "vlogo"
        filters.append(
            f"[{last}]drawtext=fontfile='{ff_path(FONT_ZH)}':textfile='{ff_path(brand)}':"
            "fontsize=92:fontcolor=#E0E0E0:x=225:y=1612:borderw=6:bordercolor=black[v]"
        )

        run([
            _ffmpeg(), "-y", "-filter_threads", "1", "-filter_complex_threads", "1",
            *inputs, "-t", f"{duration:.3f}",
            "-filter_complex", ";".join(filters),
            "-map", "[v]", "-map", f"{audio_input}:a:0",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out),
        ], output_path=out, expected_duration=duration)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("job_key", help="e.g. 2026-05-19/job_180")
    parser.add_argument("--version", default="short", help="Accepted for job_runner compatibility.")
    parser.add_argument("--output", default="output.mp4")
    args = parser.parse_args()
    print(render(args.job_key, args.output))


if __name__ == "__main__":
    main()
