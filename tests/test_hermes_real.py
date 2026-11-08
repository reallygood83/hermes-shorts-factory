"""Real Hermes CLI checks. Skipped when `hermes` is not on PATH.

These do not call a model or a speech API. They use a temporary HERMES_HOME.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from shorts_factory.installer import repo_root


def _hermes_runs() -> bool:
    binary = shutil.which("hermes")
    if not binary:
        return False
    completed = subprocess.run(
        [binary, "profile", "install", "--help"],
        check=False,
        text=True,
        capture_output=True,
        timeout=60,
    )
    return completed.returncode == 0 and "--alias" in completed.stdout


@unittest.skipUnless(_hermes_runs(), "official hermes CLI is not runnable")
class RealHermesInstallTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.home = Path(self.directory.name) / "hermes"
        self.home.mkdir()
        (self.home / "SOUL.md").write_text("PRIMARY SOUL\n", encoding="utf-8")
        (self.home / "config.yaml").write_text("primary: true\n", encoding="utf-8")
        other = self.home / "profiles" / "daily"
        other.mkdir(parents=True)
        (other / "SOUL.md").write_text("OTHER SOUL\n", encoding="utf-8")
        self.alias = Path.home() / ".local" / "bin" / "shorts-factory"
        self.alias_existed = self.alias.exists()
        self.env = {
            "HOME": str(Path.home()),
            "PATH": os.environ.get("PATH", ""),
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "TERM": "dumb",
            "HERMES_HOME": str(self.home),
        }

    def tearDown(self) -> None:
        if self.alias.exists() and not self.alias_existed:
            self.alias.unlink()
        self.directory.cleanup()

    def _run(self, argv: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            argv,
            cwd=repo_root(),
            env=self.env,
            text=True,
            capture_output=True,
            check=False,
            timeout=180,
            stdin=subprocess.DEVNULL,
        )

    def test_install_update_select_without_bot_chat(self) -> None:
        dry = self._run(
            [
                sys.executable,
                "-m",
                "shorts_factory.installer",
                "--dry-run",
                "--method",
                "hermes",
                "--hermes-home",
                str(self.home),
                "--source",
                str(repo_root()),
            ]
        )
        self.assertEqual(dry.returncode, 0, dry.stderr + dry.stdout)
        self.assertFalse((self.home / "profiles" / "shorts-factory").exists())
        self.assertIn("hermes profile install", dry.stdout)

        first = self._run(
            [
                sys.executable,
                "-m",
                "shorts_factory.installer",
                "--apply",
                "--method",
                "hermes",
                "--hermes-home",
                str(self.home),
                "--source",
                str(repo_root()),
            ]
        )
        self.assertEqual(first.returncode, 0, first.stderr + first.stdout)
        profile = self.home / "profiles" / "shorts-factory"
        self.assertTrue((profile / "SOUL.md").is_file())
        self.assertFalse((profile / ".env").exists())
        self.assertNotIn("ui_meta", (profile / "profile.yaml").read_text(encoding="utf-8"))
        self.assertEqual((self.home / "SOUL.md").read_text(encoding="utf-8"), "PRIMARY SOUL\n")
        self.assertEqual((self.home / "profiles" / "daily" / "SOUL.md").read_text(encoding="utf-8"), "OTHER SOUL\n")

        listed = self._run(["hermes", "profile", "list"])
        self.assertEqual(listed.returncode, 0, listed.stderr + listed.stdout)
        self.assertIn("shorts-factory", listed.stdout)
        self.assertIn("◆default", listed.stdout)

        selected = self._run(["hermes", "-p", "shorts-factory", "profile"])
        self.assertEqual(selected.returncode, 0, selected.stderr + selected.stdout)
        self.assertIn("shorts-factory", selected.stdout)

        (profile / ".env").write_text("XAI_API_KEY=local-test-not-real\n", encoding="utf-8")
        second = self._run(
            [
                sys.executable,
                "-m",
                "shorts_factory.installer",
                "--apply",
                "--method",
                "hermes",
                "--hermes-home",
                str(self.home),
                "--source",
                str(repo_root()),
            ]
        )
        self.assertEqual(second.returncode, 0, second.stderr + second.stdout)
        self.assertIn("hermes profile update shorts-factory -y", second.stdout)
        self.assertEqual((profile / ".env").read_text(encoding="utf-8"), "XAI_API_KEY=local-test-not-real\n")
        self.assertNotIn("local-test-not-real", second.stdout)
        self.assertEqual((self.home / "SOUL.md").read_text(encoding="utf-8"), "PRIMARY SOUL\n")

        chat = self._run(
            [
                "hermes",
                "-p",
                "shorts-factory",
                "chat",
                "--cli",
                "-c",
                "Bot Chat",
                "--create-if-missing",
            ]
        )
        self.assertNotEqual(chat.returncode, 0)
        combined = chat.stdout + chat.stderr
        self.assertIn("could not be created", combined)
        database = profile / "state.db"
        if database.is_file():
            connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
            titles = [row[0] for row in connection.execute("SELECT title FROM sessions")]
            self.assertNotIn("Bot Chat", titles)


if __name__ == "__main__":
    unittest.main()
