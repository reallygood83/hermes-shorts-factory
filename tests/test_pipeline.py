import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from shorts_factory.pipeline import (
    copy_smoke,
    init_project,
    load_project,
    main,
    narrate,
    publish_bundle,
    render,
    validate,
    write_analysis,
)
ROOT = Path(__file__).resolve().parents[1]
SMOKE = ROOT / "examples" / "smoke"


class PipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.project = Path(self.directory.name) / "film"

    def tearDown(self) -> None:
        self.directory.cleanup()

    def test_safety_flags_and_aspect(self) -> None:
        init_project(self.project, "테스트 주제", "16:9")
        project = load_project(self.project)
        self.assertEqual((project["width"], project["height"]), (1920, 1080))
        raw = json.loads((self.project / "project.json").read_text(encoding="utf-8"))
        raw["real_person_likeness"] = True
        (self.project / "project.json").write_text(json.dumps(raw), encoding="utf-8")
        with self.assertRaises(Exception):
            load_project(self.project)

    def test_paid_narration_blocked_without_approvals(self) -> None:
        init_project(self.project, "물")
        with patch("shorts_factory.tts.urlrequest.urlopen", side_effect=AssertionError("socket")):
            self.assertEqual(main(["narrate", str(self.project)]), 2)
            self.assertEqual(main(["approve-script", str(self.project)]), 0)
            self.assertEqual(main(["narrate", str(self.project)]), 2)
            self.assertEqual(main(["approve-paid", str(self.project)]), 0)
            self.assertEqual(main(["narrate", str(self.project)]), 2)
        self.assertFalse((self.project / "output" / "narration.mp3").exists())

    def test_publish_blocked_until_validation(self) -> None:
        copy_smoke(self.project, SMOKE)
        self.assertEqual(main(["approve-publish", str(self.project)]), 0)
        with self.assertRaises(Exception):
            publish_bundle(self.project)
        self.assertFalse((self.project / "output" / "publish-bundle.json").exists())

    def test_analysis_does_not_claim_rea_video_ran(self) -> None:
        copy_smoke(self.project, SMOKE)
        analysis = write_analysis(self.project, load_project(self.project))
        self.assertFalse(analysis["rea_video"]["executed_rea_video"])
        self.assertTrue(analysis["rea_video"]["available"])
        self.assertEqual(analysis["rea_video"]["scene_count"], 2)
        self.assertFalse(analysis["copied_media"])

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg not installed")
    def test_offline_smoke_mp4(self) -> None:
        copy_smoke(self.project, SMOKE)
        self.assertEqual(main(["approve-script", str(self.project)]), 0)
        os.environ.pop("SHORTS_FACTORY_ALLOW_PAID_TTS", None)
        with patch("shorts_factory.tts.urlrequest.urlopen", side_effect=AssertionError("socket")):
            rendered = render(self.project)
        self.assertIn("placeholder", rendered["mix_note"])
        report = validate(self.project)
        self.assertTrue(report["ok"], report["problems"])
        final = self.project / "output" / "final.mp4"
        self.assertGreater(final.stat().st_size, 1000)
        self.assertEqual(main(["publish", str(self.project)]), 2)
        self.assertEqual(main(["approve-publish", str(self.project)]), 0)
        bundle = publish_bundle(self.project)
        self.assertFalse(bundle["uploaded"])
        self.assertFalse(bundle["posted"])

    def test_offline_provider_does_not_require_paid_approval(self) -> None:
        copy_smoke(self.project, SMOKE)
        self.assertEqual(main(["approve-script", str(self.project)]), 0)
        self.assertEqual(main(["approve-paid", str(self.project)]), 2)
        with patch("shorts_factory.tts.urlrequest.urlopen", side_effect=AssertionError("socket")):
            report = narrate(self.project)
        self.assertTrue(report["placeholder"])
        self.assertFalse(report["metered"])


if __name__ == "__main__":
    unittest.main()
