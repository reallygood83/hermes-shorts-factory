"""Optional rea-video breakdown reader.

This does not ship rea-video and does not invent a CLI. If the operator
already has a breakdown.json, pass its path. Otherwise the summary says
the input is unavailable.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def summarize_breakdown(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {
            "available": False,
            "reason": "No breakdown path was configured. rea-video is not bundled.",
        }
    if not path.is_file():
        return {
            "available": False,
            "reason": f"breakdown file not found: {path}",
        }
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"available": False, "reason": f"breakdown.json is not JSON: {exc}"}
    if not isinstance(data, dict):
        return {"available": False, "reason": "breakdown.json must be an object"}
    scenes = data.get("scenes")
    shots = data.get("shots")
    return {
        "available": True,
        "source": str(path),
        "executed_rea_video": False,
        "top_level_keys": sorted(str(key) for key in data.keys()),
        "duration": data.get("duration"),
        "scene_count": len(scenes) if isinstance(scenes, list) else None,
        "shot_count": len(shots) if isinstance(shots, list) else None,
        "structure_notes": data.get("structure_notes") if isinstance(data.get("structure_notes"), str) else None,
    }
