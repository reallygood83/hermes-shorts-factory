import base64
import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from shorts_factory.approvals import ApprovalStore, SpeechSelection
from shorts_factory.gemini_tts import GeminiAdapter
from shorts_factory.sound import gemini_sound_effect_status, render_bed
from shorts_factory.tts import SpeechError, redacted_call


class Boom:
    def post(self, url: str, headers: dict, body: dict) -> bytes:
        raise AssertionError(url)


class Memory:
    def __init__(self) -> None:
        self.calls = []

    def post(self, url: str, headers: dict, body: dict) -> bytes:
        self.calls.append((url, headers, body))
        pcm = (b"\x00\x01" * 20)
        payload = {
            "candidates": [
                {"content": {"parts": [{"inlineData": {"mimeType": "audio/pcm", "data": base64.b64encode(pcm).decode()}}]}}
            ]
        }
        return json.dumps(payload).encode("utf-8")


class GeminiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.store = ApprovalStore(Path(self.tmp.name) / "approvals.json")
        self.dest = Path(self.tmp.name) / "out.wav"
        self.selection = SpeechSelection("gemini", "gemini-3.8-flash-tts", "Kore", "ko")
        self.script = "안녕하세요."
        self.env = patch.dict(os.environ, {}, clear=False)
        self.env.start()
        os.environ.pop("SHORTS_FACTORY_ALLOW_PAID_TTS", None)
        os.environ.pop("GEMINI_API_KEY", None)

    def tearDown(self) -> None:
        self.env.stop()
        self.tmp.cleanup()

    def test_blocked_before_transport(self) -> None:
        with self.assertRaises(SpeechError):
            GeminiAdapter(Boom()).synthesize(self.script, self.selection, self.store, self.script, self.dest)

    def test_mocked_audio_keeps_key_out_of_url(self) -> None:
        self.store.approve_script(self.script, self.selection)
        self.store.approve_paid(self.selection)
        os.environ["SHORTS_FACTORY_ALLOW_PAID_TTS"] = "1"
        os.environ["GEMINI_API_KEY"] = "gemini-test-secret"
        transport = Memory()
        result = GeminiAdapter(transport).synthesize(self.script, self.selection, self.store, self.script, self.dest)
        self.assertEqual(result.model, "gemini-3.8-flash-tts")
        self.assertTrue(self.dest.is_file())
        url, headers, body = transport.calls[0]
        self.assertTrue(url.endswith("/models/gemini-3.8-flash-tts:generateContent"))
        self.assertNotIn("gemini-test-secret", url)
        self.assertEqual(body["generationConfig"]["responseModalities"], ["AUDIO"])
        hidden = redacted_call(url, headers, body)
        self.assertEqual(hidden["headers"]["x-goog-api-key"], "[redacted]")
        self.assertNotIn("gemini-test-secret", json.dumps(hidden))

    def test_chat_model_is_not_a_speech_fallback(self) -> None:
        bad = SpeechSelection("gemini", "gemini-3.8-flash", "Kore", "ko")
        with self.assertRaises(SpeechError):
            GeminiAdapter(Boom()).build_body("안녕", bad)

    def test_sfx_is_disabled(self) -> None:
        status = gemini_sound_effect_status()
        self.assertEqual(status["status"], "unsupported")
        with self.assertRaises(SpeechError):
            render_bed(Path(self.tmp.name) / "bed.wav", 1, "sfx-gemini")
        made = render_bed(Path(self.tmp.name) / "bed.wav", 1, "local-tone")
        self.assertEqual(made["kind"], "local-tone")


if __name__ == "__main__":
    unittest.main()
