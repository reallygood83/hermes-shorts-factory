"""Speech adapters.

Selected provider: xAI Grok TTS (`grok-tts`, POST https://api.x.ai/v1/tts).
OpenAI speech is an explicit alternate, never a fallback.
Claude, Codex, and ElevenLabs fail closed. The offline adapter writes a
labeled tone and is only used when the project selects it.
"""

from __future__ import annotations

import json
import math
import os
import struct
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError

from shorts_factory.approvals import ApprovalError, ApprovalStore, SpeechSelection

XAI_TTS_URL = "https://api.x.ai/v1/tts"
XAI_PRODUCT = "grok-tts"
XAI_LANGUAGES = frozenset(
    {
        "auto",
        "en",
        "ar-EG",
        "ar-SA",
        "ar-AE",
        "bn",
        "zh",
        "fr",
        "de",
        "hi",
        "id",
        "it",
        "ja",
        "ko",
        "pt-BR",
        "pt-PT",
        "ru",
        "es-MX",
        "es-ES",
        "tr",
        "vi",
    }
)
OPENAI_SPEECH_URL = "https://api.openai.com/v1/audio/speech"
OPENAI_MODELS = frozenset({"gpt-4o-mini-tts", "gpt-4o-mini-tts-2025-12-15"})
OPENAI_DEFAULT_MODEL = "gpt-4o-mini-tts"
PAID_FLAG = "SHORTS_FACTORY_ALLOW_PAID_TTS"
DEFAULT_XAI_VOICE = "eve"
# Speech models. gemini-3.8-flash-tts lists Korean in Google's TTS language table.
# gemini-2.5-flash-preview-tts is Hermes 0.23's built-in default. Chat models are not in this set.
GEMINI_TTS_DEFAULT = "gemini-3.8-flash-tts"
GEMINI_TTS_VOICE = "Kore"
GEMINI_TTS_MODELS = frozenset(
    {
        "gemini-3.8-flash-tts",
        "gemini-3.8-flash-lite-tts",
        "gemini-2.5-flash-preview-tts",
        "gemini-3.1-flash-tts-preview",
    }
)
GEMINI_TTS_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
# Hermes provider gemini catalog index 0. A chat model, not a TTS model.
GEMINI_CHAT_MODEL = "gemini-3.8-flash"


class SpeechError(Exception):
    """The speech request cannot proceed."""


class Transport(Protocol):
    def post(self, url: str, headers: dict[str, str], body: dict[str, Any]) -> bytes:
        """Send one JSON request and return the response body."""


@dataclass(frozen=True)
class SpeechResult:
    path: Path
    provider: str
    model: str
    voice_id: str
    metered: bool
    placeholder: bool


def resolve_selection(project_tts: dict[str, Any], env: dict[str, str] | None = None) -> SpeechSelection:
    """Project values win. Env fills only blanks so a set voice is not replaced."""

    source = env if env is not None else os.environ
    provider = str(project_tts.get("provider") or "xai")
    if provider == "xai":
        model = str(project_tts.get("model") or XAI_PRODUCT)
        voice = str(project_tts.get("voice_id") or source.get("SHORTS_FACTORY_XAI_VOICE_ID") or DEFAULT_XAI_VOICE)
        language = str(project_tts.get("language") or "ko")
    elif provider == "openai":
        model = str(project_tts.get("model") or OPENAI_DEFAULT_MODEL)
        voice = str(project_tts.get("voice_id") or source.get("SHORTS_FACTORY_OPENAI_VOICE") or "alloy")
        language = str(project_tts.get("language") or "ko")
    elif provider == "gemini":
        model = str(project_tts.get("model") or GEMINI_TTS_DEFAULT)
        voice = str(
            project_tts.get("voice_id")
            or source.get("SHORTS_FACTORY_GEMINI_VOICE")
            or GEMINI_TTS_VOICE
        )
        language = str(project_tts.get("language") or "ko")
    elif provider == "offline":
        model = str(project_tts.get("model") or "offline-placeholder")
        voice = str(project_tts.get("voice_id") or "offline-tone")
        language = str(project_tts.get("language") or "ko")
    elif provider in {"anthropic", "claude", "codex", "elevenlabs"}:
        model = str(project_tts.get("model") or "")
        voice = str(project_tts.get("voice_id") or "")
        language = str(project_tts.get("language") or "")
    else:
        raise SpeechError(f"unknown speech provider: {provider}")
    return SpeechSelection(provider=provider, model=model, voice_id=voice, language=language)


def _require_script(store: ApprovalStore, script_text: str, selection: SpeechSelection) -> None:
    try:
        store.assert_script(script_text, selection)
    except ApprovalError as exc:
        raise SpeechError(str(exc)) from exc


def _require_paid(store: ApprovalStore, selection: SpeechSelection) -> None:
    try:
        store.assert_paid(selection)
    except ApprovalError as exc:
        raise SpeechError(str(exc)) from exc


def _paid_network_allowed() -> bool:
    return os.environ.get(PAID_FLAG) == "1"


class UrlLibTransport:
    """Real HTTP transport. Tests inject a fake transport instead."""

    def post(self, url: str, headers: dict[str, str], body: dict[str, Any]) -> bytes:
        payload = json.dumps(body).encode("utf-8")
        req = urlrequest.Request(url, data=payload, headers=headers, method="POST")
        try:
            with urlrequest.urlopen(req, timeout=60) as response:
                return response.read()
        except HTTPError as exc:
            detail = exc.read(400).decode("utf-8", errors="replace")
            raise SpeechError(f"speech HTTP {exc.code} from {url}: {detail}") from exc
        except URLError as exc:
            raise SpeechError(f"speech request failed before a body was read: {exc.reason}") from exc


def redacted_call(url: str, headers: dict[str, str], body: dict[str, Any]) -> dict[str, Any]:
    hidden = dict(headers)
    for name in list(hidden):
        if name.lower() == "authorization":
            hidden[name] = "Bearer [redacted]"
        elif name.lower() == "x-goog-api-key":
            hidden[name] = "[redacted]"
    return {"url": url, "headers": hidden, "body": body}


class XaiAdapter:
    name = "xai"
    metered = True
    product = XAI_PRODUCT

    def __init__(self, transport: Transport | None = None) -> None:
        self.transport = transport

    def build_body(self, text: str, selection: SpeechSelection) -> dict[str, Any]:
        if selection.provider != self.name:
            raise SpeechError("refusing to reroute a non-xAI selection to xAI")
        if selection.model != XAI_PRODUCT:
            raise SpeechError(
                f"xAI narration is pinned to {XAI_PRODUCT}; refusing model {selection.model!r}"
            )
        language = selection.language
        if language not in XAI_LANGUAGES:
            raise SpeechError(
                f"language {language!r} is not in the documented xAI TTS language list"
            )
        if not selection.voice_id:
            raise SpeechError("xAI voice_id is empty")
        return {
            "text": text,
            "voice_id": selection.voice_id,
            "language": language,
            "output_format": {"codec": "mp3", "sample_rate": 24000, "bit_rate": 128000},
            "text_normalization": True,
        }

    def synthesize(
        self,
        text: str,
        selection: SpeechSelection,
        store: ApprovalStore,
        script_text: str,
        dest: Path,
    ) -> SpeechResult:
        body = self.build_body(text, selection)
        _require_script(store, script_text, selection)
        _require_paid(store, selection)
        if not _paid_network_allowed():
            raise SpeechError(
                f"paid xAI TTS is blocked. Set {PAID_FLAG}=1 only after you intend to spend."
            )
        api_key = os.environ.get("XAI_API_KEY", "")
        if not api_key:
            raise SpeechError(
                "XAI_API_KEY is missing. SuperGrok OAuth is not read and is not accepted for this call. "
                "Create an xAI API key and put it in the profile .env. Chat login is a separate product."
            )
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        transport = self.transport if self.transport is not None else UrlLibTransport()
        audio = transport.post(XAI_TTS_URL, headers, body)
        if not audio:
            raise SpeechError("xAI TTS returned an empty body")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(audio)
        return SpeechResult(dest, self.name, XAI_PRODUCT, selection.voice_id, True, False)


class OpenAIAdapter:
    """Explicit alternate. Never selected because xAI failed."""

    name = "openai"
    metered = True

    def __init__(self, transport: Transport | None = None) -> None:
        self.transport = transport

    def build_body(self, text: str, selection: SpeechSelection) -> dict[str, Any]:
        if selection.provider != self.name:
            raise SpeechError("refusing to reroute a non-OpenAI selection to OpenAI speech")
        if selection.model not in OPENAI_MODELS:
            raise SpeechError(
                f"OpenAI speech model must be one of {sorted(OPENAI_MODELS)}; "
                f"refusing {selection.model!r}. tts-1 and tts-1-hd are not used."
            )
        if not selection.voice_id:
            raise SpeechError("OpenAI voice is empty")
        return {
            "model": selection.model,
            "voice": selection.voice_id,
            "input": text,
            "response_format": "mp3",
        }

    def synthesize(
        self,
        text: str,
        selection: SpeechSelection,
        store: ApprovalStore,
        script_text: str,
        dest: Path,
    ) -> SpeechResult:
        body = self.build_body(text, selection)
        _require_script(store, script_text, selection)
        _require_paid(store, selection)
        if not _paid_network_allowed():
            raise SpeechError(
                f"paid OpenAI speech is blocked. Set {PAID_FLAG}=1 only after you intend to spend."
            )
        api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("VOICE_TOOLS_OPENAI_KEY") or ""
        if not api_key:
            raise SpeechError(
                "OPENAI_API_KEY or VOICE_TOOLS_OPENAI_KEY is missing. "
                "Codex and ChatGPT OAuth are not read and do not authorize POST /v1/audio/speech."
            )
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        transport = self.transport if self.transport is not None else UrlLibTransport()
        audio = transport.post(OPENAI_SPEECH_URL, headers, body)
        if not audio:
            raise SpeechError("OpenAI speech returned an empty body")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(audio)
        return SpeechResult(dest, self.name, selection.model, selection.voice_id, True, False)


class OfflineAdapter:
    """Local tone. Not a substitute the pipeline may choose on its own."""

    name = "offline"
    metered = False

    def synthesize(
        self,
        text: str,
        selection: SpeechSelection,
        store: ApprovalStore,
        script_text: str,
        dest: Path,
    ) -> SpeechResult:
        if selection.provider != self.name or selection.model != "offline-placeholder":
            raise SpeechError("offline audio is available only when the project selects it")
        _require_script(store, script_text, selection)
        dest.parent.mkdir(parents=True, exist_ok=True)
        write_tone(dest, seconds=max(3.0, min(12.0, len(text) / 12)), frequency=440)
        return SpeechResult(dest, self.name, selection.model, selection.voice_id, False, True)


class UnsupportedAdapter:
    def __init__(self, name: str, reason: str) -> None:
        self.name = name
        self.reason = reason
        self.metered = True

    def synthesize(self, *args: Any, **kwargs: Any) -> SpeechResult:
        raise SpeechError(self.reason)


_UNSUPPORTED = {
    "claude": UnsupportedAdapter(
        "claude",
        "Anthropic has no speech endpoint. The Messages API (POST /v1/messages) returns text. "
        "Claude chat OAuth is not a TTS credential. This package will not invent a Claude TTS URL.",
    ),
    "anthropic": UnsupportedAdapter(
        "anthropic",
        "Anthropic has no speech endpoint. The Messages API returns text. Fail closed.",
    ),
    "codex": UnsupportedAdapter(
        "codex",
        "Codex is a coding agent and chat subscription, not a speech API. "
        "It does not authorize POST /v1/audio/speech. Fail closed.",
    ),
    "elevenlabs": UnsupportedAdapter(
        "elevenlabs",
        "ElevenLabs was removed from this package. Choose xAI Grok TTS or, explicitly, OpenAI speech.",
    ),
}


def adapter_for(provider: str, transport: Transport | None = None) -> Any:
    if provider == "xai":
        return XaiAdapter(transport)
    if provider == "gemini":
        # Local import: GeminiAdapter imports speech helpers from this module.
        from shorts_factory.gemini_tts import GeminiAdapter

        return GeminiAdapter(transport)
    if provider == "openai":
        return OpenAIAdapter(transport)
    if provider == "offline":
        if transport is not None:
            raise SpeechError("offline speech does not take a network transport")
        return OfflineAdapter()
    unsupported = _UNSUPPORTED.get(provider)
    if unsupported is not None:
        return unsupported
    raise SpeechError(f"unknown speech provider: {provider}")


def write_tone(path: Path, seconds: float, frequency: float, volume: float = 0.2) -> None:
    rate = 44100
    count = int(rate * seconds)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "w") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        frames = bytearray()
        for index in range(count):
            sample = int(volume * 32767 * math.sin(2 * math.pi * frequency * index / rate))
            frames += struct.pack("<h", sample)
        handle.writeframes(frames)
