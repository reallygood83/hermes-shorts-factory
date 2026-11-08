import tempfile
import unittest
from pathlib import Path

from shorts_factory.approvals import ApprovalError, ApprovalStore, SpeechSelection


XAI = SpeechSelection("xai", "grok-tts", "eve", "ko")
OTHER_VOICE = SpeechSelection("xai", "grok-tts", "ara", "ko")


class ApprovalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.store = ApprovalStore(Path(self.directory.name) / "approvals.json")

    def tearDown(self) -> None:
        self.directory.cleanup()

    def test_missing_script_blocks(self) -> None:
        with self.assertRaises(ApprovalError):
            self.store.assert_script("대본", XAI)

    def test_script_approval_does_not_open_paid_or_publish(self) -> None:
        self.store.approve_script("대본", XAI)
        self.store.assert_script("대본", XAI)
        with self.assertRaises(ApprovalError):
            self.store.assert_paid(XAI)
        with self.assertRaises(ApprovalError):
            self.store.assert_publish()

    def test_changed_script_or_voice_blocks(self) -> None:
        self.store.approve_script("대본", XAI)
        with self.assertRaises(ApprovalError):
            self.store.assert_script("다른 대본", XAI)
        with self.assertRaises(ApprovalError):
            self.store.assert_script("대본", OTHER_VOICE)

    def test_paid_must_match_selection(self) -> None:
        self.store.approve_paid(XAI)
        self.store.assert_paid(XAI)
        with self.assertRaises(ApprovalError):
            self.store.assert_paid(OTHER_VOICE)

    def test_offline_is_not_a_paid_credit(self) -> None:
        offline = SpeechSelection("offline", "offline-placeholder", "offline-tone", "ko")
        with self.assertRaises(ApprovalError):
            self.store.approve_paid(offline)

    def test_publish_is_local_only(self) -> None:
        with self.assertRaises(ApprovalError):
            self.store.approve_publish("youtube")
        self.store.approve_publish()
        self.assertFalse(self.store.load()["publish"]["uploaded"])


if __name__ == "__main__":
    unittest.main()
