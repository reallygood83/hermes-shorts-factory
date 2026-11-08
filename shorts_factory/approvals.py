"""Separate gates for script, paid speech, and publish.

A missing gate blocks the action. Approving one gate never fills another.
The approved speech selection is part of the script gate; a later voice or
model change fails closed until the script is approved again.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ApprovalError(Exception):
    """The requested action is blocked by an approval gate."""


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def script_sha256(script_text: str) -> str:
    return hashlib.sha256(script_text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SpeechSelection:
    provider: str
    model: str
    voice_id: str
    language: str

    def as_dict(self) -> dict[str, str]:
        return {
            "provider": self.provider,
            "model": self.model,
            "voice_id": self.voice_id,
            "language": self.language,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "SpeechSelection":
        return cls(
            provider=str(raw["provider"]),
            model=str(raw["model"]),
            voice_id=str(raw["voice_id"]),
            language=str(raw["language"]),
        )


def _blank_gate() -> dict[str, Any]:
    return {"status": "pending"}


def empty_state() -> dict[str, Any]:
    return {
        "version": 1,
        "script": _blank_gate(),
        "paid_credits": _blank_gate(),
        "publish": _blank_gate(),
    }


class ApprovalStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return empty_state()
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("version") != 1:
            raise ApprovalError(f"unsupported approval file: {self.path}")
        for gate in ("script", "paid_credits", "publish"):
            data.setdefault(gate, _blank_gate())
        return data

    def save(self, state: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(state, ensure_ascii=False, indent=2) + "\n"
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(payload, encoding="utf-8")
        temporary.replace(self.path)

    def approve_script(self, script_text: str, selection: SpeechSelection) -> dict[str, Any]:
        state = self.load()
        state["script"] = {
            "status": "approved",
            "sha256": script_sha256(script_text),
            "speech": selection.as_dict(),
            "approved_at": _now(),
        }
        self.save(state)
        return state["script"]

    def approve_paid(self, selection: SpeechSelection, scope: str = "tts") -> dict[str, Any]:
        if scope != "tts":
            raise ApprovalError("paid approval scope must be tts")
        if selection.provider == "offline":
            raise ApprovalError("offline placeholder speech is not a paid credit")
        state = self.load()
        state["paid_credits"] = {
            "status": "approved",
            "scope": scope,
            "speech": selection.as_dict(),
            "approved_at": _now(),
        }
        self.save(state)
        return state["paid_credits"]

    def approve_publish(self, target: str = "manual-local-bundle") -> dict[str, Any]:
        if target != "manual-local-bundle":
            raise ApprovalError(
                "publish approval only covers a local bundle; it does not authorize upload"
            )
        state = self.load()
        state["publish"] = {
            "status": "approved",
            "target": target,
            "uploaded": False,
            "approved_at": _now(),
        }
        self.save(state)
        return state["publish"]

    def assert_script(self, script_text: str, selection: SpeechSelection) -> None:
        gate = self.load()["script"]
        if gate.get("status") != "approved":
            raise ApprovalError("script approval is missing")
        digest = script_sha256(script_text)
        if gate.get("sha256") != digest:
            raise ApprovalError("script changed after approval; approve the new text")
        approved = gate.get("speech")
        if not isinstance(approved, dict):
            raise ApprovalError("script approval has no speech selection")
        if SpeechSelection.from_dict(approved) != selection:
            raise ApprovalError(
                "speech provider, model, voice, or language differs from the approved script"
            )

    def assert_paid(self, selection: SpeechSelection) -> None:
        gate = self.load()["paid_credits"]
        if gate.get("status") != "approved" or gate.get("scope") != "tts":
            raise ApprovalError("paid TTS approval is missing")
        approved = gate.get("speech")
        if not isinstance(approved, dict):
            raise ApprovalError("paid TTS approval has no speech selection")
        if SpeechSelection.from_dict(approved) != selection:
            raise ApprovalError("paid TTS approval does not match the speech selection")

    def assert_publish(self) -> None:
        gate = self.load()["publish"]
        if gate.get("status") != "approved":
            raise ApprovalError("publish approval is missing")
        if gate.get("target") != "manual-local-bundle":
            raise ApprovalError("publish approval target is not a local bundle")
