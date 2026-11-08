"""Repair a shorts-factory profile whose Desktop chat returns storage_unavailable.

Hermes Desktop's bot opener (``notifyBotOpenFailure``) shows
``Could not open <name>'s chat`` with the raw RPC detail. On Hermes 0.23.0
``session.create`` stores a policy that ``gateway/session_policy.py``
``restore_policy`` rejects when ``policy.model`` is empty, and that rejection
is reported as ``storage_unavailable``.

This writes only the shorts-factory profile's chat model and, when asked,
its speech settings and .env. It does not delete sessions or read the
default profile's secrets.
"""

from __future__ import annotations

import argparse
import os
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from shorts_factory import PROFILE_NAME
from shorts_factory.tts import GEMINI_TTS_DEFAULT, GEMINI_TTS_MODELS, GEMINI_TTS_VOICE

Prompt = Callable[["OnboardRequest"], "OnboardResult"]


class RepairError(Exception):
    """The profile cannot be changed safely."""


@dataclass(frozen=True)
class OnboardRequest:
    chat_provider: str
    chat_model: str
    tts_provider: str
    tts_model: str
    tts_voice: str
    has_gemini_key: bool
    has_xai_key: bool
    config_path: Path
    env_path: Path
    default_provider: str = ""
    default_model: str = ""


@dataclass(frozen=True)
class OnboardResult:
    cancelled: bool
    chat_provider: str = ""
    chat_model: str = ""
    tts_provider: str = ""
    tts_model: str = ""
    tts_voice: str = ""
    gemini_api_key: str | None = None
    xai_api_key: str | None = None
    open_config: bool = False
    local_tone: bool = True


def profile_dir(hermes_home: Path) -> Path:
    return hermes_home / "profiles" / PROFILE_NAME


def _unquote(value: str) -> str:
    return value.strip().strip('"').strip("'")


def read_model_fields(config_text: str) -> tuple[str, str]:
    """Return (provider, model) from a Hermes config. Never returns api_key values."""

    provider = ""
    model = ""
    scalar = ""
    in_model = False
    for line in config_text.splitlines():
        if line.startswith("model:"):
            in_model = True
            scalar = _unquote(line.split(":", 1)[1])
            continue
        if not in_model:
            continue
        if not line.startswith((" ", "\t")):
            break
        stripped = line.strip()
        key, _, raw = stripped.partition(":")
        if key in {"api_key", "token", "secret", "base_url"}:
            continue
        if key == "provider":
            provider = _unquote(raw)
        elif key in {"default", "model"}:
            model = _unquote(raw)
    return provider, model or scalar


def _read_model(config_text: str) -> str:
    return read_model_fields(config_text)[1]


def default_profile_model(hermes_home: Path) -> tuple[str, str]:
    """Model name from the default profile config only. Does not read .env or auth.json."""

    path = hermes_home / "config.yaml"
    if not path.is_file():
        return "", ""
    provider, model = read_model_fields(path.read_text(encoding="utf-8"))
    if not model or model in GEMINI_TTS_MODELS or model.endswith("-tts"):
        return "", ""
    return provider, model


def validate_chat_model(model: str) -> str:
    cleaned = model.strip()
    if not cleaned:
        raise RepairError(
            "채팅 모델이 비어 있습니다. Desktop은 세션 정책의 model이 비면 "
            "storage_unavailable로 'Could not open Shorts Factory’s chat'를 냅니다. "
            "기본 Hermes 모델을 고르거나, 온보딩 질문에서 대화 모델 이름을 입력하세요. "
            "음성 모델은 채팅 모델이 아닙니다."
        )
    if cleaned in GEMINI_TTS_MODELS or cleaned.endswith("-tts"):
        raise RepairError(
            f"{cleaned}는 음성 모델입니다. 채팅 모델은 기본 Hermes 모델이거나, "
            "온보딩에서 입력한 대화 모델이어야 합니다. TTS 키와 채팅 모델은 따로 저장합니다."
        )
    return cleaned


def diagnose(hermes_home: Path) -> dict[str, object]:
    profile = profile_dir(hermes_home)
    config = profile / "config.yaml"
    found = config.is_file()
    model = _read_model(config.read_text(encoding="utf-8")) if found else ""
    causes: list[dict[str, str]] = []
    if not found:
        causes.append(
            {
                "code": "profile_missing",
                "detail": "shorts-factory profile config.yaml is missing",
            }
        )
    elif not model:
        causes.append(
            {
                "code": "empty_chat_model",
                "detail": "storage_unavailable",
                "action": (
                    "Hermes 0.23.0 gateway/session_policy.py restore_policy rejects an empty "
                    "policy.model and the Desktop bot opener shows that as "
                    "Could not open Shorts Factory’s chat. Save a chat model with "
                    "python3 scripts/repair_chat.py. This does not delete state.db."
                ),
            }
        )
    elif model in GEMINI_TTS_MODELS:
        causes.append(
            {
                "code": "tts_model_used_as_chat",
                "detail": model,
                "action": "Choose the default Hermes chat model, or type a chat model in onboarding.",
            }
        )
    return {
        "profile": str(profile),
        "chat_model": model,
        "ok": not causes,
        "causes": causes,
        "desktop_verified": False,
    }


def _replace_block(text: str, name: str, block: str) -> str:
    lines = text.splitlines()
    start = next((index for index, line in enumerate(lines) if line.startswith(f"{name}:")), None)
    new_lines = block.strip("\n").splitlines()
    if start is None:
        base = text if text.endswith("\n") or not text else text + "\n"
        return base + "\n" + block.strip() + "\n"
    end = start + 1
    while end < len(lines) and (lines[end].startswith((" ", "\t")) or lines[end].strip() == ""):
        end += 1
    updated = lines[:start] + new_lines + lines[end:]
    return "\n".join(updated).rstrip() + "\n"


def _tts_block(provider: str, model: str, voice: str) -> str:
    if provider == "xai":
        return (
            "tts:\n"
            "  provider: xai\n"
            "  xai:\n"
            "    voice_id: " + voice + "\n"
            "    language: ko\n"
            "    speed: 1.0\n"
            "    auto_speech_tags: false\n"
            "    text_normalization: true\n"
            "    optimize_streaming_latency: 0\n"
            "    sample_rate: 24000\n"
            "    bit_rate: 128000\n"
        )
    if provider == "gemini":
        if model not in GEMINI_TTS_MODELS:
            raise RepairError(f"unsupported Gemini speech model: {model}")
        return (
            "tts:\n"
            "  provider: gemini\n"
            "  gemini:\n"
            "    model: " + model + "\n"
            "    voice: " + voice + "\n"
            "    audio_tags: false\n"
        )
    raise RepairError(
        "Gemini에는 효과음 API가 없습니다. 내레이션은 xai 또는 gemini이고, "
        "효과음과 BGM은 local-tone만 사용합니다."
    )


def write_chat_and_speech(config_path: Path, result: OnboardResult) -> None:
    model = validate_chat_model(result.chat_model)
    provider = result.chat_provider.strip()
    current = config_path.read_text(encoding="utf-8") if config_path.is_file() else ""
    if provider:
        model_block = f"model:\n  provider: {provider}\n  default: {model}\n"
    else:
        model_block = f"model: {model}\n"
    updated = _replace_block(current, "model", model_block)
    if result.tts_provider in {"xai", "gemini"}:
        voice = result.tts_voice or (GEMINI_TTS_VOICE if result.tts_provider == "gemini" else "eve")
        speech_model = result.tts_model or (GEMINI_TTS_DEFAULT if result.tts_provider == "gemini" else "grok-tts")
        updated = _replace_block(updated, "tts", _tts_block(result.tts_provider, speech_model, voice))
    temporary = config_path.with_name(config_path.name + ".tmp")
    temporary.write_text(updated, encoding="utf-8")
    os.replace(temporary, config_path)


def upsert_env(path: Path, updates: dict[str, str]) -> None:
    existing: dict[str, str] = {}
    order: list[str] = []
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key not in existing:
                order.append(key)
            existing[key] = value
    for key, value in updates.items():
        existing[key] = value
        if key not in order:
            order.append(key)
    body = "".join(f"{key}={existing[key]}\n" for key in order)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(body, encoding="utf-8")
    os.chmod(temporary, stat.S_IRUSR | stat.S_IWUSR)
    os.replace(temporary, path)
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)


def _env_has(path: Path, key: str) -> bool:
    if not path.is_file():
        return False
    prefix = key + "="
    return any(line.startswith(prefix) and line.split("=", 1)[1].strip() for line in path.read_text(encoding="utf-8").splitlines())


def open_config_file(path: Path) -> str:
    if sys.platform == "darwin":
        command = ["open", str(path)]
    else:
        command = ["xdg-open", str(path)]
    try:
        subprocess.run(command, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        return f"open this file locally: {path}"
    return f"opened {path.name}"


def apply_result(hermes_home: Path, result: OnboardResult, opener: Callable[[Path], str] | None = None) -> dict[str, object]:
    if result.cancelled:
        return {"wrote": False, "cancelled": True}
    profile = profile_dir(hermes_home)
    if not profile.is_dir():
        raise RepairError(f"missing profile directory: {profile}")
    config_path = profile / "config.yaml"
    env_path = profile / ".env"
    write_chat_and_speech(config_path, result)
    secret_updates = {}
    if result.gemini_api_key:
        secret_updates["GEMINI_API_KEY"] = result.gemini_api_key
    if result.xai_api_key:
        secret_updates["XAI_API_KEY"] = result.xai_api_key
    if secret_updates:
        upsert_env(env_path, secret_updates)
    opened = ""
    if result.open_config:
        opened = (opener or open_config_file)(config_path)
    return {
        "wrote": True,
        "cancelled": False,
        "chat_model": validate_chat_model(result.chat_model),
        "config": str(config_path),
        "opened": opened,
    }


def default_request(hermes_home: Path) -> OnboardRequest:
    profile = profile_dir(hermes_home)
    config = profile / "config.yaml"
    current_provider, current_model = ("", "")
    if config.is_file():
        current_provider, current_model = read_model_fields(config.read_text(encoding="utf-8"))
    default_provider, default_model = default_profile_model(hermes_home)
    env_path = profile / ".env"
    return OnboardRequest(
        chat_provider=current_provider,
        chat_model=current_model,
        tts_provider="",
        tts_model="",
        tts_voice="",
        has_gemini_key=_env_has(env_path, "GEMINI_API_KEY"),
        has_xai_key=_env_has(env_path, "XAI_API_KEY"),
        config_path=config,
        env_path=env_path,
        default_provider=default_provider,
        default_model=default_model,
    )


def choice_from_default(hermes_home: Path) -> OnboardResult:
    provider, model = default_profile_model(hermes_home)
    if not model:
        raise RepairError(
            "기본 Hermes config.yaml에 대화 모델이 없습니다. "
            "python3 scripts/repair_chat.py 로 온보딩 질문에서 모델을 입력하세요. "
            "키는 명령줄에 넣지 않습니다."
        )
    return OnboardResult(
        cancelled=False,
        chat_provider=provider,
        chat_model=model,
        tts_provider="",
    )


def run_repair(
    hermes_home: Path,
    prompt: Prompt | None = None,
    preset: OnboardResult | None = None,
    opener: Callable[[Path], str] | None = None,
) -> dict[str, object]:
    report = diagnose(hermes_home)
    if preset is not None:
        outcome = apply_result(hermes_home, preset, opener)
    else:
        if prompt is None:
            raise RepairError("a prompt is required unless a preset result is given")
        outcome = apply_result(hermes_home, prompt(default_request(hermes_home)), opener)
    outcome["diagnosis"] = report
    return outcome


def _noninteractive_result(args: argparse.Namespace) -> OnboardResult:
    return OnboardResult(
        cancelled=False,
        chat_provider=args.chat_provider,
        chat_model=args.chat_model,
        tts_provider=args.tts_provider or "",
        tts_model=args.tts_model or "",
        tts_voice=args.tts_voice or "",
        gemini_api_key=None,
        xai_api_key=None,
        open_config=args.open_config,
        local_tone=True,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Repair shorts-factory Desktop chat and optional speech keys")
    parser.add_argument("--hermes-home", type=Path, default=None)
    parser.add_argument("--diagnose", action="store_true")
    parser.add_argument("--noninteractive", action="store_true")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--use-default-model", action="store_true")
    parser.add_argument("--chat-provider", default="")
    parser.add_argument("--chat-model", default="")
    parser.add_argument("--tts-provider", default="")
    parser.add_argument("--tts-model", default="")
    parser.add_argument("--tts-voice", default="")
    parser.add_argument("--open-config", action="store_true")
    args = parser.parse_args(argv)
    home = (args.hermes_home or Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes")))).expanduser()
    if args.diagnose:
        print(_public_diagnosis(diagnose(home)))
        return 0
    try:
        if args.noninteractive or args.use_default_model:
            if args.use_default_model and args.chat_model:
                raise RepairError("모델은 기본 Hermes 모델과 직접 입력 중 하나만 고르세요.")
            if args.use_default_model:
                outcome = run_repair(home, preset=choice_from_default(home))
            elif args.chat_model:
                outcome = run_repair(home, preset=_noninteractive_result(args))
            else:
                raise RepairError(
                    "채팅 모델을 고르지 않았습니다. 화면에서 python3 scripts/repair_chat.py 를 실행하거나, "
                    "--use-default-model 또는 --chat-model 중 하나를 지정하세요. API 키는 명령줄에 넣지 않습니다."
                )
        else:
            from shorts_factory.onboard_ui import prompt_for_environment

            outcome = run_repair(home, prompt=prompt_for_environment(force_headless=args.headless))
    except RepairError as exc:
        print(f"repair blocked: {exc}")
        return 2
    if outcome.get("cancelled"):
        print("cancelled; no files written")
        return 0
    print(f"saved chat model {outcome.get('chat_model')} in the shorts-factory profile")
    print("Desktop itself was not opened here. On your computer, reopen Shorts Factory after this repair.")
    if outcome.get("opened"):
        print(str(outcome["opened"]))
    return 0


def _public_diagnosis(report: dict[str, object]) -> str:
    lines = [f"profile: {report['profile']}", f"chat_model: {report['chat_model'] or '(empty)'}"]
    causes = report["causes"]
    if isinstance(causes, list):
        for cause in causes:
            if isinstance(cause, dict):
                lines.append(f"{cause.get('code')}: {cause.get('detail')}")
                if cause.get("action"):
                    lines.append(str(cause["action"]))
    if report.get("ok"):
        lines.append("chat model is set. If Desktop still says storage_unavailable, run hermes gateway ensure in this HERMES_HOME and retry. This command does not delete chats.")
    lines.append("desktop_verified: false")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
