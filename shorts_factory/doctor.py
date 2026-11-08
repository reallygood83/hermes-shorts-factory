"""Detect ffmpeg, ffprobe, a Hangul font, and optional Manim.

Nothing is installed. Hints are commands the operator can run themselves.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    detail: str
    install_hint: str


Which = Callable[[str], str | None]

FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKkr-Regular.otf",
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/Library/Fonts/AppleSDGothicNeo.ttc",
    "C:/Windows/Fonts/malgun.ttf",
    "C:/Windows/Fonts/malgunbd.ttf",
)


def _hint(binary: str) -> str:
    if sys.platform == "darwin":
        return f"brew install {binary}" if binary == "ffmpeg" else "brew install ffmpeg  # provides ffprobe"
    if sys.platform.startswith("win"):
        return "winget install Gyan.FFmpeg"
    return f"sudo apt-get install {binary}" if binary == "ffmpeg" else "sudo apt-get install ffmpeg"


def _manim_hint() -> str:
    common = "Optional. The offline smoke MP4 does not need Manim. Install only if you opt in."
    if sys.platform == "darwin":
        return common + " brew install py3cairo pango pkg-config ffmpeg && pip install manim"
    if sys.platform.startswith("win"):
        return common + " See https://docs.manim.community/en/stable/installation/windows.html"
    return common + " sudo apt-get install ffmpeg libcairo2-dev libpango1.0-dev pkg-config && pip install manim"


def find_font() -> str | None:
    for candidate in FONT_CANDIDATES:
        if Path(candidate).is_file():
            return candidate
    return None


def run_checks(which: Which | None = None) -> list[Check]:
    lookup = which or shutil.which
    checks: list[Check] = []
    for binary in ("ffmpeg", "ffprobe"):
        found = lookup(binary)
        checks.append(
            Check(
                name=binary,
                status="ok" if found else "missing",
                detail=found or "not on PATH",
                install_hint="" if found else _hint(binary),
            )
        )
    font = find_font()
    checks.append(
        Check(
            name="hangul-font",
            status="ok" if font else "missing",
            detail=font or "no known Hangul font",
            install_hint="" if font else "Install Noto Sans CJK or another Hangul font. The doctor does not download fonts.",
        )
    )
    manim = lookup("manim")
    checks.append(
        Check(
            name="manim",
            status="ok" if manim else "optional-missing",
            detail=manim or "not on PATH",
            install_hint="" if manim else _manim_hint(),
        )
    )
    key_set = bool(os.environ.get("XAI_API_KEY"))
    checks.append(
        Check(
            name="xai-tts",
            status="configured" if key_set else "optional-missing",
            detail="XAI_API_KEY is set" if key_set else "XAI_API_KEY is unset; paid narration will fail closed",
            install_hint="Create a key at https://console.x.ai and store it only in the profile .env. SuperGrok OAuth is not sufficient.",
        )
    )
    return checks


def doctor_ok(checks: list[Check]) -> bool:
    required = {"ffmpeg", "ffprobe", "hangul-font"}
    return all(item.status == "ok" for item in checks if item.name in required)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check local shorts-factory dependencies")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    checks = run_checks()
    if args.json:
        print(json.dumps([asdict(item) for item in checks], ensure_ascii=False, indent=2))
    else:
        for item in checks:
            line = f"[{item.status}] {item.name}: {item.detail}"
            if item.install_hint:
                line += f"\n  hint: {item.install_hint}"
            print(line)
    return 0 if doctor_ok(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
