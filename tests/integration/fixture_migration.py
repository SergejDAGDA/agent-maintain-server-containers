"""Deliberately incompatible SQLite v1 -> v2 migration, synthetic CI ONLY.

No external data, deployment, Docker mutation, or automatic restoration.
The simulated process crash occurs strictly AFTER its transaction commits.
"""
from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

from fixture_app import DB_NAME, SENTINEL, verify_state
from restic_fixture import TEST_MARKER


class SyntheticMigrationInterrupted(RuntimeError):
    """Expected bounded fault injection, no underlying state values."""


def _approved(root: Path) -> Path:
    root = Path(root)
    marker = root.parent / ".msc-restic-ci-only"
    if (not root.is_absolute() or root.is_symlink() or root.name != "original"
            or not root.is_dir() or not marker.is_file() or marker.is_symlink()
            or marker.read_text(encoding="ascii").strip() != TEST_MARKER
            or (root / "SYNTHETIC_ONLY").read_text(encoding="utf-8").strip() != SENTINEL
            or (root / DB_NAME).is_symlink()):
        raise ValueError("REFUSED: not a uniquely owned synthetic CI database")
    return root


def migrate_v2_then_interrupt(root: Path) -> None:
    """Commit a schema that the v1 application cannot read, then fail."""
    root = _approved(root)
    verify_state(root)
    with sqlite3.connect(root / DB_NAME, timeout=5) as con:
        if con.execute("PRAGMA user_version").fetchone() != (0,):
            raise ValueError("REFUSED: synthetic baseline schema not v1")
        con.execute("ALTER TABLE attachment RENAME TO document_blob")
        con.execute("ALTER TABLE document_blob RENAME COLUMN digest TO checksum")
        con.execute("PRAGMA user_version = 2")
    # Intentionally *after* successful commit, emulating a later upgrade crash.
    raise SyntheticMigrationInterrupted("synthetic failure after committed migration")


def verify_v2(root: Path, *, expected: dict) -> str:
    """Read-only independent check of v2 rows, files, and unchanged identity."""
    root = _approved(root)
    with sqlite3.connect((root / DB_NAME).as_uri() + "?mode=ro", uri=True) as con:
        con.execute("PRAGMA query_only=ON")
        if con.execute("PRAGMA quick_check").fetchone() != ("ok",):
            raise ValueError("synthetic migrated database is corrupt")
        if con.execute("PRAGMA user_version").fetchone() != (2,):
            raise ValueError("synthetic migration revision missing")
        if con.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='attachment'").fetchone() != (0,):
            raise ValueError("obsolete v1 attachment table remains")
        identity = con.execute("SELECT identifier FROM fixture_identity").fetchone()[0]
        rows = con.execute("SELECT name, checksum FROM document_blob ORDER BY name").fetchall()
    if identity != expected["identifier"] or len(rows) != expected["attachments"]:
        raise ValueError("migrated synthetic identity mismatch")
    for name, checksum in rows:
        path = root / "attachments" / name
        if (not path.is_file() or path.is_symlink()
                or hashlib.sha256(path.read_bytes()).hexdigest() != checksum):
            raise ValueError("migrated synthetic files inconsistent")
    return "v2"
