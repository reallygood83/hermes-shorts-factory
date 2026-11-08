"""Assemble a local MP4 with ffmpeg.

Captions and an original tone are generated here. No stock footage, no
remote renderer, and no paid speech.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from shorts_factory.doctor import find_font
from shorts_factory.tts import write_tone


class RenderError(Exception):
    """Local assembly cannot finish."""


def _escape_filter_path(path: Path) -> str:
    return str(path).replace("\\", "\\\\").replace(":", "\\:").replace("'", r"\'")


def render_mp4(
    *,
    hook: str,
    body: str,
    narration_wav: Path,
    destination: Path,
    width: int,
    height: int,
    hook_seconds: float,
    duration: float,
    font: str | None = None,
) -> dict[str, Any]:
    if width % 2 or height % 2:
        raise RenderError("width and height must be even")
    if hook_seconds < 3:
        raise RenderError("hook must cover at least 3 seconds")
    if duration <= hook_seconds:
        raise RenderError("duration must be longer than the hook")
    if not narration_wav.is_file():
        raise RenderError(f"narration wav is missing: {narration_wav}")
    font_path = font or find_font()
    if not font_path:
        raise RenderError("no Hangul font found; run the doctor")

    destination.parent.mkdir(parents=True, exist_ok=True)
    work = destination.parent
    hook_file = work / "hook.txt"
    body_file = work / "body.txt"
    bgm = work / "bgm.wav"
    hook_file.write_text(hook.strip() + "\n", encoding="utf-8")
    body_file.write_text(body.strip() + "\n", encoding="utf-8")
    write_tone(bgm, seconds=duration, frequency=196, volume=0.08)

    font_esc = _escape_filter_path(Path(font_path))
    hook_esc = _escape_filter_path(hook_file)
    body_esc = _escape_filter_path(body_file)
    video_filter = (
        f"[0:v]drawtext=fontfile='{font_esc}':textfile='{hook_esc}':fontsize=64:"
        f"fontcolor=white:x=(w-text_w)/2:y=h*0.22:enable='lt(t\\,{hook_seconds})',"
        f"drawtext=fontfile='{font_esc}':textfile='{body_esc}':fontsize=42:"
        f"fontcolor=white:x=(w-text_w)/2:y=h*0.62:enable='gte(t\\,{hook_seconds})'[v]"
    )
    audio_filter = "[1:a]volume=0.9[n];[2:a]volume=0.35[b];[n][b]amix=inputs=2:duration=first[a]"
    command = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c=0x111827:s={width}x{height}:d={duration}:r=30",
        "-i",
        str(narration_wav),
        "-i",
        str(bgm),
        "-filter_complex",
        video_filter + ";" + audio_filter,
        "-map",
        "[v]",
        "-map",
        "[a]",
        "-t",
        str(duration),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-preset",
        "veryfast",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-movflags",
        "+faststart",
        str(destination),
    ]
    completed = subprocess.run(command, check=False, text=True, capture_output=True)
    if completed.returncode != 0:
        tail = (completed.stderr or "")[-1200:]
        raise RenderError(f"ffmpeg failed: {tail}")
    return {
        "path": str(destination),
        "width": width,
        "height": height,
        "duration": duration,
        "hook_seconds": hook_seconds,
        "font": font_path,
        "third_party_media": False,
        "bgm": "generated-sine",
    }


def probe(path: Path) -> dict[str, Any]:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration:stream=codec_type,width,height,codec_name",
        "-of",
        "json",
        str(path),
    ]
    completed = subprocess.run(command, check=False, text=True, capture_output=True)
    if completed.returncode != 0:
        raise RenderError(completed.stderr.strip() or "ffprobe failed")
    return json.loads(completed.stdout)


def validate_mp4(path: Path, width: int, height: int, duration: float) -> dict[str, Any]:
    report = probe(path)
    streams = report.get("streams") or []
    video = next((item for item in streams if item.get("codec_type") == "video"), None)
    audio = next((item for item in streams if item.get("codec_type") == "audio"), None)
    actual = float((report.get("format") or {}).get("duration") or 0)
    problems: list[str] = []
    if video is None:
        problems.append("missing video stream")
    else:
        if int(video.get("width") or 0) != width or int(video.get("height") or 0) != height:
            problems.append(f"resolution {video.get('width')}x{video.get('height')}")
        if video.get("codec_name") != "h264":
            problems.append(f"video codec {video.get('codec_name')}")
    if audio is None:
        problems.append("missing audio stream")
    if abs(actual - duration) > 0.4:
        problems.append(f"duration {actual} != {duration}")
    return {"ok": not problems, "problems": problems, "probe": report}
