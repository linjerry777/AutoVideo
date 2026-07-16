#!/usr/bin/env python3
"""Render five comparison styles for one tech-figure Shorts job.

This script is intentionally a preview tool. It does not overwrite the normal
pipeline output and does not schedule or upload anything.
"""
from __future__ import annotations

import argparse
import tempfile
from dataclasses import dataclass
from pathlib import Path

import figure_reference_style_composer as base


W, H = base.W, base.H
FONT_DIR = Path("C:/Windows/Fonts")


@dataclass(frozen=True)
class Style:
    key: str
    label: str
    title1: str
    title2: str
    video_y: int
    video_h: int
    title1_size: int
    title2_size: int
    title1_color: str
    title2_color: str
    quote_zh_size: int
    quote_en_size: int
    quote_zh_margin: int
    quote_en_margin: int
    analysis_size: int
    analysis_margin: int
    source_size: int
    source_y: int
    brand_y: int
    brand_size: int
    logo_size: int
    video_filter: str
    background: str = "black"
    source_prefix: str = "Source:"


STYLES = [
    Style(
        key="01_hormozi",
        label="Hormozi strong caption",
        title1="AI 股權不是幻想",
        title2="Sam 說普通人也該分到",
        video_y=300,
        video_h=1215,
        title1_size=104,
        title2_size=82,
        title1_color="#FFF238",
        title2_color="white",
        quote_zh_size=88,
        quote_en_size=42,
        quote_zh_margin=845,
        quote_en_margin=700,
        analysis_size=90,
        analysis_margin=820,
        source_size=48,
        source_y=1518,
        brand_y=1595,
        brand_size=110,
        logo_size=150,
        video_filter="eq=contrast=1.18:saturation=1.12",
    ),
    Style(
        key="02_podcast",
        label="Podcast quote clip",
        title1="Sam Altman 的 AI 財富觀",
        title2="不是補助，而是所有權",
        video_y=250,
        video_h=1270,
        title1_size=74,
        title2_size=82,
        title1_color="white",
        title2_color="#FFF238",
        quote_zh_size=72,
        quote_en_size=38,
        quote_zh_margin=820,
        quote_en_margin=705,
        analysis_size=78,
        analysis_margin=805,
        source_size=44,
        source_y=1526,
        brand_y=1600,
        brand_size=98,
        logo_size=138,
        video_filter="eq=contrast=1.05:saturation=1.02",
    ),
    Style(
        key="03_bigthink",
        label="Big Think explainer",
        title1="為什麼 AI 時代",
        title2="普通人需要股權？",
        video_y=270,
        video_h=1245,
        title1_size=88,
        title2_size=96,
        title1_color="#FFF238",
        title2_color="white",
        quote_zh_size=76,
        quote_en_size=44,
        quote_zh_margin=835,
        quote_en_margin=710,
        analysis_size=84,
        analysis_margin=805,
        source_size=46,
        source_y=1518,
        brand_y=1588,
        brand_size=106,
        logo_size=150,
        video_filter="eq=contrast=1.05:saturation=1.06",
    ),
    Style(
        key="04_valuetainment",
        label="Valuetainment conflict",
        title1="Sam 爆出 AI 財富真相",
        title2="現金補助可能不夠了",
        video_y=290,
        video_h=1225,
        title1_size=82,
        title2_size=88,
        title1_color="#FF3939",
        title2_color="white",
        quote_zh_size=82,
        quote_en_size=40,
        quote_zh_margin=835,
        quote_en_margin=700,
        analysis_size=86,
        analysis_margin=815,
        source_size=48,
        source_y=1518,
        brand_y=1592,
        brand_size=104,
        logo_size=148,
        video_filter="eq=contrast=1.16:saturation=0.98",
    ),
    Style(
        key="05_motivation",
        label="MotivationHub emotional",
        title1="AI 不只會取代工作",
        title2="也會重分配財富",
        video_y=285,
        video_h=1230,
        title1_size=84,
        title2_size=92,
        title1_color="#FFD24A",
        title2_color="white",
        quote_zh_size=80,
        quote_en_size=40,
        quote_zh_margin=835,
        quote_en_margin=700,
        analysis_size=86,
        analysis_margin=815,
        source_size=46,
        source_y=1518,
        brand_y=1592,
        brand_size=104,
        logo_size=148,
        video_filter="eq=contrast=1.12:saturation=1.18:brightness=-0.03",
    ),
]


def write_quote_ass(item: dict, duration: float, path: Path, style: Style) -> None:
    clip_start = float(item.get("clip_start") or 0)
    origin = max(0.0, clip_start - 2.0)
    rows = []
    for cue in base.parse_transcript_window(item.get("transcript_window") or ""):
        start = max(0.0, cue["start"] - origin)
        end = max(start + 0.7, cue["end"] - origin)
        if start <= duration:
            rows.append({
                "start": start,
                "end": min(duration, end),
                "zh": base.zh_for(cue["text"]),
                "en": cue["text"],
            })

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: ZH,Microsoft JhengHei,{style.quote_zh_size},&H00FFFFFF,&H000000FF,&H00000000,&HAA000000,-1,0,0,0,100,100,0,0,1,6,0,2,54,54,{style.quote_zh_margin},1
Style: EN,Arial,{style.quote_en_size},&H00FFFFFF,&H000000FF,&H00000000,&HAA000000,0,0,0,0,100,100,0,0,1,4,0,2,84,84,{style.quote_en_margin},1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""
    lines = [header]
    for row in rows:
        start = base.ass_time(row["start"])
        end = base.ass_time(row["end"])
        lines.append(f"Dialogue: 0,{start},{end},ZH,,0,0,0,,{base.split_zh(row['zh'])}\n")
        lines.append(f"Dialogue: 1,{start},{end},EN,,0,0,0,,{base.clean_text(row['en'])}\n")
    path.write_text("".join(lines), encoding="utf-8")


def write_analysis_ass(job_dir: Path, item: dict, duration: float, path: Path, style: Style) -> None:
    timing_file = job_dir / "short" / "audio" / "audio_01_timing.json"
    rows: list[dict] = []
    if timing_file.exists():
        try:
            rows = list(base.read_json(timing_file))
        except Exception:
            rows = []
    if not rows:
        rows = [{"text": item.get("script_short") or item.get("summary") or "這句話真正的重點，是 AI 會改變財富分配。", "start": 0.0, "end": duration}]

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: AN,Microsoft JhengHei,{style.analysis_size},&H00FFFFFF,&H000000FF,&H00000000,&HAA000000,-1,0,0,0,100,100,0,0,1,7,0,2,70,70,{style.analysis_margin},1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""
    lines = [header]
    for row in rows:
        start = float(row.get("start") or 0)
        end = min(duration, max(start + 0.7, float(row.get("end") or duration)))
        if start <= duration:
            lines.append(f"Dialogue: 0,{base.ass_time(start)},{base.ass_time(end)},AN,,0,0,0,,{base.split_zh(row.get('text') or '', 13)}\n")
    path.write_text("".join(lines), encoding="utf-8")


def add_brand_filters(filters: list[str], last: str, source_file: Path, brand_file: Path, logo_input: int | None, style: Style) -> str:
    filters.append(
        f"[{last}]drawtext=fontfile='{base.ff_path(base.FONT_LATIN)}':textfile='{base.ff_path(source_file)}':"
        f"fontsize={style.source_size}:fontcolor=white:x=62:y={style.source_y}:borderw=3:bordercolor=black[vsrc]"
    )
    last = "vsrc"
    if logo_input is not None and base.DORO_LOGO.exists():
        filters += [
            f"[{logo_input}:v]scale={style.logo_size}:{style.logo_size},format=rgba[logo]",
            f"[{last}][logo]overlay=58:{style.brand_y}[vlogo]",
        ]
        last = "vlogo"
    filters.append(
        f"[{last}]drawtext=fontfile='{base.ff_path(base.FONT_ZH)}':textfile='{base.ff_path(brand_file)}':"
        f"fontsize={style.brand_size}:fontcolor=#E0E0E0:x={80 + style.logo_size}:y={style.brand_y + 22}:borderw=6:bordercolor=black[v]"
    )
    return "v"


def title_filters(style: Style, line1_file: Path, line2_file: Path) -> list[str]:
    return [
        f"[v0]drawtext=fontfile='{base.ff_path(base.FONT_ZH)}':textfile='{base.ff_path(line1_file)}':fontsize={style.title1_size}:fontcolor={style.title1_color}:x=(w-text_w)/2:y=28:borderw=7:bordercolor=black[v1]",
        f"[v1]drawtext=fontfile='{base.ff_path(base.FONT_ZH)}':textfile='{base.ff_path(line2_file)}':fontsize={style.title2_size}:fontcolor={style.title2_color}:x=(w-text_w)/2:y=136:borderw=7:bordercolor=black[v2]",
    ]


def render_quote_part(job_dir: Path, item: dict, broll: Path, out: Path, duration: float, style: Style) -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        line1_file = tmp / "headline_1.txt"
        line2_file = tmp / "headline_2.txt"
        source_file = tmp / "source.txt"
        brand_file = tmp / "brand.txt"
        ass = tmp / "quote.ass"
        line1_file.write_text(style.title1, encoding="utf-8")
        line2_file.write_text(style.title2, encoding="utf-8")
        source_file.write_text(f"{style.source_prefix} {item.get('source_name') or item.get('source') or 'YouTube'}", encoding="utf-8")
        brand_file.write_text("DORO 解析", encoding="utf-8")
        write_quote_ass(item, duration, ass, style)

        inputs = ["-i", str(broll)]
        logo_input = None
        if base.DORO_LOGO.exists():
            logo_input = 1
            inputs += ["-loop", "1", "-i", str(base.DORO_LOGO)]
        filters = [
            f"color=c={style.background}:s={W}x{H}:r=30:d={duration:.3f}[canvas]",
            f"[0:v]scale={W}:{style.video_h}:force_original_aspect_ratio=increase,crop={W}:{style.video_h},{style.video_filter}[main]",
            f"[canvas][main]overlay=0:{style.video_y}[v0]",
            *title_filters(style, line1_file, line2_file),
            f"[v2]subtitles='{base.ff_path(ass)}':fontsdir='{base.ff_path(FONT_DIR)}'[v3]",
        ]
        add_brand_filters(filters, "v3", source_file, brand_file, logo_input, style)
        base.run([
            base._ffmpeg(), "-y", *inputs, "-t", f"{duration:.3f}",
            "-filter_complex", ";".join(filters), "-map", "[v]", "-map", "0:a:0?",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out),
        ])


def render_analysis_part(job_dir: Path, item: dict, broll: Path, audio: Path, out: Path, style: Style) -> None:
    duration = max(6.0, base.probe_duration(audio))
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        line1_file = tmp / "analysis_1.txt"
        line2_file = tmp / "analysis_2.txt"
        source_file = tmp / "source.txt"
        brand_file = tmp / "brand.txt"
        ass = tmp / "analysis.ass"
        line1_file.write_text(style.title1, encoding="utf-8")
        line2_file.write_text(style.title2, encoding="utf-8")
        source_file.write_text("Commentary: DORO", encoding="utf-8")
        brand_file.write_text("DORO 解析", encoding="utf-8")
        write_analysis_ass(job_dir, item, duration, ass, style)

        inputs = ["-stream_loop", "-1", "-i", str(broll), "-i", str(audio)]
        logo_input = None
        if base.DORO_LOGO.exists():
            logo_input = 2
            inputs += ["-loop", "1", "-i", str(base.DORO_LOGO)]
        filters = [
            f"color=c={style.background}:s={W}x{H}:r=30:d={duration:.3f}[canvas]",
            f"[0:v]scale={W}:{style.video_h}:force_original_aspect_ratio=increase,crop={W}:{style.video_h},{style.video_filter},eq=brightness=-0.13[main]",
            f"[canvas][main]overlay=0:{style.video_y}[v0]",
            *title_filters(style, line1_file, line2_file),
            f"[v2]subtitles='{base.ff_path(ass)}':fontsdir='{base.ff_path(FONT_DIR)}'[v3]",
        ]
        add_brand_filters(filters, "v3", source_file, brand_file, logo_input, style)
        base.run([
            base._ffmpeg(), "-y", *inputs, "-t", f"{duration:.3f}",
            "-filter_complex", ";".join(filters), "-map", "[v]", "-map", "1:a:0",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out),
        ])


def render_style(job_key: str, style: Style, output_dir: Path | None = None) -> Path:
    job_dir = base.PIPELINE_DIR / job_key
    broll = job_dir / "broll" / "broll_01.mp4"
    audio = job_dir / "short" / "audio" / "audio_01.mp3"
    if not broll.exists():
        raise FileNotFoundError(broll)
    if not audio.exists():
        raise FileNotFoundError(audio)
    _data, item = base.read_news(job_dir)
    out_dir = output_dir or (job_dir / "short")
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"style_compare_{style.key}.mp4"
    quote_duration = min(base.probe_duration(broll), 25.0)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        quote_part = tmp / "quote.mp4"
        analysis_part = tmp / "analysis.mp4"
        render_quote_part(job_dir, item, broll, quote_part, quote_duration, style)
        render_analysis_part(job_dir, item, broll, audio, analysis_part, style)
        base.concat([quote_part, analysis_part], out)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("job_key", help="e.g. 2026-05-19/figure_ready_tech_02_sam")
    parser.add_argument("--style", choices=[s.key for s in STYLES] + ["all"], default="all")
    parser.add_argument("--output-dir")
    args = parser.parse_args()

    output_dir = Path(args.output_dir).resolve() if args.output_dir else None
    styles = STYLES if args.style == "all" else [next(s for s in STYLES if s.key == args.style)]
    for style in styles:
        print(f"{style.key} | {style.label} | {render_style(args.job_key, style, output_dir)}")


if __name__ == "__main__":
    main()
