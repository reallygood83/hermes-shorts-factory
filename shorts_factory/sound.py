"""Beds and effects.

Gemini's documented speech API recites text. It is not a sound-effects or
music API, so those tracks stay on the local original tone.
"""

from __future__ import annotations

from pathlib import Path

from shorts_factory.tts import SpeechError, write_tone


def gemini_sound_effect_status() -> dict[str, str]:
    return {
        "provider": "gemini",
        "kind": "sfx",
        "status": "unsupported",
        "detail": (
            "Gemini TTS (generateContent, responseModalities AUDIO) synthesizes speech. "
            "Google's speech guide does not provide a separate sound-effects endpoint. "
            "Use local-tone for an original tone, or keep xAI/Gemini for narration only."
        ),
    }


def render_bed(path: Path, seconds: float, kind: str) -> dict[str, str]:
    if kind == "sfx-gemini":
        raise SpeechError(gemini_sound_effect_status()["detail"])
    if kind != "local-tone":
        raise SpeechError(f"unknown bed {kind!r}; the original local bed is local-tone")
    write_tone(path, seconds=seconds, frequency=196, volume=0.08)
    return {"kind": "local-tone", "path": str(path), "third_party_media": "false"}
