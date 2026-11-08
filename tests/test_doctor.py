import unittest
from unittest.mock import patch

from shorts_factory.doctor import run_checks


class DoctorTests(unittest.TestCase):
    def test_missing_binaries_do_not_install_anything(self) -> None:
        with patch("shorts_factory.doctor.sys.platform", "darwin"):
            checks = {item.name: item for item in run_checks(which=lambda _name: None)}
        self.assertEqual(checks["ffmpeg"].status, "missing")
        self.assertIn("brew install ffmpeg", checks["ffmpeg"].install_hint)
        self.assertIn("pip install manim", checks["manim"].install_hint)
        self.assertNotIn("curl", checks["manim"].install_hint)

    def test_windows_hint_is_documented_not_executed(self) -> None:
        with patch("shorts_factory.doctor.sys.platform", "win32"):
            checks = {item.name: item for item in run_checks(which=lambda _name: None)}
        self.assertIn("winget install", checks["ffmpeg"].install_hint)


if __name__ == "__main__":
    unittest.main()
