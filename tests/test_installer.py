import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from shorts_factory.installer import repo_root, run_install


class InstallerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.home = Path(self.directory.name) / "hermes"
        self.home.mkdir()
        (self.home / "SOUL.md").write_text("PRIMARY SOUL\n", encoding="utf-8")
        (self.home / "config.yaml").write_text("primary: true\n", encoding="utf-8")
        (self.home / ".env").write_text("PRIMARY_SECRET=do-not-touch\n", encoding="utf-8")
        other = self.home / "profiles" / "daily"
        other.mkdir(parents=True)
        (other / "SOUL.md").write_text("OTHER SOUL\n", encoding="utf-8")
        (other / "config.yaml").write_text("other: true\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.directory.cleanup()

    def _snapshot(self) -> dict[str, str]:
        paths = [
            self.home / "SOUL.md",
            self.home / "config.yaml",
            self.home / ".env",
            self.home / "profiles" / "daily" / "SOUL.md",
            self.home / "profiles" / "daily" / "config.yaml",
        ]
        return {str(path): path.read_text(encoding="utf-8") for path in paths}

    def test_dry_run_writes_nothing(self) -> None:
        before = self._snapshot()
        report = run_install(repo_root(), self.home, apply=False, method="file", force_config=False)
        self.assertEqual(report.mode, "dry-run")
        self.assertFalse((self.home / "profiles" / "shorts-factory").exists())
        self.assertEqual(before, self._snapshot())
        self.assertNotIn("PRIMARY_SECRET", "\n".join(report.lines))

    def test_apply_is_isolated_and_idempotent(self) -> None:
        before = self._snapshot()
        first = run_install(repo_root(), self.home, apply=True, method="file", force_config=False)
        profile = self.home / "profiles" / "shorts-factory"
        self.assertTrue((profile / "SOUL.md").is_file())
        self.assertTrue((profile / "skills" / "shorts-factory" / "SKILL.md").is_file())
        self.assertIn("provider: xai", (profile / "config.yaml").read_text(encoding="utf-8"))
        self.assertNotIn("eleven", (profile / "config.yaml").read_text(encoding="utf-8").lower())
        self.assertFalse((profile / ".env").exists())
        self.assertIn("XAI_API_KEY", (profile / ".env.example").read_text(encoding="utf-8"))
        self.assertNotIn("xai-", (profile / ".env.example").read_text(encoding="utf-8"))
        self.assertEqual(before, self._snapshot())

        (profile / ".env").write_text("XAI_API_KEY=local-secret\n", encoding="utf-8")
        (profile / "config.yaml").write_text("tts:\n  provider: xai\n  note: user-tuned\n", encoding="utf-8")
        (profile / "memories").mkdir()
        (profile / "memories" / "note.md").write_text("keep me\n", encoding="utf-8")
        second = run_install(repo_root(), self.home, apply=True, method="file", force_config=False)
        self.assertIn("kept existing config.yaml", "\n".join(second.lines))
        self.assertIn("user-tuned", (profile / "config.yaml").read_text(encoding="utf-8"))
        self.assertEqual((profile / ".env").read_text(encoding="utf-8"), "XAI_API_KEY=local-secret\n")
        self.assertEqual((profile / "memories" / "note.md").read_text(encoding="utf-8"), "keep me\n")
        self.assertNotIn("local-secret", "\n".join(second.lines))
        self.assertEqual(before, self._snapshot())
        self.assertEqual(first.profile_dir, second.profile_dir)

    def test_update_backs_up_soul_without_touching_others(self) -> None:
        run_install(repo_root(), self.home, apply=True, method="file", force_config=False)
        profile = self.home / "profiles" / "shorts-factory"
        (profile / "SOUL.md").write_text("local soul edit\n", encoding="utf-8")
        before = self._snapshot()
        run_install(repo_root(), self.home, apply=True, method="file", force_config=False)
        self.assertEqual((profile / "SOUL.md").read_text(encoding="utf-8"), (repo_root() / "SOUL.md").read_text(encoding="utf-8"))
        backups = list((profile / "backups").rglob("SOUL.md"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(encoding="utf-8"), "local soul edit\n")
        self.assertEqual(before, self._snapshot())

    def test_unrelated_profile_is_refused(self) -> None:
        profile = self.home / "profiles" / "shorts-factory"
        profile.mkdir(parents=True)
        (profile / "SOUL.md").write_text("unrelated\n", encoding="utf-8")
        report = run_install(repo_root(), self.home, apply=True, method="file", force_config=False)
        self.assertTrue(report.refused)
        self.assertEqual((profile / "SOUL.md").read_text(encoding="utf-8"), "unrelated\n")
        self.assertFalse((profile / "config.yaml").exists())

    def test_source_env_is_not_copied(self) -> None:
        source = Path(self.directory.name) / "source"
        skill = source / "skills" / "shorts-factory"
        skill.mkdir(parents=True)
        (source / "distribution.yaml").write_text("name: shorts-factory\nversion: 1.0.0\n", encoding="utf-8")
        (source / "SOUL.md").write_text("soul\n", encoding="utf-8")
        (source / "config.yaml").write_text("tts:\n  provider: xai\n", encoding="utf-8")
        (source / "profile.yaml").write_text("display_name: Shorts Factory\n", encoding="utf-8")
        (skill / "SKILL.md").write_text("skill\n", encoding="utf-8")
        (source / ".env").write_text("XAI_API_KEY=should-not-copy\n", encoding="utf-8")
        run_install(source, self.home, apply=True, method="file", force_config=False)
        profile = self.home / "profiles" / "shorts-factory"
        self.assertFalse((profile / ".env").exists())
        self.assertNotIn("should-not-copy", (profile / ".env.example").read_text(encoding="utf-8"))

    def test_hermes_cli_uses_documented_arguments(self) -> None:
        bindir = Path(self.directory.name) / "bin"
        bindir.mkdir()
        log = Path(self.directory.name) / "hermes.log"
        stub = bindir / "hermes"
        stub.write_text(
            "#!/bin/sh\n"
            f"printf '%s\\n' \"$@\" > {log}\n"
            "mkdir -p \"$HERMES_HOME/profiles/shorts-factory\"\n"
            "printf 'name: shorts-factory\\n' > \"$HERMES_HOME/profiles/shorts-factory/distribution.yaml\"\n",
            encoding="utf-8",
        )
        stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
        env = os.environ.copy()
        env["PATH"] = str(bindir) + os.pathsep + env.get("PATH", "")
        env["XAI_API_KEY"] = "xai-should-not-appear-in-argv"
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "shorts_factory.installer",
                "--apply",
                "--method",
                "hermes",
                "--hermes-home",
                str(self.home),
            ],
            cwd=repo_root(),
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr + completed.stdout)
        logged = log.read_text(encoding="utf-8")
        self.assertIn("profile", logged)
        self.assertIn("install", logged)
        self.assertIn("--name", logged)
        self.assertIn("shorts-factory", logged)
        self.assertIn("--alias", logged)
        self.assertIn("-y", logged)
        self.assertNotIn("--clone", logged)
        self.assertNotIn("xai-should-not-appear-in-argv", logged)
        self.assertEqual((self.home / "SOUL.md").read_text(encoding="utf-8"), "PRIMARY SOUL\n")


if __name__ == "__main__":
    unittest.main()
