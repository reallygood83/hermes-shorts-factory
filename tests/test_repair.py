import os
import stat
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from shorts_factory.onboard_ui import decide_chat_model, headless_prompt
from shorts_factory.repair import (
    OnboardRequest,
    OnboardResult,
    RepairError,
    apply_result,
    diagnose,
    run_repair,
)


def _profile(root: Path) -> Path:
    profile = root / "profiles" / "shorts-factory"
    profile.mkdir(parents=True)
    (profile / "config.yaml").write_text("tts:\n  provider: xai\n", encoding="utf-8")
    (profile / "memories").mkdir()
    (profile / "memories" / "keep.txt").write_text("stay\n", encoding="utf-8")
    (root / "SOUL.md").write_text("PRIMARY\n", encoding="utf-8")
    (root / "config.yaml").write_text(
        "model:\n  provider: gemini\n  default: gemini-3.8-flash\n  api_key: super-secret\n",
        encoding="utf-8",
    )
    return profile


class RepairTests(unittest.TestCase):
    def test_missing_model_explains_storage_unavailable(self) -> None:
        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            _profile(home)
            report = diagnose(home)
            self.assertFalse(report["ok"])
            self.assertEqual(report["causes"][0]["detail"], "storage_unavailable")
            self.assertIn("repair_chat.py", report["causes"][0]["action"])

    def test_cancel_writes_nothing(self) -> None:
        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            profile = _profile(home)
            before = (profile / "config.yaml").read_text(encoding="utf-8")
            outcome = apply_result(home, OnboardResult(cancelled=True))
            self.assertFalse(outcome["wrote"])
            self.assertEqual((profile / "config.yaml").read_text(encoding="utf-8"), before)
            self.assertFalse((profile / ".env").exists())

    def test_default_model_is_copied_without_secrets(self) -> None:
        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            profile = _profile(home)
            (profile / ".env").write_text("XAI_API_KEY=keep-me\n", encoding="utf-8")
            outcome = run_repair(
                home,
                prompt=lambda request: OnboardResult(
                    cancelled=False,
                    chat_provider=request.default_provider,
                    chat_model=request.default_model,
                    tts_provider="gemini",
                    tts_model="gemini-3.8-flash-tts",
                    tts_voice="Kore",
                    gemini_api_key="gemini-new",
                ),
            )
            text = (profile / "config.yaml").read_text(encoding="utf-8")
            self.assertIn("default: gemini-3.8-flash", text)
            self.assertIn("provider: gemini", text)
            self.assertNotIn("super-secret", text)
            self.assertIn("provider: gemini", text.split("tts:", 1)[1])
            env = (profile / ".env").read_text(encoding="utf-8")
            self.assertIn("XAI_API_KEY=keep-me", env)
            self.assertIn("GEMINI_API_KEY=gemini-new", env)
            self.assertEqual(stat.S_IMODE((profile / ".env").stat().st_mode), 0o600)
            self.assertEqual((home / "SOUL.md").read_text(encoding="utf-8"), "PRIMARY\n")
            self.assertEqual((profile / "memories" / "keep.txt").read_text(encoding="utf-8"), "stay\n")
            self.assertNotIn("super-secret", str(outcome))
            again = run_repair(
                home,
                preset=OnboardResult(
                    cancelled=False,
                    chat_provider="gemini",
                    chat_model="gemini-3.8-flash",
                ),
            )
            self.assertEqual((profile / "config.yaml").read_text(encoding="utf-8"), text)
            self.assertTrue(again["wrote"])

    def test_question_choices(self) -> None:
        request = OnboardRequest(
            chat_provider="",
            chat_model="",
            tts_provider="",
            tts_model="",
            tts_voice="",
            has_gemini_key=False,
            has_xai_key=False,
            config_path=Path("config.yaml"),
            env_path=Path(".env"),
            default_provider="xai",
            default_model="grok-4.6",
        )
        provider, model = decide_chat_model("default", request)
        self.assertEqual((provider, model), ("xai", "grok-4.6"))
        with self.assertRaises(RepairError):
            decide_chat_model("custom", request, "", "")
        answers = iter(["2", "openai", "gpt-5.4", "3", "n"])
        result = headless_prompt(request, input_fn=lambda _prompt: next(answers), secret_fn=lambda _prompt: "")
        self.assertFalse(result.cancelled)
        self.assertEqual(result.chat_model, "gpt-5.4")
        self.assertEqual(result.tts_provider, "")

    def test_tts_model_rejected_as_chat_model(self) -> None:
        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            _profile(home)
            with self.assertRaises(RepairError):
                apply_result(
                    home,
                    OnboardResult(cancelled=False, chat_provider="gemini", chat_model="gemini-3.8-flash-tts"),
                )


if __name__ == "__main__":
    unittest.main()
