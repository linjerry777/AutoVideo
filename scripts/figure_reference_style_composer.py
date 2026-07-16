#!/usr/bin/env python3
"""Render a figure quote in a high-retention Shorts reference layout.

This is a DORO-owned version of the observed style:
- bold two-line hook
- large source clip with bilingual quote captions
- source credit and DORO brand strip
- a second DORO analysis section using our narration
"""
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
VIDEO_Y = 270
VIDEO_H = 1245
SOURCE_Y = 1518
BRAND_Y = 1588
FONT_ZH = Path("C:/Windows/Fonts/msjhbd.ttc")
FONT_LATIN = Path("C:/Windows/Fonts/arialbd.ttf")
DORO_LOGO = BASE_DIR / "assets" / "brand" / "doro_insight_logo.png"


ZH_OVERRIDES = [
    ("check every month", "我不只是想每個月收到一張支票"),
    ("ownership share", "我想擁有 AI 創造價值的一部分"),
    ("compound and get more valuable", "它會複利增值，越來越有價值"),
    ("Universal basic wealth", "所以我更喜歡全民基本財富"),
    ("extreme wealth", "我想要的是每個人都有極大財富"),
    ("co-create the future", "人們真正想要的是一起創造未來"),
    ("scientific inventions", "即使 AI 發明新科學，人類也要參與"),
    ("cut corners on AI safety", "AI 安全不能偷工減料"),
    ("real big deal", "這會是非常大的事"),
    ("negative outcomes", "有些負面後果太嚴重"),
    ("recover from", "可能根本無法挽回"),
    ("translation", "它還能即時翻譯"),
    ("hearing", "對聽力輔助會是重大改變"),
    ("orders of magnitude", "使用量會成倍暴增"),
    ("intelligence", "智慧正在變成日用品"),
]


def _ffmpeg() -> str:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        return ffmpeg
    raise RuntimeError("ffmpeg not found")


def ff_path(path: Path | str) -> str:
    return str(path).replace("\\", "/").replace(":", "\\:")


def run(cmd: list[str]) -> None:
    result = subprocess.run(cmd, text=True, encoding="utf-8", errors="replace", capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-1200:] or result.stdout[-1200:])


def clean_text(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text or "")
    return re.sub(r"\s+", " ", text).strip()


def read_json(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8", errors="replace"))


def read_news(job_dir: Path) -> tuple[dict, dict]:
    data = read_json(job_dir / "news.json")
    item = (data.get("items") or [{}])[0]
    return data, item


def probe_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nk=1:nw=1", str(path)],
        text=True,
        capture_output=True,
    )
    return float((result.stdout or "0").strip() or 0)


def parse_transcript_window(window: str) -> list[dict]:
    rows = []
    line_re = re.compile(r"^\[(?P<start>\d+(?:\.\d+)?)-(?P<end>\d+(?:\.\d+)?)\]\s*(?P<text>.*)$")
    for line in (window or "").splitlines():
        match = line_re.match(line.strip())
        if match:
            rows.append({
                "start": float(match.group("start")),
                "end": float(match.group("end")),
                "text": clean_text(match.group("text")),
            })
    return rows


def zh_for(en: str) -> str:
    low = en.lower()
    for needle, zh in ZH_OVERRIDES:
        if needle.lower() in low:
            return zh
    if len(en.split()) <= 8:
        return "這句話不只是表面意思"
    return "關鍵不是技術本身，而是它會改變分配方式"


def split_zh(text: str, max_chars: int = 14) -> str:
    text = clean_text(text)
    if len(text) <= max_chars:
        return text
    cut = max_chars
    for mark in "，、：； ":
        idx = text.rfind(mark, 0, max_chars + 1)
        if idx >= 6:
            cut = idx + (0 if mark == " " else 1)
            break
    return text[:cut].strip() + r"\N" + text[cut:].strip()


def split_zh_chunks(text: str, max_chars: int = 17) -> list[str]:
    text = clean_text(text)
    if not text:
        return []
    parts = [p.strip() for p in re.split(r"(?<=[。！？；，、])", text) if p.strip()]
    chunks: list[str] = []
    for part in parts or [text]:
        while len(part) > max_chars:
            cut = max_chars
            for mark in "，、；： ":
                idx = part.rfind(mark, 0, max_chars + 1)
                if idx >= 6:
                    cut = idx + (0 if mark == " " else 1)
                    break
            chunks.append(part[:cut].strip())
            part = part[cut:].strip()
        if part:
            chunks.append(part)
    return chunks


def split_en_chunks(text: str, max_chars: int = 62) -> list[str]:
    words = clean_text(text).split()
    chunks: list[str] = []
    current: list[str] = []
    for word in words:
        candidate = " ".join([*current, word])
        if current and len(candidate) > max_chars:
            chunks.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        chunks.append(" ".join(current))
    return chunks


def quote_rows_from_analysis(item: dict, duration: float) -> list[dict]:
    zh_chunks = split_zh_chunks(item.get("quote_zh") or "")
    en_chunks = split_en_chunks(item.get("quote_original") or "")
    count = max(len(zh_chunks), len(en_chunks))
    if count <= 0:
        return []
    start_at = 0.8
    usable = max(3.0, duration - start_at - 0.6)
    step = usable / count
    rows = []
    for idx in range(count):
        rows.append({
            "start": start_at + idx * step,
            "end": min(duration, start_at + (idx + 1) * step + 0.15),
            "zh": zh_chunks[min(idx, len(zh_chunks) - 1)] if zh_chunks else "",
            "en": en_chunks[min(idx, len(en_chunks) - 1)] if en_chunks else "",
        })
    return rows


def ass_time(seconds: float) -> str:
    centis = int(round(max(0, seconds) * 100))
    h, rem = divmod(centis, 360000)
    m, rem = divmod(rem, 6000)
    s, c = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{c:02d}"


def write_quote_ass(item: dict, duration: float, path: Path) -> None:
    clip_start = float(item.get("clip_start") or 0)
    origin = max(0.0, clip_start - 2.0)
    rows = quote_rows_from_analysis(item, duration)
    if not rows:
        for cue in parse_transcript_window(item.get("transcript_window") or ""):
            start = max(0.0, cue["start"] - origin)
            end = max(start + 0.7, cue["end"] - origin)
            if start <= duration:
                rows.append({
                    "start": start,
                    "end": min(duration, end),
                    "zh": zh_for(cue["text"]),
                    "en": cue["text"],
                })
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: ZH,Microsoft JhengHei,76,&H00FFFFFF,&H000000FF,&H00000000,&HAA000000,-1,0,0,0,100,100,0,0,1,6,0,2,54,54,835,1
Style: EN,Arial,44,&H00FFFFFF,&H000000FF,&H00000000,&HAA000000,0,0,0,0,100,100,0,0,1,4,0,2,84,84,710,1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""
    lines = [header]
    for row in rows:
        start = ass_time(row["start"])
        end = ass_time(row["end"])
        lines.append(f"Dialogue: 0,{start},{end},ZH,,0,0,0,,{split_zh(row['zh'])}\n")
        lines.append(f"Dialogue: 1,{start},{end},EN,,0,0,0,,{clean_text(row['en'])}\n")
    path.write_text("".join(lines), encoding="utf-8")


def write_analysis_ass(job_dir: Path, item: dict, duration: float, path: Path) -> None:
    timing_file = job_dir / "short" / "audio" / "audio_01_timing.json"
    rows: list[dict] = []
    if timing_file.exists():
        try:
            rows = list(read_json(timing_file))
        except Exception:
            rows = []
    if not rows:
        fallback = item.get("script_short") or item.get("summary") or "這段話的重點，是 AI 正在改變普通人的位置。"
        rows = [{"text": fallback, "start": 0.0, "end": duration}]

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: AN,Microsoft JhengHei,84,&H00FFFFFF,&H000000FF,&H00000000,&HAA000000,-1,0,0,0,100,100,0,0,1,7,0,2,70,70,805,1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""
    lines = [header]
    for row in rows:
        start = float(row.get("start") or 0)
        end = min(duration, max(start + 0.7, float(row.get("end") or duration)))
        if start <= duration:
            lines.append(f"Dialogue: 0,{ass_time(start)},{ass_time(end)},AN,,0,0,0,,{split_zh(row.get('text') or '', 13)}\n")
    path.write_text("".join(lines), encoding="utf-8")


def headline_for(item: dict) -> tuple[str, str]:
    figure = (item.get("figure_name") or "科技大咖").replace(" AI", "")
    if "Sam" in figure:
        return "為什麼 Sam 說", "普通人要有 AI 股權"
    if "Jensen" in figure or "黃仁勳" in figure:
        return "為什麼黃仁勳說", "AI 開始替公司打工"
    if "Elon" in figure:
        return "為什麼馬斯克說", "AI 安全不能省"
    if "Mark" in figure:
        return "為什麼祖克柏說", "眼鏡會改變溝通"
    if "Bill" in figure or "Gates" in figure:
        return "為什麼比爾蓋茲說", "智慧會變成產品"
    if "Satya" in figure or "Nadella" in figure:
        return "為什麼 Satya 說", "AI 會變成思考工具"
    return f"{figure}說", item.get("title") or item.get("hook") or "這句話值得聽"


def add_brand_filters(filters: list[str], last: str, source_file: Path, brand_file: Path, logo_input: int | None) -> str:
    filters.append(
        f"[{last}]drawtext=fontfile='{ff_path(FONT_LATIN)}':textfile='{ff_path(source_file)}':"
        f"fontsize=46:fontcolor=white:x=62:y={SOURCE_Y}:borderw=3:bordercolor=black[vsrc]"
    )
    last = "vsrc"
    if logo_input is not None and DORO_LOGO.exists():
        filters += [
            f"[{logo_input}:v]scale=150:150,format=rgba[logo]",
            f"[{last}][logo]overlay=58:{BRAND_Y}[vlogo]",
        ]
        last = "vlogo"
    filters.append(
        f"[{last}]drawtext=fontfile='{ff_path(FONT_ZH)}':textfile='{ff_path(brand_file)}':"
        f"fontsize=106:fontcolor=#E0E0E0:x=230:y={BRAND_Y + 22}:borderw=6:bordercolor=black[v]"
    )
    return "v"


def render_quote_part(job_dir: Path, item: dict, broll: Path, out: Path, duration: float) -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        line1, line2 = headline_for(item)
        line1_file = tmp / "headline_1.txt"
        line2_file = tmp / "headline_2.txt"
        source_file = tmp / "source.txt"
        brand_file = tmp / "brand.txt"
        ass = tmp / "quote.ass"
        line1_file.write_text(line1, encoding="utf-8")
        line2_file.write_text(line2, encoding="utf-8")
        source_file.write_text(f"Source: {item.get('source_name') or item.get('source') or 'YouTube'}", encoding="utf-8")
        brand_file.write_text("DORO 解析", encoding="utf-8")
        write_quote_ass(item, duration, ass)

        inputs = ["-i", str(broll)]
        logo_input = None
        if DORO_LOGO.exists():
            logo_input = 1
            inputs += ["-loop", "1", "-i", str(DORO_LOGO)]
        filters = [
            f"color=c=black:s={W}x{H}:r=30:d={duration:.3f}[canvas]",
            f"[0:v]scale={W}:{VIDEO_H}:force_original_aspect_ratio=increase,crop={W}:{VIDEO_H},eq=contrast=1.05:saturation=1.06[main]",
            f"[canvas][main]overlay=0:{VIDEO_Y}[v0]",
            f"[v0]drawtext=fontfile='{ff_path(FONT_ZH)}':textfile='{ff_path(line1_file)}':fontsize=98:fontcolor=#FFF238:x=(w-text_w)/2:y=28:borderw=6:bordercolor=black[v1]",
            f"[v1]drawtext=fontfile='{ff_path(FONT_ZH)}':textfile='{ff_path(line2_file)}':fontsize=104:fontcolor=white:x=(w-text_w)/2:y=136:borderw=6:bordercolor=black[v2]",
            f"[v2]subtitles='{ff_path(ass)}':fontsdir='{ff_path('C:/Windows/Fonts')}'[v3]",
        ]
        add_brand_filters(filters, "v3", source_file, brand_file, logo_input)
        run([
            _ffmpeg(), "-y", *inputs, "-t", f"{duration:.3f}",
            "-filter_complex", ";".join(filters), "-map", "[v]", "-map", "0:a:0?",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out),
        ])


def render_analysis_part(job_dir: Path, item: dict, broll: Path, audio: Path, out: Path) -> None:
    duration = max(6.0, probe_duration(audio))
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        line1_file = tmp / "analysis_1.txt"
        line2_file = tmp / "analysis_2.txt"
        source_file = tmp / "source.txt"
        brand_file = tmp / "brand.txt"
        ass = tmp / "analysis.ass"
        line1, line2 = headline_for(item)
        line1_file.write_text(line1, encoding="utf-8")
        line2_file.write_text(line2, encoding="utf-8")
        source_file.write_text("Commentary: DORO", encoding="utf-8")
        brand_file.write_text("DORO 解析", encoding="utf-8")
        write_analysis_ass(job_dir, item, duration, ass)

        inputs = ["-stream_loop", "-1", "-i", str(broll), "-i", str(audio)]
        logo_input = None
        if DORO_LOGO.exists():
            logo_input = 2
            inputs += ["-loop", "1", "-i", str(DORO_LOGO)]
        filters = [
            f"color=c=black:s={W}x{H}:r=30:d={duration:.3f}[canvas]",
            f"[0:v]scale={W}:{VIDEO_H}:force_original_aspect_ratio=increase,crop={W}:{VIDEO_H},eq=brightness=-0.16:contrast=1.05:saturation=0.92[main]",
            f"[canvas][main]overlay=0:{VIDEO_Y}[v0]",
            f"[v0]drawtext=fontfile='{ff_path(FONT_ZH)}':textfile='{ff_path(line1_file)}':fontsize=98:fontcolor=#FFF238:x=(w-text_w)/2:y=28:borderw=6:bordercolor=black[v1]",
            f"[v1]drawtext=fontfile='{ff_path(FONT_ZH)}':textfile='{ff_path(line2_file)}':fontsize=104:fontcolor=white:x=(w-text_w)/2:y=136:borderw=6:bordercolor=black[v2]",
            f"[v2]subtitles='{ff_path(ass)}':fontsdir='{ff_path('C:/Windows/Fonts')}'[v3]",
        ]
        add_brand_filters(filters, "v3", source_file, brand_file, logo_input)
        run([
            _ffmpeg(), "-y", *inputs, "-t", f"{duration:.3f}",
            "-filter_complex", ";".join(filters), "-map", "[v]", "-map", "1:a:0",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out),
        ])


def concat(parts: list[Path], out: Path) -> None:
    with tempfile.TemporaryDirectory() as td:
        list_file = Path(td) / "concat.txt"
        list_file.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
        run([_ffmpeg(), "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(out)])


def render(job_key: str, output_name: str) -> Path:
    job_dir = PIPELINE_DIR / job_key
    broll = job_dir / "broll" / "broll_01.mp4"
    audio = job_dir / "short" / "audio" / "audio_01.mp3"
    if not broll.exists():
        raise FileNotFoundError(broll)
    if not audio.exists():
        raise FileNotFoundError(audio)
    _data, item = read_news(job_dir)
    out = job_dir / "short" / output_name
    out.parent.mkdir(parents=True, exist_ok=True)
    quote_duration = min(probe_duration(broll), 25.0)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        quote_part = tmp / "quote.mp4"
        analysis_part = tmp / "analysis.mp4"
        render_quote_part(job_dir, item, broll, quote_part, quote_duration)
        render_analysis_part(job_dir, item, broll, audio, analysis_part)
        concat([quote_part, analysis_part], out)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("job_key", help="e.g. 2026-05-19/figure_ready_tech_02_sam")
    parser.add_argument("--output", default="reference_style_output.mp4")
    args = parser.parse_args()
    print(render(args.job_key, args.output))


if __name__ == "__main__":
    main()
