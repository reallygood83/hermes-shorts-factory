"""Gemini speech adapter.

The request matches Hermes 0.23 ``_generate_gemini_tts``: ``generateContent``
with ``responseModalities: ["AUDIO"]`` and a prebuilt voice. The API key stays
in the ``x-goog-api-key`` header. This is narration, not sound effects.
"""

from __future__ import annotations

import base64
import io
import json
import os
import wave
from pathlib import Path
from typing import Any

from shorts_factory.approvals import ApprovalStore, SpeechSelection
from shorts_factory.tts import (
    GEMINI_TTS_MODELS,
    GEMINI_TTS_URL,
    PAID_FLAG,
    SpeechError,
    SpeechResult,
    Transport,
    UrlLibTransport,
    _paid_network_allowed,
    _require_paid,
    _require_script,
)

GEMINI_TTS_BASE = "https://generativelanguage.googleapis.com/v1beta"


def _wrap_pcm(pcm: bytes, rate: int = 24000) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "w") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(pcm)
    return buffer.getvalue()


class GeminiAdapter:
    name = "gemini"
    metered = True

    def __init__(self, transport: Transport | None = None) -> None:
        self.transport = transport

    def build_body(self, text: str, selection: SpeechSelection) -> dict[str, Any]:
        if selection.provider != self.name:
            raise SpeechError("refusing to reroute a non-Gemini selection to Gemini")
        if selection.model not in GEMINI_TTS_MODELS:
            raise SpeechError(
                f"Gemini speech model must be one of {sorted(GEMINI_TTS_MODELS)}; "
                f"refusing {selection.model!r}. Chat models are not used for narration."
            )
        if not selection.voice_id:
            raise SpeechError("Gemini voice is empty")
        return {
            "contents": [{"parts": [{"text": text}]}],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": selection.voice_id}}},
            },
        }

    def endpoint(self, model: str) -> str:
        return GEMINI_TTS_URL.format(model=model)

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
                f"paid Gemini TTS is blocked. Set {PAID_FLAG}=1 only after you intend to spend."
            )
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or ""
        if not api_key:
            raise SpeechError(
                "GEMINI_API_KEY is missing. A Gemini chat login is not a speech credential. "
                "Put the key in the shorts-factory profile .env."
            )
        url = self.endpoint(selection.model)
        if api_key in url:
            raise SpeechError("refusing to put the Gemini key in the request URL")
        headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}
        transport = self.transport if self.transport is not None else UrlLibTransport()
        raw = transport.post(url, headers, body)
        audio = _audio_from_response(raw)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(audio)
        return SpeechResult(dest, self.name, selection.model, selection.voice_id, True, False)


def _audio_from_response(raw: bytes) -> bytes:
    try:
        payload = json.loads(raw.decode("utf-8"))
        parts = payload["candidates"][0]["content"]["parts"]
    except (UnicodeError, json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
        raise SpeechError("Gemini TTS response was malformed") from exc
    part = next((item for item in parts if "inlineData" in item or "inline_data" in item), None)
    if part is None:
        raise SpeechError("Gemini TTS response contained no audio data")
    encoded = (part.get("inlineData") or part.get("inline_data") or {}).get("data", "")
    if not encoded:
        raise SpeechError("Gemini TTS returned empty audio data")
    try:
        pcm = base64.b64decode(encoded)
    except ValueError as exc:
        raise SpeechError("Gemini TTS audio was not base64") from exc
    return _wrap_pcm(pcm)
