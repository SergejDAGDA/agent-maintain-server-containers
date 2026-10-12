"""Synthetic CI-only read-side observer for the PostgreSQL Restic fixture.

This object is constructed and registered only by reviewed integration code.
No policy-selected imports, arbitrary targets, capture, restore, deletion
or shell execution are available on this class. The underlying ResticFixture
is already limited to runner-owned local data and approved CLI commands.
"""
from __future__ import annotations

from pathlib import Path

from pg_restic_fixture import PgResticFixture


class SyntheticPgReadOnlyInspector:
    def __init__(
        self, provider: PgResticFixture, *, snapshot_id: str,
        package: Path, repository_id: str,
    ):
        self._provider = provider
        self._sid = snapshot_id
        self._package = package
        self._repository_id = repository_id

    def inspect_repository(self) -> dict:
        self._provider.check_pg(self._sid, package=self._package)
        return {
            "repository_id": self._repository_id,
            "repository_accessible": True,
            "key_retrievable": self._provider.password.is_file(),
        }

    def lookup_snapshot_exact(self, immutable_snapshot_id: str) -> dict:
        if immutable_snapshot_id != self._sid:
            raise RuntimeError("CI read-only exact-snapshot scope mismatch")
        self._provider.check_pg(self._sid, package=self._package)
        return {"snapshot_id": self._sid, "snapshot_exact_match": True}

    def inspect_repository_data(self, immutable_snapshot_id: str) -> dict:
        if immutable_snapshot_id != self._sid:
            raise RuntimeError("CI read-only repository-check scope mismatch")
        self._provider.check_pg(self._sid, package=self._package)
        return {"snapshot_id": self._sid, "repository_data_checked": True}
