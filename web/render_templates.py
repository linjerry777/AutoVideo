"""Shared render template spec loader."""
from __future__ import annotations

import copy
import json
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DEFAULT_SPEC_FILE = BASE_DIR / "web" / "render_template_spec.default.json"
LOCAL_SPEC_FILE = BASE_DIR / "data" / "render_template_spec.json"

DEFAULT_SPEC = {
    "canvas": {"width": 1080, "height": 1920},
    "safe_zone": {"top": 140, "bottom": 220, "left": 54, "right": 54},
    "news": {"opening_label": "先看這個重點", "subtitle_bottom": 340, "visual_change_seconds": 1.8},
    "figure": {
        "top_safe_shift": 90,
        "video_y": 340,
        "video_h": 1010,
        "title_y1": 190,
        "title_y2": 250,
        "top_logo_y": 190,
        "analysis_header_h": 325,
        "analysis_title_y": 170,
        "analysis_underline_y": 252,
        "analysis_logo_y": 170,
        "outro_logo_size": 300,
        "outro_logo_y": 315,
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    result = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_render_template_spec(path: Path | None = None) -> dict:
    spec = copy.deepcopy(DEFAULT_SPEC)
    for candidate in [DEFAULT_SPEC_FILE, path, LOCAL_SPEC_FILE]:
        if not candidate:
            continue
        try:
            if Path(candidate).exists():
                spec = _deep_merge(spec, json.loads(Path(candidate).read_text(encoding="utf-8")))
        except Exception:
            continue
    return spec
