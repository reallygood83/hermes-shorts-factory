"""Install the shorts-factory profile without touching the primary Hermes home.

Dry-run is the default. `--apply` writes only under
`$HERMES_HOME/profiles/shorts-factory`. When the `hermes` executable is on
PATH and the profile is not there yet, `--method auto` runs the documented
command:

    hermes profile install <checkout> --name shorts-factory --alias -y

A second `--apply` against an existing shorts-factory profile runs the
documented `hermes profile update shorts-factory -y`. `config.yaml` is kept
unless `--force-config` is set. Without the `hermes` executable, `--method file`
copies the same owned files.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from shorts_factory import PROFILE_NAME

OWNED_FILES = ("SOUL.md", "config.yaml", "profile.yaml", "distribution.yaml")
OWNED_DIRS = ("skills",)
PRIMARY_FILES = ("SOUL.md", "config.yaml", ".env", "profile.yaml", "auth.json")
ENV_EXAMPLE = """# Created by the shorts-factory installer. Copy to .env and fill locally.
# Do not commit .env. Chat OAuth is not a speech credential.
# XAI_API_KEY=
# SHORTS_FACTORY_XAI_VOICE_ID=
# SHORTS_FACTORY_ALLOW_PAID_TTS=0
"""


class InstallError(Exception):
    """Installation cannot proceed safely."""


@dataclass
class InstallReport:
    mode: str
    method: str
    profile_dir: Path
    lines: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)
    refused: bool = False

    def say(self, line: str) -> None:
        self.lines.append(line)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_hermes_home() -> Path:
    override = os.environ.get("HERMES_HOME")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".hermes"


def hermes_install_argv(source: Path, name: str = PROFILE_NAME) -> list[str]:
    return [
        "hermes",
        "profile",
        "install",
        str(source),
        "--name",
        name,
        "--alias",
        "-y",
    ]


def hermes_update_argv(name: str = PROFILE_NAME, force_config: bool = False) -> list[str]:
    argv = ["hermes", "profile", "update", name, "-y"]
    if force_config:
        argv.append("--force-config")
    return argv


def _read(path: Path) -> bytes | None:
    if not path.is_file():
        return None
    return path.read_bytes()


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(data)
    os.replace(temporary, path)


def _distribution_name(profile_dir: Path) -> str | None:
    manifest = profile_dir / "distribution.yaml"
    if not manifest.is_file():
        return None
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if line.startswith("name:"):
            return line.split(":", 1)[1].strip().strip('"').strip("'")
    return None


def _assert_isolated(hermes_home: Path, source: Path) -> Path:
    home = hermes_home.resolve()
    profile = (home / "profiles" / PROFILE_NAME).resolve()
    source_resolved = source.resolve()
    if home == source_resolved or source_resolved in home.parents:
        raise InstallError("refusing to use the repository as HERMES_HOME")
    if profile == home or home in profile.parents and profile.parent.name != "profiles":
        raise InstallError("profile path escaped the profiles directory")
    try:
        profile.relative_to(home / "profiles")
    except ValueError as exc:
        raise InstallError("profile path is outside HERMES_HOME/profiles") from exc
    return profile


def _backup(profile: Path, relative: str, previous: bytes) -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = profile / "backups" / stamp / relative
    _atomic_write(destination, previous)


def _copy_file(source: Path, profile: Path, relative: str, report: InstallReport, backup: bool) -> None:
    origin = source / relative
    if not origin.is_file():
        raise InstallError(f"distribution is missing {relative}")
    data = origin.read_bytes()
    target = profile / relative
    previous = _read(target)
    if previous == data:
        report.say(f"unchanged {relative}")
        return
    if previous is not None and backup:
        _backup(profile, relative, previous)
        report.say(f"backed up {relative}")
    _atomic_write(target, data)
    report.changed.append(relative)
    report.say(f"wrote {relative}")


def _copy_tree(source: Path, profile: Path, relative: str, report: InstallReport) -> None:
    origin = source / relative
    if not origin.is_dir():
        raise InstallError(f"distribution is missing {relative}/")
    for path in sorted(origin.rglob("*")):
        if not path.is_file():
            continue
        if any(part.startswith(".") for part in path.relative_to(origin).parts):
            continue
        rel = path.relative_to(source).as_posix()
        previous = _read(profile / rel)
        data = path.read_bytes()
        if previous == data:
            report.say(f"unchanged {rel}")
            continue
        if previous is not None:
            _backup(profile, rel, previous)
            report.say(f"backed up {rel}")
        _atomic_write(profile / rel, data)
        report.changed.append(rel)
        report.say(f"wrote {rel}")


def _write_env_example(profile: Path, report: InstallReport) -> None:
    target = profile / ".env.example"
    data = ENV_EXAMPLE.encode("utf-8")
    if _read(target) == data:
        report.say("unchanged .env.example")
        return
    _atomic_write(target, data)
    report.changed.append(".env.example")
    report.say("wrote .env.example")


def profile_conflict(hermes_home: Path, source: Path) -> str | None:
    profile = _assert_isolated(hermes_home, source)
    if not profile.exists():
        return None
    identity = any((profile / name).is_file() for name in ("SOUL.md", "config.yaml", "profile.yaml", ".env"))
    if not identity and not any(profile.iterdir()):
        return None
    if _distribution_name(profile) == PROFILE_NAME:
        return None
    return (
        f"{profile} exists and is not the shorts-factory distribution. "
        "Refusing to overwrite an unrelated profile."
    )


def _populate(source: Path, profile: Path, force_config: bool, report: InstallReport, first_install: bool) -> None:
    for relative in OWNED_FILES:
        if relative == "config.yaml" and not first_install and not force_config:
            report.say("kept existing config.yaml (pass --force-config to replace it)")
            continue
        if relative == "profile.yaml" and (profile / relative).is_file() and not force_config:
            report.say("kept existing profile.yaml (pass --force-config to replace it)")
            continue
        _copy_file(source, profile, relative, report, backup=not first_install)
    for relative in OWNED_DIRS:
        _copy_tree(source, profile, relative, report)
    _write_env_example(profile, report)


def apply_file_layout(
    source: Path,
    hermes_home: Path,
    force_config: bool,
    report: InstallReport,
) -> None:
    profile = _assert_isolated(hermes_home, source)
    conflict = profile_conflict(hermes_home, source)
    if conflict:
        raise InstallError(conflict)
    ours = _distribution_name(profile) == PROFILE_NAME
    if not ours:
        staging = profile.parent / f".{PROFILE_NAME}.installing"
        if staging.exists():
            shutil.rmtree(staging)
        staging.mkdir(parents=True)
        try:
            _populate(source, staging, force_config=True, report=report, first_install=True)
            if profile.exists():
                profile.rmdir()
            staging.rename(profile)
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise
    else:
        _populate(source, profile, force_config, report, first_install=False)
    report.say(f"profile ready at {profile}")
    report.say("open it with: hermes -p shorts-factory chat")
    report.say("alias command is created only by: hermes profile install <repo> --name shorts-factory --alias -y")


def _hermes_available() -> bool:
    return shutil.which("hermes") is not None


def apply_hermes_cli(
    source: Path,
    hermes_home: Path,
    report: InstallReport,
    force_config: bool,
) -> None:
    profile = _assert_isolated(hermes_home, source)
    conflict = profile_conflict(hermes_home, source)
    if conflict:
        raise InstallError(conflict)
    if not _hermes_available():
        raise InstallError("hermes executable not found on PATH")
    if _distribution_name(profile) == PROFILE_NAME:
        argv = hermes_update_argv(force_config=force_config)
    else:
        argv = hermes_install_argv(source)
    report.say("running documented Hermes command: " + " ".join(argv))
    completed = subprocess.run(
        argv,
        cwd=source,
        env={**os.environ, "HERMES_HOME": str(hermes_home)},
        check=False,
        text=True,
        capture_output=True,
    )
    if completed.stdout:
        report.say(completed.stdout.rstrip())
    if completed.returncode != 0:
        detail = (completed.stderr or "").strip()
        raise InstallError(f"{' '.join(argv)} exited {completed.returncode}: {detail}")
    report.say("open it with: hermes -p shorts-factory chat")
    report.say("alias command is created only by the first install: hermes profile install <repo> --name shorts-factory --alias -y")


def plan_lines(source: Path, hermes_home: Path, method: str) -> list[str]:
    profile = hermes_home / "profiles" / PROFILE_NAME
    lines = [
        f"source: {source}",
        f"HERMES_HOME: {hermes_home}",
        f"profile: {profile}",
        f"method: {method}",
        "primary files that will not be modified: " + ", ".join(PRIMARY_FILES),
        "other profiles under profiles/ will not be modified",
        "no dependency install, no network, no TTS call, no Desktop database write",
    ]
    if method == "hermes":
        if _distribution_name(profile) == PROFILE_NAME:
            lines.append("would run: " + " ".join(hermes_update_argv()))
        else:
            lines.append("would run: " + " ".join(hermes_install_argv(source)))
    else:
        lines.append("would copy: " + ", ".join(OWNED_FILES + OWNED_DIRS))
        lines.append("would write .env.example without secret values")
    conflict = profile_conflict(hermes_home, source)
    if conflict:
        lines.append("REFUSE: " + conflict)
    return lines


def run_install(
    source: Path,
    hermes_home: Path,
    apply: bool,
    method: str,
    force_config: bool,
) -> InstallReport:
    if method not in {"auto", "file", "hermes"}:
        raise InstallError(f"unknown method {method}")
    chosen = method
    if method == "auto":
        chosen = "hermes" if _hermes_available() else "file"
    report = InstallReport("apply" if apply else "dry-run", chosen, hermes_home / "profiles" / PROFILE_NAME)
    for line in plan_lines(source, hermes_home, chosen):
        report.say(line)
    conflict = profile_conflict(hermes_home, source)
    if conflict:
        report.refused = True
        report.say("refused before any write")
        return report
    if not apply:
        report.say("dry-run only; no files written")
        return report
    if chosen == "hermes":
        apply_hermes_cli(source, hermes_home, report, force_config)
        return report
    apply_file_layout(source, hermes_home, force_config, report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Install the shorts-factory Hermes profile")
    parser.add_argument("--apply", action="store_true", help="write the profile; omit for dry-run")
    parser.add_argument("--dry-run", action="store_true", help="explicit dry-run (default)")
    parser.add_argument("--method", choices=("auto", "file", "hermes"), default="auto")
    parser.add_argument("--hermes-home", type=Path, default=None)
    parser.add_argument("--source", type=Path, default=None)
    parser.add_argument("--force-config", action="store_true")
    args = parser.parse_args(argv)
    if args.apply and args.dry_run:
        print("pass only one of --apply and --dry-run")
        return 2
    try:
        report = run_install(
            source=(args.source or repo_root()).resolve(),
            hermes_home=(args.hermes_home or default_hermes_home()).resolve(),
            apply=args.apply,
            method=args.method,
            force_config=args.force_config,
        )
    except InstallError as exc:
        print(f"install refused: {exc}")
        return 2
    print("\n".join(report.lines))
    return 2 if report.refused else 0


if __name__ == "__main__":
    raise SystemExit(main())
