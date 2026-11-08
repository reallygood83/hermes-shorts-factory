"""Project state machine for one short.

Creative decisions stay with the Hermes director. This module stores the
project, checks safety flags, and calls the speech and ffmpeg helpers.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

from shorts_factory.approvals import ApprovalError, ApprovalStore, SpeechSelection
from shorts_factory.rea_video import summarize_breakdown
from shorts_factory.render_offline import RenderError, render_mp4, validate_mp4
from shorts_factory.tts import SpeechError, adapter_for, resolve_selection, write_tone

ASPECTS = {
    "9:16": (1080, 1920),
    "16:9": (1920, 1080),
}


class ProjectError(Exception):
    """The project cannot take this step."""


def _load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ProjectError("project.json must be an object")
    return data


def load_project(directory: Path) -> dict[str, Any]:
    path = directory / "project.json"
    if not path.is_file():
        raise ProjectError(f"missing {path}")
    project = _load(path)
    aspect = str(project.get("aspect") or "9:16")
    if aspect not in ASPECTS:
        raise ProjectError("aspect must be 9:16 or 16:9")
    width, height = ASPECTS[aspect]
    project["width"] = int(project.get("width") or width)
    project["height"] = int(project.get("height") or height)
    if (project["width"], project["height"]) != (width, height):
        raise ProjectError(f"{aspect} requires {width}x{height}")
    _assert_safe(project)
    return project


def _assert_safe(project: dict[str, Any]) -> None:
    if project.get("real_person_likeness") is True:
        raise ProjectError("real-person likeness is refused, including invented speech in their voice")
    if project.get("narration_subject") != "original_fictional":
        raise ProjectError("narration_subject must be original_fictional")
    if project.get("media_reuse") != "structure_only":
        raise ProjectError("media_reuse must be structure_only")
    if project.get("audience") not in (None, "general"):
        raise ProjectError("audience must be general")


def selection_for(project: dict[str, Any]) -> SpeechSelection:
    raw = project.get("tts")
    if not isinstance(raw, dict):
        raise ProjectError("project tts object is missing")
    return resolve_selection(raw)


def script_text(directory: Path) -> str:
    path = directory / "script.md"
    if not path.is_file():
        raise ProjectError("script.md is missing")
    return path.read_text(encoding="utf-8")


def parse_script(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current = ""
    for line in text.splitlines():
        if line.startswith("# "):
            current = line[2:].strip()
            sections.setdefault(current, [])
            continue
        if current:
            sections[current].append(line)
    hook = "\n".join(sections.get("훅", [])).strip()
    narration = "\n".join(sections.get("내레이션", [])).strip()
    if not hook or not narration:
        raise ProjectError("script.md needs '# 훅' and '# 내레이션' sections")
    return {"hook": hook, "narration": narration}


def store_for(directory: Path) -> ApprovalStore:
    return ApprovalStore(directory / ".shorts" / "approvals.json")


def init_project(directory: Path, topic: str, aspect: str = "9:16") -> None:
    if aspect not in ASPECTS:
        raise ProjectError("aspect must be 9:16 or 16:9")
    if directory.exists() and any(directory.iterdir()):
        raise ProjectError(f"{directory} is not empty")
    width, height = ASPECTS[aspect]
    directory.mkdir(parents=True)
    project = {
        "topic": topic,
        "reference_url": None,
        "aspect": aspect,
        "width": width,
        "height": height,
        "duration_seconds": 8,
        "hook_seconds": 3,
        "language": "ko",
        "audience": "general",
        "tts": {
            "provider": "xai",
            "model": "grok-tts",
            "voice_id": "eve",
            "language": "ko",
        },
        "narration_subject": "original_fictional",
        "real_person_likeness": False,
        "media_reuse": "structure_only",
        "rea_video_breakdown": None,
    }
    (directory / "project.json").write_text(
        json.dumps(project, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (directory / "script.md").write_text(
        f"# 훅\n{topic} — 이 3초를 에이전트가 다시 써야 한다.\n\n"
        f"# 내레이션\n{topic}에 대한 자리표시자다. 승인 전에 실제 대본으로 바꾼다.\n\n"
        "# 샷\n1. 0-3초: 직접 만든 큰 자막.\n2. 3초 이후: 직접 찍거나 만든 장면만.\n",
        encoding="utf-8",
    )


def write_analysis(directory: Path, project: dict[str, Any]) -> dict[str, Any]:
    breakdown_path = project.get("rea_video_breakdown")
    breakdown = summarize_breakdown(
        (directory / str(breakdown_path)).resolve() if breakdown_path else None
    )
    reference = project.get("reference_url")
    analysis = {
        "topic": project.get("topic"),
        "reference_url": reference,
        "reference_policy": "structure_only",
        "copied_media": False,
        "rea_video": breakdown,
        "notes": [
            "참고 주소가 있으면 컷 리듬과 훅 위치만 적는다.",
            "원본 화면, 음악, 대사는 복사하지 않는다.",
        ],
    }
    destination = directory / "analysis.json"
    destination.write_text(json.dumps(analysis, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return analysis


def narrate(directory: Path) -> dict[str, Any]:
    project = load_project(directory)
    text = script_text(directory)
    parts = parse_script(text)
    selection = selection_for(project)
    spoken = parts["hook"] + "\n" + parts["narration"]
    output = directory / "output"
    output.mkdir(parents=True, exist_ok=True)
    wav_path = output / "narration.wav"
    adapter = adapter_for(selection.provider)
    if selection.provider == "offline":
        result = adapter.synthesize(spoken, selection, store_for(directory), text, wav_path)
        kind = "offline-placeholder-tone"
    elif selection.provider in {"xai", "openai"}:
        mp3 = output / "narration.mp3"
        result = adapter.synthesize(spoken, selection, store_for(directory), text, mp3)
        kind = "provider-audio"
        wav_path = mp3
    else:
        result = adapter.synthesize(spoken, selection, store_for(directory), text, wav_path)
        kind = "blocked"
    report = {
        "kind": kind,
        "placeholder": result.placeholder,
        "provider": result.provider,
        "model": result.model,
        "voice_id": result.voice_id,
        "metered": result.metered,
        "path": str(result.path),
        "posted": False,
    }
    (output / "narration.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def render(directory: Path) -> dict[str, Any]:
    project = load_project(directory)
    text = script_text(directory)
    parts = parse_script(text)
    selection = selection_for(project)
    store_for(directory).assert_script(text, selection)
    output = directory / "output"
    output.mkdir(parents=True, exist_ok=True)
    if selection.provider == "offline":
        narration = output / "narration.wav"
        write_tone(narration, seconds=float(project["duration_seconds"]), frequency=440, volume=0.15)
        mix_note = "offline placeholder tone mixed into the mp4; this is not Grok speech"
        (output / "narration.json").write_text(
            json.dumps(
                {
                    "kind": "offline-placeholder-tone",
                    "placeholder": True,
                    "provider": "offline",
                    "model": selection.model,
                    "voice_id": selection.voice_id,
                    "metered": False,
                    "posted": False,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    elif selection.provider in {"xai", "openai"}:
        store_for(directory).assert_paid(selection)
        narration = output / "narration.mp3"
        if not narration.is_file():
            raise ProjectError("paid narration file is missing; run narrate after both approvals")
        mix_note = "approved provider audio mixed into the mp4"
    else:
        raise ProjectError(f"cannot render provider {selection.provider}")

    destination = output / "final.mp4"
    mix_input = narration
    try:
        rendered = render_mp4(
            hook=parts["hook"],
            body=parts["narration"],
            narration_wav=mix_input,
            destination=destination,
            width=int(project["width"]),
            height=int(project["height"]),
            hook_seconds=float(project["hook_seconds"]),
            duration=float(project["duration_seconds"]),
        )
    except RenderError as exc:
        raise ProjectError(str(exc)) from exc
    rendered["mix_note"] = mix_note
    rendered["speech_selection"] = selection.as_dict()
    (output / "render-report.json").write_text(
        json.dumps(rendered, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return rendered


def validate(directory: Path) -> dict[str, Any]:
    project = load_project(directory)
    path = directory / "output" / "final.mp4"
    if not path.is_file():
        raise ProjectError("final.mp4 is missing")
    try:
        report = validate_mp4(
            path,
            int(project["width"]),
            int(project["height"]),
            float(project["duration_seconds"]),
        )
    except RenderError as exc:
        raise ProjectError(str(exc)) from exc
    (directory / "output" / "validation.json").write_text(
        json.dumps({"ok": report["ok"], "problems": report["problems"]}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if not report["ok"]:
        raise ProjectError("validation failed: " + "; ".join(report["problems"]))
    return report


def publish_bundle(directory: Path) -> dict[str, Any]:
    project = load_project(directory)
    store_for(directory).assert_publish()
    validation_path = directory / "output" / "validation.json"
    if not validation_path.is_file():
        raise ProjectError("validation.json is missing")
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    if not validation.get("ok"):
        raise ProjectError("publish blocked because validation did not pass")
    final = directory / "output" / "final.mp4"
    if not final.is_file():
        raise ProjectError("final.mp4 is missing")
    bundle = {
        "uploaded": False,
        "posted": False,
        "remote_generation": False,
        "target": "manual-local-bundle",
        "local_mp4": str(final.resolve()),
        "topic": project.get("topic"),
        "note": "승인되어도 이 명령은 업로드하지 않는다. 파일을 사람이 직접 올린다.",
    }
    destination = directory / "output" / "publish-bundle.json"
    destination.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return bundle


def copy_smoke(destination: Path, source: Path) -> None:
    if destination.exists():
        raise ProjectError(f"{destination} already exists")
    shutil.copytree(source, destination)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="shorts-factory local project commands")
    sub = parser.add_subparsers(dest="command", required=True)

    init_cmd = sub.add_parser("init")
    init_cmd.add_argument("directory", type=Path)
    init_cmd.add_argument("--topic", required=True)
    init_cmd.add_argument("--aspect", default="9:16", choices=tuple(ASPECTS))

    for name in ("analyze", "narrate", "render", "validate", "publish", "status"):
        cmd = sub.add_parser(name)
        cmd.add_argument("directory", type=Path)

    approve_script = sub.add_parser("approve-script")
    approve_script.add_argument("directory", type=Path)
    approve_paid = sub.add_parser("approve-paid")
    approve_paid.add_argument("directory", type=Path)
    approve_publish = sub.add_parser("approve-publish")
    approve_publish.add_argument("directory", type=Path)

    args = parser.parse_args(argv)
    directory = args.directory.resolve()
    try:
        if args.command == "init":
            init_project(directory, args.topic, args.aspect)
            print(f"initialized {directory}")
            return 0
        if args.command == "status":
            project = load_project(directory)
            print(json.dumps({"project": project, "approvals": store_for(directory).load()}, ensure_ascii=False, indent=2))
            return 0
        if args.command == "analyze":
            print(json.dumps(write_analysis(directory, load_project(directory)), ensure_ascii=False, indent=2))
            return 0
        if args.command == "approve-script":
            project = load_project(directory)
            text = script_text(directory)
            parse_script(text)
            record = store_for(directory).approve_script(text, selection_for(project))
            print(json.dumps(record, ensure_ascii=False, indent=2))
            return 0
        if args.command == "approve-paid":
            project = load_project(directory)
            record = store_for(directory).approve_paid(selection_for(project))
            print(json.dumps(record, ensure_ascii=False, indent=2))
            return 0
        if args.command == "approve-publish":
            record = store_for(directory).approve_publish()
            print(json.dumps(record, ensure_ascii=False, indent=2))
            return 0
        if args.command == "narrate":
            print(json.dumps(narrate(directory), ensure_ascii=False, indent=2))
            return 0
        if args.command == "render":
            print(json.dumps(render(directory), ensure_ascii=False, indent=2))
            return 0
        if args.command == "validate":
            report = validate(directory)
            print(json.dumps({"ok": report["ok"], "problems": report["problems"]}, ensure_ascii=False, indent=2))
            return 0
        if args.command == "publish":
            print(json.dumps(publish_bundle(directory), ensure_ascii=False, indent=2))
            return 0
    except (ProjectError, ApprovalError, SpeechError) as exc:
        print(f"blocked: {exc}")
        return 2
    print("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
