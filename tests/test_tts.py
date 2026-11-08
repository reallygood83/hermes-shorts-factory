import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from shorts_factory.approvals import ApprovalStore, SpeechSelection
from shorts_factory.tts import (
    OPENAI_SPEECH_URL,
    XAI_TTS_URL,
    OpenAIAdapter,
    SpeechError,
    XaiAdapter,
    adapter_for,
    redacted_call,
    resolve_selection,
)


class BoomTransport:
    def post(self, url: str, headers: dict, body: dict) -> bytes:
        raise AssertionError(f"network call {url}")


class MemoryTransport:
    def __init__(self) -> None:
        self.calls = []

    def post(self, url: str, headers: dict, body: dict) -> bytes:
        self.calls.append((url, headers, body))
        return b"ID3fake"


XAI = SpeechSelection("xai", "grok-tts", "eve", "ko")
SCRIPT = "물 한 잔."


class TtsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.store = ApprovalStore(Path(self.directory.name) / "approvals.json")
        self.dest = Path(self.directory.name) / "out.mp3"
        self.env = patch.dict(os.environ, {}, clear=False)
        self.env.start()
        os.environ.pop("SHORTS_FACTORY_ALLOW_PAID_TTS", None)
        os.environ.pop("XAI_API_KEY", None)
        os.environ.pop("OPENAI_API_KEY", None)
        os.environ.pop("VOICE_TOOLS_OPENAI_KEY", None)

    def tearDown(self) -> None:
        self.env.stop()
        self.directory.cleanup()

    def test_missing_approvals_do_not_open_a_socket(self) -> None:
        with patch("shorts_factory.tts.urlrequest.urlopen", side_effect=AssertionError("socket")):
            with self.assertRaises(SpeechError):
                XaiAdapter(BoomTransport()).synthesize(SCRIPT, XAI, self.store, SCRIPT, self.dest)

    def test_paid_flag_and_key_required_before_transport(self) -> None:
        self.store.approve_script(SCRIPT, XAI)
        self.store.approve_paid(XAI)
        with self.assertRaises(SpeechError):
            XaiAdapter(BoomTransport()).synthesize(SCRIPT, XAI, self.store, SCRIPT, self.dest)
        os.environ["SHORTS_FACTORY_ALLOW_PAID_TTS"] = "1"
        with self.assertRaises(SpeechError) as missing_key:
            XaiAdapter(BoomTransport()).synthesize(SCRIPT, XAI, self.store, SCRIPT, self.dest)
        self.assertIn("XAI_API_KEY", str(missing_key.exception))
        self.assertIn("OAuth", str(missing_key.exception))

    def test_xai_call_shape_and_no_fallback(self) -> None:
        self.store.approve_script(SCRIPT, XAI)
        self.store.approve_paid(XAI)
        os.environ["SHORTS_FACTORY_ALLOW_PAID_TTS"] = "1"
        os.environ["XAI_API_KEY"] = "xai-test-secret"
        transport = MemoryTransport()
        result = XaiAdapter(transport).synthesize(SCRIPT, XAI, self.store, SCRIPT, self.dest)
        self.assertEqual(result.provider, "xai")
        self.assertEqual(len(transport.calls), 1)
        url, headers, body = transport.calls[0]
        self.assertEqual(url, XAI_TTS_URL)
        self.assertEqual(body["language"], "ko")
        self.assertEqual(body["voice_id"], "eve")
        self.assertNotIn("model", body)
        self.assertEqual(body["output_format"]["codec"], "mp3")
        hidden = redacted_call(url, headers, body)
        self.assertEqual(hidden["headers"]["Authorization"], "Bearer [redacted]")
        self.assertNotIn("xai-test-secret", str(hidden))

        class Fail:
            def post(self, url: str, headers: dict, body: dict) -> bytes:
                raise SpeechError("upstream 403")

        with self.assertRaises(SpeechError) as failed:
            XaiAdapter(Fail()).synthesize(SCRIPT, XAI, self.store, SCRIPT, self.dest)
        self.assertIn("403", str(failed.exception))
        self.assertNotIn("openai", str(failed.exception).lower())

    def test_voice_change_is_not_silent(self) -> None:
        self.store.approve_script(SCRIPT, XAI)
        switched = SpeechSelection("xai", "grok-tts", "ara", "ko")
        with self.assertRaises(SpeechError):
            XaiAdapter(BoomTransport()).synthesize(SCRIPT, switched, self.store, SCRIPT, self.dest)

    def test_env_does_not_override_project_voice(self) -> None:
        selection = resolve_selection(
            {"provider": "xai", "model": "grok-tts", "voice_id": "eve", "language": "ko"},
            {"SHORTS_FACTORY_XAI_VOICE_ID": "ara"},
        )
        self.assertEqual(selection.voice_id, "eve")

    def test_openai_rejects_legacy_models(self) -> None:
        selection = SpeechSelection("openai", "tts-1", "alloy", "ko")
        self.store.approve_script(SCRIPT, selection)
        self.store.approve_paid(selection)
        os.environ["SHORTS_FACTORY_ALLOW_PAID_TTS"] = "1"
        os.environ["OPENAI_API_KEY"] = "sk-test"
        with self.assertRaises(SpeechError):
            OpenAIAdapter(BoomTransport()).synthesize(SCRIPT, selection, self.store, SCRIPT, self.dest)
        allowed = SpeechSelection("openai", "gpt-4o-mini-tts", "alloy", "ko")
        self.store.approve_script(SCRIPT, allowed)
        self.store.approve_paid(allowed)
        transport = MemoryTransport()
        OpenAIAdapter(transport).synthesize(SCRIPT, allowed, self.store, SCRIPT, self.dest)
        self.assertEqual(transport.calls[0][0], OPENAI_SPEECH_URL)
        self.assertEqual(transport.calls[0][2]["model"], "gpt-4o-mini-tts")

    def test_claude_codex_and_elevenlabs_fail_closed(self) -> None:
        for name in ("claude", "anthropic", "codex", "elevenlabs"):
            with self.assertRaises(SpeechError):
                adapter_for(name).synthesize()

    def test_unknown_language_fails(self) -> None:
        selection = SpeechSelection("xai", "grok-tts", "eve", "zz")
        with self.assertRaises(SpeechError):
            XaiAdapter().build_body("안녕", selection)


if __name__ == "__main__":
    unittest.main()
