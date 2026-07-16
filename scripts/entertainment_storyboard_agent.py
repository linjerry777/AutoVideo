#!/usr/bin/env python3
"""Build movie-language pet storyboard candidates for the entertainment_yt lane.

This lane is deliberately token-cheap: it researches/tracks a trend, converts a
recognizable film or TV shot grammar into a cat daily-disaster premise, and
generates one vertical 9:16 storyboard still per shot. Video-model calls happen
only after the user explicitly approves a candidate from the dashboard.
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests

BASE_DIR = Path(__file__).resolve().parents[1]
PIPELINE_DIR = BASE_DIR / "pipeline"

sys.path.insert(0, str(BASE_DIR))

from web.db import (  # noqa: E402
    create_storyboard_candidate,
    get_setting,
    get_storyboard_candidate,
    update_storyboard_candidate,
    update_storyboard_frame,
)


NEGATIVE_IMAGE_RULES = (
    "No grid. No storyboard sheet. No split panels. No text. No logo. "
    "No subtitles. No watermark. No cartoon. No anime. No human face close-up. "
    "Do not copy any copyrighted character, costume, production design, or exact movie frame."
)

DIEGETIC_SOUND_RULE = (
    "Generate only realistic diegetic sound effects and subtle room tone. "
    "No music, no soundtrack, no narration, no human speech, no subtitles."
)


FILM_LANGUAGE_PATTERNS: list[dict[str, Any]] = [
    {
        "reference_title": "Interstellar",
        "reference_scene": "future observer warns the past",
        "title_seed": "不要被罐罐誘惑",
        "shot_language": (
            "Alternate two timelines. A-line shots feel like a future observer looking through a dark time layer "
            "at the past room, while the past cat remains third-person in frame. B-line shots are reaction close-ups "
            "of the future cat warning from the window. Cuts accelerate until the warning fails."
        ),
        "adaptation_rule": (
            "Future cat watches past cat being tempted by canned food. Future cat tries to warn it. "
            "The warning fails; the owner hand takes past cat to bath time. Ending: towel-wrapped cat accepts "
            "a compensation can with defeated dignity."
        ),
        "beats": [
            ("A1", "誘惑出現", 2.0, "future-cat POV from a dark time layer watches the same white cat in the past kitchen notice a shiny food can on the floor, past cat shown third-person, cautious curiosity", "subtle room tone, tiny metal can roll, soft cat breath"),
            ("B1", "未來警告", 1.8, "third-person close shot of the future white cat pressed against a rainy window, paw raised as if warning the past, urgent eyes, dark blue night light", "cat paw taps glass, worried meow, distant rain"),
            ("A2", "伸手了", 1.6, "future observer view into the warm kitchen, past cat slowly reaches one paw toward the can, owner hand blurred in the background holding a towel", "claws lightly scrape floor, can lid clicks faintly"),
            ("B2", "快停下", 1.5, "future cat reaction close-up at the window, mouth open in a desperate silent shout, paw smearing condensation on glass, faster emotional rhythm", "sharp cat meow, paw slap on glass"),
            ("A3", "洗澡陷阱", 2.2, "past cat grabs the can, owner hand gently lifts the cat, bathroom light spills into the kitchen doorway, the can remains on floor like bait", "can clatter, towel rustle, bathroom water starts"),
            ("C1", "補償罐罐", 2.4, "ending shot in bathroom doorway, wet towel-wrapped white cat sits miserably beside the same can, defeated but eating, cinematic bittersweet warm light", "wet cat tiny protest meow, towel rub, can opening pop"),
        ],
    },
    {
        "reference_title": "Squid Game",
        "reference_scene": "freeze-or-get-caught game",
        "title_seed": "偷肉泥定格挑戰",
        "shot_language": (
            "Simple game-rule editing: wide surveillance view, sudden command, freeze frame tension, close-ups of tiny movement, "
            "then an abrupt consequence. The comedy comes from strict rules applied to a tiny pet crime."
        ),
        "adaptation_rule": (
            "A cat tries to steal a churu snack while the owner turns away. Every time the owner turns back, the cat freezes. "
            "A tail twitch exposes it and the owner confiscates the snack."
        ),
        "beats": [
            ("S1", "遊戲開始", 2.0, "high wide angle of a bright living room, white cat at one side, unopened churu snack on low table, owner hand leaving frame, tense game-show stillness", "room tone, plastic snack packet crinkle"),
            ("S2", "第一步", 1.7, "low floor tracking shot beside the cat paws as the cat creeps toward the churu packet, shallow depth of field, mischievous focus", "soft paw steps, tiny plastic crinkle"),
            ("S3", "主人回頭", 1.5, "sudden medium shot of owner silhouette turning back from hallway, cat instantly frozen mid-step near the table, absurd tension", "quick cloth rustle, silence drop"),
            ("S4", "尾巴出賣", 1.6, "close-up of the cat tail twitching by one centimeter beside the churu packet, the rest of the cat perfectly frozen", "single tail brush, suspense room tone"),
            ("S5", "證據確鑿", 2.0, "owner hand enters frame and lifts the churu packet away while cat stares forward pretending nothing happened", "packet lifted, disappointed cat chirp"),
            ("S6", "任務失敗", 2.2, "final deadpan portrait of the white cat sitting far from the table, snack gone, dramatic empty space, daylight living room", "small defeated meow, distant room tone"),
        ],
    },
    {
        "reference_title": "Jurassic Park",
        "reference_scene": "predator pursuit and hiding",
        "title_seed": "澡盆追捕戰",
        "shot_language": (
            "Creature-chase grammar: hiding close-ups, offscreen threat sound, slow reveal, sudden chase, then a breathless hideout. "
            "The danger is reinterpreted as bath time."
        ),
        "adaptation_rule": (
            "The cat hides from bath time. The towel and bathtub become the pursuing monster. The cat nearly escapes, then gets wrapped."
        ),
        "beats": [
            ("J1", "聽見水聲", 2.0, "close shot under a sofa, white cat hiding in shadow, bathroom light reflected on the floor, eyes alert", "running bath water, quiet cat breathing"),
            ("J2", "毛巾逼近", 1.8, "low angle hallway shot, fluffy towel dragged by owner hand enters frame like a looming creature, cat ears visible behind furniture", "towel drag on floor, water echo"),
            ("J3", "慢慢回頭", 1.6, "cat close-up turning its head slowly, pupils wide, warm home shadows, cinematic fear but cute", "tiny worried meow, floor creak"),
            ("J4", "爆衝", 1.5, "dynamic motion shot of the white cat sprinting across hallway away from the towel, paws blurred but face visible", "rapid paw taps, towel whoosh"),
            ("J5", "被包住", 2.0, "owner hand gently wraps the cat in a towel near bathroom doorway, cat face poking out with betrayed expression", "soft towel wrap, water splash"),
            ("J6", "濕貓結局", 2.4, "wet towel-wrapped cat sits beside bathtub, grumpy but safe, bath steam behind, cinematic soft bathroom light", "water dripping, small grumpy meow"),
        ],
    },
    {
        "reference_title": "Dune 2",
        "reference_scene": "desert rise and conquest ritual",
        "title_seed": "征服掃地機器人",
        "shot_language": (
            "Epic scale grammar applied to a tiny domestic object: vast low angles, slow ritual movement, dust-like light, heroic reveal, "
            "then absurd domination of a machine."
        ),
        "adaptation_rule": (
            "The robot vacuum becomes a desert beast. The cat studies it, approaches with ritual seriousness, then stands on it like a conqueror."
        ),
        "beats": [
            ("D1", "沙漠巨獸", 2.0, "low floor-level shot of a robot vacuum emerging from a dusty sunbeam across wooden floor, white cat watches from the distance", "robot vacuum hum, low room tone"),
            ("D2", "觀察路線", 1.8, "profile close-up of the cat eyes tracking the robot vacuum, sunlight strip across fur, serious heroic mood", "steady robot hum, soft whisker movement"),
            ("D3", "試探一掌", 1.6, "cat paw touches the robot vacuum edge as it rotates, macro close-up, tense but funny", "paw tap, robot motor change"),
            ("D4", "跳上去", 1.7, "medium dynamic shot of the cat stepping onto the moving robot vacuum, body balanced, epic low angle", "plastic wheel rumble, tiny cat chirp"),
            ("D5", "開始巡航", 2.0, "wide vertical shot of the cat riding the robot vacuum across the living room like a ruler crossing dunes", "robot hum moving across room"),
            ("D6", "王座成立", 2.3, "final heroic portrait of the cat sitting on the stopped robot vacuum in a sunbeam, calm conqueror expression", "robot beep, proud silence, soft meow"),
        ],
    },
    {
        "reference_title": "John Wick",
        "reference_scene": "revenge preparation montage",
        "title_seed": "空罐罐復仇",
        "shot_language": (
            "Preparation montage: object close-ups, precise hands, ritualized focus, fast inserts, then a clean action payoff. "
            "The revenge target becomes an empty can."
        ),
        "adaptation_rule": (
            "The cat finds an empty can instead of food, prepares like a tiny professional, then knocks the empty can off the counter."
        ),
        "beats": [
            ("W1", "發現空罐", 1.8, "close shot of white cat staring at an empty food can on kitchen counter, betrayed eyes, moody evening light", "metal can wobble, quiet room tone"),
            ("W2", "整理裝備", 1.6, "macro shot of cat paw flexing on countertop, claws barely visible, serious ritual preparation mood", "claws tap counter, soft breath"),
            ("W3", "鎖定目標", 1.6, "over-shoulder shot from behind cat head looking at the empty can, shallow focus, can centered like a target", "tiny tail swish, metallic tick"),
            ("W4", "慢步靠近", 1.8, "low tracking shot along the counter as cat advances toward the can, controlled movement, cinematic tension", "soft paw steps on counter"),
            ("W5", "一掌制裁", 1.5, "fast action close-up of cat paw striking the empty can, can flying off counter, motion blur but clear paw", "sharp metal clank, cat chirp"),
            ("W6", "冷酷收尾", 2.2, "cat sits calmly on counter after the can falls, dramatic kitchen shadows, deadpan satisfied expression", "can rolling on floor, silence, soft meow"),
        ],
    },
]


def today_key() -> str:
    return datetime.now(ZoneInfo("Asia/Taipei")).date().isoformat()


def compact(text: Any, limit: int = 120) -> str:
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
    return cleaned if len(cleaned) <= limit else cleaned[: limit - 1] + "…"


def collect_trends(limit: int) -> list[dict[str, Any]]:
    try:
        from scripts import media_ops_agent

        items = media_ops_agent.collect_external_trends(limit_per_source=max(4, limit))
    except Exception as exc:
        print(f"[storyboard] external trend fetch failed: {exc}", file=sys.stderr)
        items = []

    preferred = []
    for item in items:
        text = f"{item.get('title', '')} {item.get('summary', '')} {item.get('source_type', '')}".lower()
        if any(k in text for k in ("meme", "movie", "film", "shorts", "tiktok", "youtube", "viral", "kpop", "mv")):
            preferred.append(item)
    return (preferred or items)[:limit]


def fallback_trends(limit: int) -> list[dict[str, Any]]:
    seeds = [
        ("貓咪日常災難：罐罐誘惑", "use a classic movie scene rhythm to turn pet routine into a micro-drama", "local_seed"),
        ("貓咪日常災難：偷肉泥挑戰", "freeze-game pet comedy", "local_seed"),
        ("貓咪日常災難：洗澡追捕", "bath-time chase parody", "local_seed"),
        ("貓咪日常災難：掃地機器人王座", "tiny epic machine conquest", "local_seed"),
    ]
    return [
        {"title": title, "summary": summary, "source": source, "source_type": source, "url": f"local://storyboard/{idx}"}
        for idx, (title, summary, source) in enumerate(seeds[:limit], start=1)
    ]


def _pattern_for(index: int, trend: dict[str, Any]) -> dict[str, Any]:
    text = f"{trend.get('title', '')} {trend.get('summary', '')}".lower()
    if any(k in text for k in ("bath", "洗澡", "毛巾")):
        return FILM_LANGUAGE_PATTERNS[2]
    if any(k in text for k in ("robot", "掃地", "vacuum", "機器人")):
        return FILM_LANGUAGE_PATTERNS[3]
    if any(k in text for k in ("snack", "肉泥", "遊戲", "game")):
        return FILM_LANGUAGE_PATTERNS[1]
    return FILM_LANGUAGE_PATTERNS[(index - 1) % len(FILM_LANGUAGE_PATTERNS)]


def _visual_prompt(pattern: dict[str, Any], beat: tuple[str, str, float, str, str], index: int) -> str:
    shot_code, title, _trim, description, _sound = beat
    continuity = (
        "Continuity: same photorealistic chubby white British shorthair cat, natural fur, expressive eyes, "
        "same modern Taiwanese apartment, consistent props across shots, cinematic lighting continuity."
    )
    return (
        f"Shot {index} ({shot_code}) - {title}. "
        "Create exactly one vertical 9:16 photorealistic cinematic storyboard frame. "
        f"Composition and camera: {description}. "
        f"Shot-language reference to preserve: {pattern['shot_language']} "
        f"{continuity} Lighting must match the emotional beat. {NEGATIVE_IMAGE_RULES}"
    )


def _seedance_prompt(pattern: dict[str, Any], beat: tuple[str, str, float, str, str], index: int) -> str:
    shot_code, title, _trim, description, sound = beat
    return (
        f"Shot {index} ({shot_code}) {title}, 4 seconds, vertical 9:16. "
        f"Animate from the first frame only: {description}. "
        "Keep the cat identity and room continuity stable. Use subtle handheld cinematic motion, no fast morphing, "
        "no extra characters, no readable text, no subtitles, no logo, no watermark. "
        f"Sound: {DIEGETIC_SOUND_RULE} Specific diegetic details: {sound}."
    )


def build_candidate(trend: dict[str, Any], index: int, profile: str) -> tuple[dict, list[dict]]:
    pattern = _pattern_for(index, trend)
    source_title = compact(trend.get("title") or f"trend {index}", 90)
    title = f"奶烙出任務：{pattern['title_seed']}"
    hook = "不是貓在演電影，是用電影鏡頭語法拍一場貓貓日常災難。"
    synopsis = f"保留《{pattern['reference_title']}》片段的剪輯節奏，把衝突換成：{pattern['adaptation_rule']}"
    media_score = int(trend.get("score") or trend.get("media_ops_score") or 62) + min(index, 8)

    frames = []
    for frame_index, beat in enumerate(pattern["beats"], start=1):
        shot_code, frame_title, trim_seconds, _description, sound = beat
        frames.append(
            {
                "frame_index": frame_index,
                "shot_code": shot_code,
                "title": frame_title,
                "duration_seconds": 4,
                "trim_seconds": trim_seconds,
                "visual_prompt": _visual_prompt(pattern, beat, frame_index),
                "seedance_prompt": _seedance_prompt(pattern, beat, frame_index),
                "sound_prompt": f"{DIEGETIC_SOUND_RULE} {sound}",
            }
        )

    candidate = {
        "lane": "entertainment_storyboard",
        "target_profile": profile,
        "title": title,
        "hook": hook,
        "synopsis": synopsis,
        "reference_title": pattern["reference_title"],
        "reference_scene": pattern["reference_scene"],
        "shot_language": pattern["shot_language"],
        "adaptation_rule": pattern["adaptation_rule"],
        "source_title": source_title,
        "source_url": trend.get("url") or "",
        "source_name": trend.get("source") or trend.get("source_name") or "",
        "source_type": trend.get("source_type") or "",
        "trend_score": int(trend.get("score") or 0),
        "media_ops_score": max(0, min(100, media_score)),
        "estimated_seconds": int(round(sum(float(frame["trim_seconds"]) for frame in frames))),
        "estimated_cost_usd": round(len(frames) * 4 * 0.05, 2),
        "status": "draft",
        "video_status": "",
        "agent_reason": (
            f"Reference: {pattern['reference_title']} / {pattern['reference_scene']}. "
            "Frame-first storyboard; approve before spending Seedance tokens."
        ),
    }
    return candidate, frames


def _pipeline_rel(path: Path) -> str:
    return str(path.relative_to(PIPELINE_DIR)).replace("\\", "/")


def candidate_dir(candidate_id: int) -> Path:
    item = get_storyboard_candidate(candidate_id)
    image_paths = [str(frame.get("image_path") or "").strip() for frame in (item or {}).get("frames", [])]
    for image_path in image_paths:
        if image_path:
            rel = Path(image_path)
            return (PIPELINE_DIR / rel).parent
    return PIPELINE_DIR / "storyboards" / today_key() / f"candidate_{candidate_id}"


def _image2_request(prompt: str, output: Path, timeout: int = 300) -> None:
    from web.claude_client import generate_image

    output.parent.mkdir(parents=True, exist_ok=True)
    output.with_suffix(".prompt.txt").write_text(prompt, encoding="utf-8")
    generate_image(prompt, output, size="1024x1792", timeout=timeout)


def generate_single_storyboard_frame(candidate: dict, frame: dict, output: Path, timeout: int = 300) -> str:
    prompt = (
        f"{frame.get('visual_prompt') or ''}\n\n"
        f"Reference shot language: {candidate.get('reference_title') or ''} / {candidate.get('reference_scene') or ''}.\n"
        f"Cat adaptation rule: {candidate.get('adaptation_rule') or ''}\n"
        "Final image must be one clean 9:16 frame only."
    )
    _image2_request(prompt, output, timeout=timeout)
    return "image2_frame"


def generate_candidate_frames(candidate_id: int) -> None:
    item = get_storyboard_candidate(candidate_id)
    if not item:
        raise ValueError(f"storyboard candidate not found: {candidate_id}")
    frames = item.get("frames") or []
    if not frames:
        raise ValueError("candidate has no frames")

    out_dir = candidate_dir(candidate_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    ok_count = 0
    for frame in frames:
        frame_index = int(frame.get("frame_index") or 1)
        output = out_dir / f"frame_{frame_index:02d}_{frame.get('shot_code') or 'shot'}.jpg"
        try:
            source = generate_single_storyboard_frame(item, frame, output)
            update_storyboard_frame(
                int(frame["id"]),
                image_path=_pipeline_rel(output),
                status=source,
            )
            ok_count += 1
        except Exception as exc:
            print(f"[storyboard] image2 failed frame={frame_index}: {exc}", file=sys.stderr)
            update_storyboard_frame(int(frame["id"]), status="image_failed")
    update_storyboard_candidate(
        candidate_id,
        status="images_ready" if ok_count == len(frames) else "image_failed",
    )


def build_storyboard_sheet_prompt(candidate: dict, frames: list[dict]) -> str:
    """Legacy compatibility only. New candidates must use frame-first images."""
    shots = "\n".join(f"{f.get('frame_index')}. {f.get('visual_prompt')}" for f in frames)
    return (
        "Do not generate a storyboard sheet. Generate each 9:16 frame separately instead.\n\n"
        f"Candidate: {candidate.get('title')}\n{shots}"
    )


def generate_storyboard_sheet(candidate: dict, frames: list[dict], output: Path, timeout: int = 300) -> str:
    """Legacy endpoint shim.

    The old UI called this to generate a 2x3 contact sheet. New workflow forbids
    sheets, so this function writes a prompt note and raises a clear error.
    """
    output.parent.mkdir(parents=True, exist_ok=True)
    output.with_suffix(".prompt.txt").write_text(build_storyboard_sheet_prompt(candidate, frames), encoding="utf-8")
    raise RuntimeError("storyboard sheets are disabled; regenerate individual frames instead")


def sync_sheet_panels_to_frames(candidate_id: int, sheet_path: Path, status: str = "image2_sheet") -> None:
    raise RuntimeError("storyboard sheets are disabled; use generate_candidate_frames")


def rebuild_storyboard_sheet_from_frames(candidate_id: int) -> Path:
    raise RuntimeError("storyboard sheets are disabled; the dashboard now previews individual frames")


def run(limit: int, generate_images: bool) -> list[int]:
    profile = get_setting("autopilot_storyboard_profile", "entertainment_yt") or "entertainment_yt"
    trends = collect_trends(limit * 2) or fallback_trends(limit)
    ids: list[int] = []
    for idx, trend in enumerate(trends[:limit], start=1):
        candidate, frames = build_candidate(trend, idx, profile)
        candidate_id = create_storyboard_candidate(candidate, frames)
        ids.append(candidate_id)
        if generate_images:
            try:
                generate_candidate_frames(candidate_id)
            except Exception as exc:
                print(f"[storyboard] frame image generation failed candidate={candidate_id}: {exc}", file=sys.stderr)
                update_storyboard_candidate(candidate_id, status="image_failed")
    return ids


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=int(get_setting("autopilot_storyboard_daily_candidates", "5") or 5))
    parser.add_argument("--no-images", action="store_true", help="only create concepts and prompts")
    args = parser.parse_args()
    ids = run(max(1, min(args.limit, 10)), generate_images=not args.no_images)
    print(json.dumps({"ok": True, "candidate_ids": ids}, ensure_ascii=False))


if __name__ == "__main__":
    main()
