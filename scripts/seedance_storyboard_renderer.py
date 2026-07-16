#!/usr/bin/env python3
"""Render an approved storyboard candidate through BytePlus ModelArk Seedance.

The renderer is intentionally sequential. It submits one image-to-video task,
polls it to completion, downloads the 4-second segment, normalizes dimensions,
then starts the next segment.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import requests

BASE_DIR = Path(__file__).resolve().parents[1]
PIPELINE_DIR = BASE_DIR / "pipeline"

try:
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env", override=False)
except Exception:
    pass

POST_URL = "https://ark.ap-southeast.bytepluses.com/api/v3/contents/generations/tasks"
# BytePlus/ModelArk 1.0 Pro model version.
MODEL = os.getenv("SEEDANCE_MODEL", "seedance-1-0-pro-250528")
RESOLUTION = os.getenv("SEEDANCE_RESOLUTION", "480p")
GENERATE_AUDIO = os.getenv("SEEDANCE_GENERATE_AUDIO", "false").lower() in {"1", "true", "yes", "on"}
OUTPUT_W = int(os.getenv("SEEDANCE_OUTPUT_W", "1080"))
OUTPUT_H = int(os.getenv("SEEDANCE_OUTPUT_H", "1920"))

sys.path.insert(0, str(BASE_DIR))

from web.db import get_storyboard_candidate, update_storyboard_candidate, update_storyboard_frame  # noqa: E402


def _pipeline_rel(path: Path) -> str:
    return str(path.relative_to(PIPELINE_DIR)).replace("\\", "/")


def _headers() -> dict[str, str]:
    key = os.getenv("ARK_API_KEY", "").strip()
    if not key:
        raise RuntimeError("ARK_API_KEY is not set")
    if key.lower().startswith("bearer "):
        key = key.split(" ", 1)[1]
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def _frame_b64(path: Path) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def _task_video_url(task: dict[str, Any]) -> str:
    content = task.get("content") or {}
    if isinstance(content, dict):
        if content.get("video_url"):
            return str(content["video_url"])
        video = content.get("video")
        if isinstance(video, dict) and video.get("url"):
            return str(video["url"])
    data = task.get("data") or {}
    if isinstance(data, dict):
        if data.get("video_url"):
            return str(data["video_url"])
        result = data.get("result") or {}
        if isinstance(result, dict) and result.get("video_url"):
            return str(result["video_url"])
    raise RuntimeError(f"task succeeded but returned no video URL: {str(task)[:500]}")


def submit_seedance_task(
    frame_path: Path,
    prompt: str,
    duration: int = 4,
    resolution: str = RESOLUTION,
    last_frame_path: Path | None = None,
) -> str:
    body = {
        "model": MODEL,
        "content": [
            {"type": "text", "text": prompt},
            {
                "type": "image_url",
                "image_url": {"url": _frame_b64(frame_path)},
                "role": "first_frame",
            },
        ],
        "ratio": "9:16",
        "duration": duration,
        "resolution": resolution,
        "watermark": False,
        "generate_audio": GENERATE_AUDIO,
    }
    if last_frame_path is not None:
        body["content"].append(
            {
                "type": "image_url",
                "image_url": {"url": _frame_b64(last_frame_path)},
                "role": "last_frame",
            }
        )
    resp = requests.post(POST_URL, headers=_headers(), json=body, timeout=180)
    resp.raise_for_status()
    data = resp.json()
    task_id = data.get("id") or data.get("task_id") or (data.get("data") or {}).get("id")
    if not task_id:
        raise RuntimeError(f"Seedance did not return a task id: {str(data)[:500]}")
    return str(task_id)


def poll_seedance_task(task_id: str, interval: int = 10, timeout: int = 1800) -> str:
    deadline = time.time() + timeout
    url = f"{POST_URL}/{task_id}"
    while time.time() < deadline:
        resp = requests.get(url, headers=_headers(), timeout=120)
        resp.raise_for_status()
        data = resp.json()
        status = str(data.get("status") or (data.get("data") or {}).get("status") or "").lower()
        if status == "succeeded":
            return _task_video_url(data)
        if status in {"failed", "expired", "cancelled", "canceled"}:
            err = data.get("error") or (data.get("data") or {}).get("error") or {}
            message = err.get("message") if isinstance(err, dict) else str(err)
            raise RuntimeError(f"Seedance task {task_id} {status}: {message or str(data)[:500]}")
        time.sleep(interval)
    raise TimeoutError(f"Seedance task {task_id} timed out after {timeout}s")


def download_file(url: str, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=300) as resp:
        resp.raise_for_status()
        with output.open("wb") as fh:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    fh.write(chunk)


def run_ffmpeg(args: list[str]) -> None:
    subprocess.run(args, cwd=str(BASE_DIR), check=True)


def normalize_segment(input_path: Path, output_path: Path) -> None:
    run_ffmpeg(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(input_path),
            "-vf",
            f"scale={OUTPUT_W}:{OUTPUT_H}:force_original_aspect_ratio=increase,crop={OUTPUT_W}:{OUTPUT_H},format=yuv420p",
            "-c:v",
            "libx264",
            "-profile:v",
            "baseline",
            "-level",
            "4.2",
            "-r",
            "24",
            "-c:a",
            "aac",
            "-shortest",
            str(output_path),
        ]
    )


def concat_segments(paths: list[Path], output_path: Path) -> None:
    concat_file = output_path.parent / "concat.txt"
    concat_file.write_text(
        "\n".join(f"file '{str(path.resolve()).replace(chr(92), '/')}'" for path in paths) + "\n",
        encoding="utf-8",
    )
    run_ffmpeg(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-vf",
            f"scale={OUTPUT_W}:{OUTPUT_H}:force_original_aspect_ratio=increase,crop={OUTPUT_W}:{OUTPUT_H},format=yuv420p",
            "-c:v",
            "libx264",
            "-profile:v",
            "baseline",
            "-level",
            "4.2",
            "-r",
            "24",
            "-c:a",
            "aac",
            "-shortest",
            str(output_path),
        ]
    )


def render_frame_segment(candidate_id: int, frame_id: int, force: bool = True) -> Path:
    """Render exactly one storyboard frame into its full 4-second Seedance segment."""
    item = get_storyboard_candidate(candidate_id)
    if not item:
        raise ValueError(f"storyboard candidate not found: {candidate_id}")
    frame = next((f for f in item.get("frames") or [] if int(f["id"]) == int(frame_id)), None)
    if not frame:
        raise ValueError(f"storyboard frame not found: {frame_id}")
    image_path = PIPELINE_DIR / str(frame.get("image_path") or "")
    if not image_path.exists():
        raise FileNotFoundError(image_path)

    frame_index = int(frame.get("frame_index") or 1)
    shot_code = str(frame.get("shot_code") or f"S{frame_index}")
    out_dir = image_path.parent
    segments_dir = out_dir / "segments"
    segments_dir.mkdir(parents=True, exist_ok=True)
    raw_path = segments_dir / f"segment-{frame_index:02d}-{shot_code}-raw.mp4"
    trimmed_path = segments_dir / f"segment-{frame_index:02d}-{shot_code}.mp4"

    if not force and trimmed_path.exists():
        update_storyboard_frame(frame_id, video_path=_pipeline_rel(trimmed_path), video_status="ready")
        return trimmed_path

    prompt = str(frame.get("seedance_prompt") or "")
    if frame.get("sound_prompt") and str(frame.get("sound_prompt")) not in prompt:
        prompt = f"{prompt}\nSound rules: {frame.get('sound_prompt')}"
    update_storyboard_frame(frame_id, video_status="rendering")
    task_id = submit_seedance_task(image_path, prompt)
    video_url = poll_seedance_task(task_id)
    download_file(video_url, raw_path)
    normalize_segment(raw_path, trimmed_path)
    update_storyboard_frame(
        frame_id,
        video_path=_pipeline_rel(trimmed_path),
        video_status="ready",
    )
    return trimmed_path


def _candidate_uses_pair_mode(item: dict[str, Any]) -> bool:
    reason = item.get("agent_reason") or ""
    if isinstance(reason, str):
        try:
            reason = json.loads(reason)
        except (TypeError, json.JSONDecodeError):
            return False
    return isinstance(reason, dict) and reason.get("seedance_pair_mode") is True


def render_frame_pair(candidate_id: int, first: dict[str, Any], last: dict[str, Any], pair_index: int) -> Path:
    first_path = PIPELINE_DIR / str(first.get("image_path") or "")
    last_path = PIPELINE_DIR / str(last.get("image_path") or "")
    if not first_path.exists():
        raise FileNotFoundError(first_path)
    if not last_path.exists():
        raise FileNotFoundError(last_path)

    first_index = int(first.get("frame_index") or pair_index * 2 - 1)
    first_code = str(first.get("shot_code") or f"S{first_index}")
    last_index = int(last.get("frame_index") or first_index + 1)
    last_code = str(last.get("shot_code") or f"S{last_index}")
    segments_dir = first_path.parent / "segments"
    segments_dir.mkdir(parents=True, exist_ok=True)
    stem = f"segment-{pair_index:02d}-{first_code}-to-{last_code}"
    raw_path = segments_dir / f"{stem}-raw.mp4"
    output_path = segments_dir / f"{stem}.mp4"

    prompt = str(first.get("seedance_prompt") or "")
    if first.get("sound_prompt") and str(first.get("sound_prompt")) not in prompt:
        prompt = f"{prompt}\nSound rules: {first.get('sound_prompt')}"
    update_storyboard_frame(int(first["id"]), video_status="rendering")
    update_storyboard_frame(int(last["id"]), video_status="paired_with_previous")
    task_id = submit_seedance_task(first_path, prompt, last_frame_path=last_path)
    video_url = poll_seedance_task(task_id)
    download_file(video_url, raw_path)
    normalize_segment(raw_path, output_path)
    update_storyboard_frame(
        int(first["id"]),
        video_path=_pipeline_rel(output_path),
        video_status="ready",
    )
    return output_path


def render_candidate(candidate_id: int) -> Path:
    item = get_storyboard_candidate(candidate_id)
    if not item:
        raise ValueError(f"storyboard candidate not found: {candidate_id}")
    frames = item.get("frames") or []
    if not frames:
        raise ValueError("candidate has no frames")

    first_image = next((PIPELINE_DIR / str(f.get("image_path") or "") for f in frames if f.get("image_path")), None)
    if first_image is None:
        raise ValueError("candidate has no generated frame images")
    out_dir = first_image.parent
    segments_dir = out_dir / "segments"
    segments_dir.mkdir(parents=True, exist_ok=True)

    update_storyboard_candidate(candidate_id, status="approved_for_video", video_status="rendering")
    trimmed_paths: list[Path] = []
    if _candidate_uses_pair_mode(item):
        if len(frames) % 2:
            raise ValueError("pair mode requires an even number of storyboard frames")
        for offset in range(0, len(frames), 2):
            first, last = frames[offset], frames[offset + 1]
            existing_video = str(first.get("video_path") or "")
            if existing_video:
                existing_path = PIPELINE_DIR / existing_video
                if existing_path.exists():
                    trimmed_paths.append(existing_path)
                    continue
            trimmed_paths.append(render_frame_pair(candidate_id, first, last, offset // 2 + 1))
    else:
        for frame in frames:
            frame_id = int(frame["id"])
            existing_video = str(frame.get("video_path") or "")
            if existing_video:
                existing_path = PIPELINE_DIR / existing_video
                if existing_path.exists():
                    trimmed_paths.append(existing_path)
                    continue
            image_path = PIPELINE_DIR / str(frame.get("image_path") or "")
            if not image_path.exists():
                raise FileNotFoundError(image_path)
            trimmed_path = render_frame_segment(candidate_id, frame_id, force=True)
            trimmed_paths.append(trimmed_path)

    output = out_dir / "output.mp4"
    concat_segments(trimmed_paths, output)
    update_storyboard_candidate(
        candidate_id,
        output_video_path=_pipeline_rel(output),
        video_status="ready",
        status="video_ready",
    )
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate_id", type=int)
    args = parser.parse_args()
    output = render_candidate(args.candidate_id)
    print(json.dumps({"ok": True, "output": str(output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
