"""PostgreSQL recovery-set Restic exercise for ephemeral synthetic CI ONLY.

Reuses the existing ResticFixture allowlisted runner and encrypted local
repository. No production provider, no network backends, no deletion, no
Docker mutation. The caller supplies the module's reviewed package validator,
never a path or callable from external policy.
"""
from __future__ import annotations

import json
from pathlib import Path

from restic_fixture import (
    ResticFixture, ResticFixtureError, SNAPSHOT_ID,
)

TAG = "msc-pg-fixture-only"


class PgResticFixture(ResticFixture):
    """Bound to exactly one fully validated synthetic PostgreSQL group package."""

    def capture_pg(self, package: Path, *, validate) -> str:
        source = self._inside(package, expected="pg-recovery-set")
        if not source.is_dir() or source.is_symlink():
            raise ResticFixtureError("REFUSED: PostgreSQL synthetic package missing")
        validate(source)
        output = self._call(["backup", "--json", "--tag", TAG, str(source)])
        summaries = []
        for line in output.splitlines():
            try:
                entry = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ResticFixtureError("invalid synthetic Restic backup JSON") from exc
            if isinstance(entry, dict) and entry.get("message_type") == "summary":
                summaries.append(entry.get("snapshot_id"))
        if (len(summaries) != 1 or not isinstance(summaries[0], str)
                or not SNAPSHOT_ID.fullmatch(summaries[0])):
            raise ResticFixtureError("missing immutable PostgreSQL Restic snapshot ID")
        sid = summaries[0]
        self.check_pg(sid, package=source)
        return sid

    def check_pg(self, sid: str, *, package: Path) -> None:
        if not isinstance(sid, str) or not SNAPSHOT_ID.fullmatch(sid):
            raise ResticFixtureError("REFUSED: invalid immutable PostgreSQL snapshot ID")
        source = self._inside(package, expected="pg-recovery-set")
        if not source.is_dir() or source.is_symlink():
            raise ResticFixtureError("REFUSED: synthetic checkpoint missing")
        try:
            inventory = json.loads(self._call(["snapshots", "--json"]))
        except json.JSONDecodeError as exc:
            raise ResticFixtureError("invalid synthetic snapshot inventory") from exc
        if not isinstance(inventory, list):
            raise ResticFixtureError("invalid synthetic snapshot inventory")
        matched = [
            entry for entry in inventory
            if isinstance(entry, dict) and entry.get("id") == sid
            and entry.get("paths") == [str(source)]
            and isinstance(entry.get("tags"), list) and TAG in entry["tags"]
        ]
        if len(matched) != 1:
            raise ResticFixtureError("REFUSED: exact PostgreSQL snapshot not found")
        self._call(["check", "--read-data"])

    def restore_pg(self, sid: str, *, package: Path, validate) -> Path:
        """Restore from encrypted repository into new, independent staging only.

        Returns a validated *package path*, not a started application or a
        RESTORE_TESTED assertion. The caller must run isolated Compose smoke.
        """
        source = self._inside(package, expected="pg-recovery-set")
        self.check_pg(sid, package=source)
        target = self._inside(self.sandbox / "pg-restic-restore-tree",
                              expected="pg-restic-restore-tree")
        if target.exists() or target.is_symlink():
            raise ResticFixtureError("REFUSED: PostgreSQL restore target already exists")
        self._call(["restore", sid, "--target", str(target)])
        recovered = target / source.relative_to("/")
        if (not recovered.is_dir() or recovered.is_symlink()
                or not recovered.resolve().is_relative_to(target.resolve())):
            raise ResticFixtureError("REFUSED: restored PostgreSQL set invalid")
        validate(recovered)
        return recovered
