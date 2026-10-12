"""Restic-backed test checkpoints ONLY for GitHub-hosted synthetic CI.

No production adapter, no remote backends, no retention/prune, no generic path
inputs and no Docker mutation. The fixture is prepared consistently by the
existing synthetic-only SQLite snapshot helper before Restic sees any bytes.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from fixture_backup import restore_fixture, verify_checkpoint

SNAPSHOT_ID = re.compile(r"^[a-f0-9]{64}$")
TEST_MARKER = "MSC_RESTIC_SYNTHETIC_CI_V1"
ALLOWED_COMMANDS = frozenset({"init", "backup", "snapshots", "check", "restore"})


class ResticFixtureError(RuntimeError):
    """Safe error; never contains raw restic output, credentials or state names."""


@dataclass(frozen=True)
class SnapshotEvidence:
    snapshot_id: str
    repository_checked: bool
    restore_tested: bool


class ResticFixture:
    """Scoped to a newly created, marker-verified synthetic runner directory."""

    def __init__(self, sandbox: Path, restic: str | None = None):
        sandbox = Path(sandbox)
        marker = sandbox / ".msc-restic-ci-only"
        if (not sandbox.is_dir() or sandbox.is_symlink()
                or not marker.is_file() or marker.is_symlink()
                or marker.read_text(encoding="ascii").strip() != TEST_MARKER):
            raise ResticFixtureError("REFUSED: synthetic Restic sandbox marker missing")
        if restic is None:
            restic = shutil.which("restic")
        if not restic or not Path(restic).is_file():
            raise ResticFixtureError("REFUSED: restic executable unavailable")
        self.binary = str(Path(restic).resolve())
        self.sandbox = sandbox.resolve()
        self.repo = self.sandbox / "restic-repository"
        self.password = self.sandbox / "synthetic-password"
        self.tmp = self.sandbox / "restic-tmp"
        self.home = self.sandbox / "restic-home"

    def _inside(self, path: Path, *, expected: str | None = None) -> Path:
        path = Path(path)
        if not path.is_absolute() or path.is_symlink():
            raise ResticFixtureError("REFUSED: non-absolute or symlinked fixture path")
        if path.resolve() == self.sandbox or not path.resolve().is_relative_to(self.sandbox):
            raise ResticFixtureError("REFUSED: path outside disposable sandbox")
        if expected is not None and path.name != expected:
            raise ResticFixtureError("REFUSED: unexpected synthetic fixture path")
        return path

    def _call(self, args: list[str], *, password_override: Path | None = None) -> str:
        if not args or args[0] not in ALLOWED_COMMANDS:
            raise ResticFixtureError("REFUSED: unsupported Restic operation")
        if not self.repo.is_relative_to(self.sandbox):
            raise ResticFixtureError("REFUSED: repository location invalid")
        self.tmp.mkdir(exist_ok=True)
        self.home.mkdir(exist_ok=True)
        # No inherited RESTIC/cloud credentials or custom backup targets.
        env = {
            "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
            "HOME": str(self.home),
            "TMPDIR": str(self.tmp),
            "LANG": "C",
        }
        password = password_override or self.password
        if not password.is_file() or password.is_symlink():
            raise ResticFixtureError("REFUSED: fixture password file absent")
        cli = [self.binary, "--no-cache", "--repo", str(self.repo),
               "--password-file", str(password)] + args
        try:
            proc = subprocess.run(cli, env=env, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True, timeout=160,
                                  check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ResticFixtureError("fixture Restic invocation failed") from exc
        if proc.returncode != 0:
            raise ResticFixtureError("fixture Restic operation refused or failed")
        return proc.stdout

    def initialize(self) -> None:
        if self.repo.exists() or self.password.exists():
            raise ResticFixtureError("REFUSED: Restic test repository already exists")
        self.password.write_text(secrets.token_hex(32), encoding="ascii")
        self.password.chmod(0o600)
        self._call(["init"])
        if not (self.repo / "config").is_file():
            raise ResticFixtureError("Restic initialization did not create a repository")

    def capture(self, staged_checkpoint: Path) -> str:
        checkpoint = self._inside(staged_checkpoint, expected="source-checkpoint")
        if not checkpoint.is_dir() or checkpoint.is_symlink():
            raise ResticFixtureError("REFUSED: source checkpoint missing")
        verify_checkpoint(checkpoint)
        # Explicit full path, no globs, no excludes, no alternate repositories.
        output = self._call(["backup", "--json", "--tag", "msc-fixture-only",
                             str(checkpoint)])
        snapshots = []
        for line in output.splitlines():
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                raise ResticFixtureError("malformed JSON in fixture backup response")
            if isinstance(value, dict) and value.get("message_type") == "summary":
                snapshots.append(value.get("snapshot_id"))
        if len(snapshots) != 1 or not isinstance(snapshots[0], str) or not SNAPSHOT_ID.fullmatch(snapshots[0]):
            raise ResticFixtureError("missing immutable Restic snapshot identity")
        identifier = snapshots[0]
        self.check_snapshot(identifier, staged_checkpoint=checkpoint)
        return identifier

    def check_snapshot(self, identifier: str, *, staged_checkpoint: Path) -> None:
        if not SNAPSHOT_ID.fullmatch(identifier):
            raise ResticFixtureError("REFUSED: invalid immutable Restic snapshot identity")
        cp = self._inside(staged_checkpoint, expected="source-checkpoint")
        raw = self._call(["snapshots", "--json"])
        try:
            snapshots = json.loads(raw)
        except json.JSONDecodeError:
            raise ResticFixtureError("invalid Restic snapshot inventory")
        if not isinstance(snapshots, list):
            raise ResticFixtureError("Restic snapshot inventory malformed")
        candidates = [x for x in snapshots
                      if isinstance(x, dict) and x.get("id") == identifier
                      and x.get("paths") == [str(cp)]
                      and "msc-fixture-only" in x.get("tags", [])]
        if len(candidates) != 1:
            raise ResticFixtureError("missing exact scoped Restic checkpoint")
        self._call(["check", "--read-data"])

    def restore_and_verify(self, identifier: str, *, staged_checkpoint: Path,
                           restored_state: Path) -> SnapshotEvidence:
        checkpoint = self._inside(staged_checkpoint, expected="source-checkpoint")
        destination = self._inside(restored_state, expected="restic-restored")
        if destination.exists() or destination.is_symlink():
            raise ResticFixtureError("REFUSED: restore destination already exists")
        self.check_snapshot(identifier, staged_checkpoint=checkpoint)
        raw_restore = self.sandbox / "restic-restore-tree"
        if raw_restore.exists() or raw_restore.is_symlink():
            raise ResticFixtureError("REFUSED: raw restore staging already exists")
        self._call(["restore", identifier, "--target", str(raw_restore)])
        recovered = raw_restore / checkpoint.relative_to("/")
        if not recovered.is_dir() or recovered.is_symlink():
            raise ResticFixtureError("scoped snapshot content not restored")
        expected = verify_checkpoint(checkpoint)
        actual = verify_checkpoint(recovered)
        if expected != actual:
            raise ResticFixtureError("Restic restored snapshot differs")
        if restore_fixture(recovered, destination) != expected:
            raise ResticFixtureError("Restic restored application state differs")
        return SnapshotEvidence(identifier, repository_checked=True, restore_tested=True)

    def reject_incorrect_password(self) -> None:
        incorrect = self.sandbox / "wrong-fixture-password"
        if incorrect.exists():
            raise ResticFixtureError("REFUSED: wrong-password test path already exists")
        incorrect.write_text(secrets.token_hex(32), encoding="ascii")
        incorrect.chmod(0o600)
        try:
            try:
                self._call(["snapshots", "--json"], password_override=incorrect)
            except ResticFixtureError:
                return
            raise ResticFixtureError("REFUSED: wrong-password repository access unexpectedly succeeded")
        finally:
            incorrect.unlink(missing_ok=True)
