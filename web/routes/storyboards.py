"""Storyboard candidate pool for the entertainment_yt experiment lane."""
from __future__ import annotations

import json
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from web.db import (
    delete_storyboard_candidate,
    get_storyboard_candidate,
    list_storyboard_candidates,
    update_storyboard_candidate,
    update_storyboard_frame,
)

router = APIRouter(prefix="/api/storyboards")
BASE_DIR = Path(__file__).resolve().parents[2]
PIPELINE_DIR = BASE_DIR / "pipeline"
RUN_STATE_FILE = BASE_DIR / "data" / "storyboard_agent_status.json"


class GenerateRequest(BaseModel):
    limit: int | None = 5
    generate_images: bool | None = False


class StatusUpdate(BaseModel):
    status: str


class FrameUpdate(BaseModel):
    title: str | None = None
    visual_prompt: str | None = None
    seedance_prompt: str | None = None
    sound_prompt: str | None = None
    duration_seconds: int | None = None
    trim_seconds: float | None = None


def _write_run_state(data: dict) -> None:
    RUN_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    RUN_STATE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_run_state() -> dict:
    try:
        if RUN_STATE_FILE.exists():
            data = json.loads(RUN_STATE_FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}
    return {}


def _asset_url(path: str) -> str:
    if not path:
        return ""
    clean = path.replace("\\", "/").lstrip("/")
    return f"/pipeline_asset/{clean}"


def _decorate(item: dict) -> dict:
    item = dict(item)
    item["frame_count"] = len(item.get("frames") or [])
    item["image_count"] = sum(1 for frame in item.get("frames") or [] if frame.get("image_path"))
    item["image2_count"] = sum(1 for frame in item.get("frames") or [] if str(frame.get("status") or "").startswith("image2"))
    item["fallback_count"] = sum(1 for frame in item.get("frames") or [] if frame.get("status") == "fallback")
    item["sheet_image_url"] = _asset_url(item.get("sheet_image_path") or "")
    item["output_video_url"] = _asset_url(item.get("output_video_path") or "")
    item["video_count"] = sum(1 for frame in item.get("frames") or [] if frame.get("video_path"))
    item["frames"] = [
        {
            **frame,
            "image_url": _asset_url(frame.get("image_path") or ""),
            "video_url": _asset_url(frame.get("video_path") or ""),
        }
        for frame in item.get("frames") or []
    ]
    return item


@router.get("")
def list_storyboards(limit: int = 50, status: str | None = None):
    return {
        "items": [_decorate(item) for item in list_storyboard_candidates(limit=limit, status=status)],
        "agent": _read_run_state(),
    }


@router.get("/{candidate_id}")
def get_storyboard(candidate_id: int):
    item = get_storyboard_candidate(candidate_id)
    if not item:
        raise HTTPException(404, "storyboard candidate not found")
    return _decorate(item)


@router.post("/generate")
def generate_storyboards(req: GenerateRequest):
    limit = max(1, min(int(req.limit or 5), 10))
    generate_images = bool(req.generate_images)
    script = BASE_DIR / "scripts" / "entertainment_storyboard_agent.py"
    if not script.exists():
        raise HTTPException(500, "entertainment_storyboard_agent.py missing")

    _write_run_state({
        "status": "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "limit": limit,
        "generate_images": generate_images,
    })

    def _run() -> None:
        args = [sys.executable, "-X", "utf8", str(script), "--limit", str(limit)]
        if not generate_images:
            args.append("--no-images")
        try:
            result = subprocess.run(args, cwd=str(BASE_DIR), capture_output=True, text=True, timeout=1800)
            payload = {
                "status": "done" if result.returncode == 0 else "failed",
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "returncode": result.returncode,
                "stdout": result.stdout[-1200:],
                "stderr": result.stderr[-1200:],
            }
            _write_run_state(payload)
        except Exception as exc:
            _write_run_state({
                "status": "failed",
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "error": str(exc),
            })

    threading.Thread(target=_run, daemon=True).start()
    return {"ok": True, "status": "running", "limit": limit, "generate_images": generate_images}


@router.patch("/{candidate_id}/status")
def set_storyboard_status(candidate_id: int, req: StatusUpdate):
    allowed = {"draft", "image_failed", "images_ready", "approved_for_video", "archived", "video_rendering", "video_ready", "video_failed", "scheduled", "published"}
    if req.status not in allowed:
        raise HTTPException(400, f"invalid status: {req.status}")
    item = get_storyboard_candidate(candidate_id)
    if not item:
        raise HTTPException(404, "storyboard candidate not found")
    fields = {"status": req.status}
    if req.status == "approved_for_video":
        fields["approved_at"] = datetime.now(timezone.utc).isoformat()
    update_storyboard_candidate(candidate_id, **fields)
    return {"ok": True, "item": _decorate(get_storyboard_candidate(candidate_id))}


@router.delete("/{candidate_id}")
def delete_storyboard(candidate_id: int):
    if not delete_storyboard_candidate(candidate_id):
        raise HTTPException(404, "storyboard candidate not found")
    return {"ok": True, "deleted_id": candidate_id}


@router.post("/{candidate_id}/regenerate-frames")
def regenerate_storyboard_frames(candidate_id: int):
    item = get_storyboard_candidate(candidate_id)
    if not item:
        raise HTTPException(404, "storyboard candidate not found")
    try:
        from scripts.entertainment_storyboard_agent import generate_candidate_frames

        generate_candidate_frames(candidate_id)
    except Exception as exc:
        update_storyboard_candidate(candidate_id, status="image_failed")
        raise HTTPException(500, f"regenerate frames failed: {exc}") from exc
    return {"ok": True, "item": _decorate(get_storyboard_candidate(candidate_id))}


@router.post("/{candidate_id}/regenerate-sheet")
def regenerate_storyboard_sheet_legacy(candidate_id: int):
    return regenerate_storyboard_frames(candidate_id)


@router.patch("/{candidate_id}/frames/{frame_id}")
def update_storyboard_frame_prompt(candidate_id: int, frame_id: int, req: FrameUpdate):
    item = get_storyboard_candidate(candidate_id)
    if not item:
        raise HTTPException(404, "storyboard candidate not found")
    frame_ids = {int(frame["id"]) for frame in item.get("frames") or []}
    if frame_id not in frame_ids:
        raise HTTPException(404, "storyboard frame not found")
    fields = {
        key: value
        for key, value in req.dict(exclude_none=True).items()
        if key in {"title", "visual_prompt", "seedance_prompt", "sound_prompt", "duration_seconds", "trim_seconds"}
    }
    if fields:
        update_storyboard_frame(frame_id, **fields)
    return {"ok": True, "item": _decorate(get_storyboard_candidate(candidate_id))}


@router.post("/{candidate_id}/frames/{frame_id}/regenerate")
def regenerate_storyboard_frame(candidate_id: int, frame_id: int):
    item = get_storyboard_candidate(candidate_id)
    if not item:
        raise HTTPException(404, "storyboard candidate not found")
    frames = item.get("frames") or []
    frame = next((frame for frame in frames if int(frame["id"]) == frame_id), None)
    if not frame:
        raise HTTPException(404, "storyboard frame not found")
    try:
        from scripts.entertainment_storyboard_agent import (
            candidate_dir,
            generate_single_storyboard_frame,
        )

        out_dir = candidate_dir(candidate_id)
        output = out_dir / f"frame_{int(frame.get('frame_index') or 1):02d}_{frame.get('shot_code') or 'shot'}.jpg"
        source = generate_single_storyboard_frame(item, frame, output)
        update_storyboard_frame(
            frame_id,
            image_path=str(output.relative_to(PIPELINE_DIR)).replace("\\", "/"),
            status=source,
            video_path="",
            video_status="",
        )
    except Exception as exc:
        update_storyboard_frame(frame_id, status="image_failed")
        raise HTTPException(500, f"regenerate frame failed: {exc}") from exc
    return {"ok": True, "item": _decorate(get_storyboard_candidate(candidate_id))}


@router.post("/{candidate_id}/frames/{frame_id}/regenerate-video")
def regenerate_storyboard_frame_video(candidate_id: int, frame_id: int):
    item = get_storyboard_candidate(candidate_id)
    if not item:
        raise HTTPException(404, "storyboard candidate not found")
    frames = item.get("frames") or []
    frame = next((frame for frame in frames if int(frame["id"]) == frame_id), None)
    if not frame:
        raise HTTPException(404, "storyboard frame not found")
    if not frame.get("image_path"):
        raise HTTPException(400, "frame needs image before video rendering")

    update_storyboard_frame(frame_id, video_status="rendering", video_path="")
    update_storyboard_candidate(candidate_id, video_status="segment_rendering")

    def _run() -> None:
        try:
            from scripts.seedance_storyboard_renderer import render_frame_segment

            render_frame_segment(candidate_id, frame_id, force=True)
            current = get_storyboard_candidate(candidate_id)
            if current and current.get("status") == "video_ready":
                update_storyboard_candidate(candidate_id, video_status="ready")
            else:
                update_storyboard_candidate(candidate_id, video_status="segment_ready")
        except Exception as exc:
            update_storyboard_frame(frame_id, video_status=f"failed: {exc}")
            update_storyboard_candidate(candidate_id, video_status=f"segment_failed: {exc}")

    threading.Thread(target=_run, daemon=True).start()
    return {"ok": True, "status": "segment_rendering", "item": _decorate(get_storyboard_candidate(candidate_id))}


@router.post("/{candidate_id}/render-video")
def render_storyboard_video(candidate_id: int):
    item = get_storyboard_candidate(candidate_id)
    if not item:
        raise HTTPException(404, "storyboard candidate not found")
    if not all(frame.get("image_path") for frame in item.get("frames") or []):
        raise HTTPException(400, "all storyboard frames need images before video rendering")

    update_storyboard_candidate(candidate_id, status="video_rendering", video_status="rendering")

    def _run() -> None:
        try:
            from scripts.seedance_storyboard_renderer import render_candidate

            render_candidate(candidate_id)
        except Exception as exc:
            update_storyboard_candidate(candidate_id, status="video_failed", video_status=f"failed: {exc}")

    threading.Thread(target=_run, daemon=True).start()
    return {"ok": True, "status": "video_rendering", "item": _decorate(get_storyboard_candidate(candidate_id))}
