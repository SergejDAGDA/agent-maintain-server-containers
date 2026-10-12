"""Disposable synthetic backup/restore fixture — NOT a production backup engine.

Only marked, generated test data with fixed artifact names can enter a checkpoint.
Database capture uses sqlite3.Connection.backup (rather than copying a live WAL).
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import sqlite3
import tempfile
from pathlib import Path

from fixture_app import ATTACHMENT, DB_NAME, SENTINEL, verify_state

MARKER_FILE = "SYNTHETIC_ONLY"
MANIFEST_FILE = "checkpoint.json"
MARKER = "msc-test-checkpoint-v1"


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _paths(root: Path) -> list[str]:
    """Require exactly the synthetic files, never recurse through arbitrary data."""
    folder = root / "attachments"
    if not folder.is_dir() or folder.is_symlink():
        raise ValueError("fixture attachments directory invalid")
    attachments = sorted(folder.iterdir())
    if len(attachments) != 3 or any(
        not f.is_file() or f.is_symlink() or not ATTACHMENT.fullmatch(f.name)
        for f in attachments
    ):
        raise ValueError("fixture attachment inventory invalid")
    return [DB_NAME, MARKER_FILE] + ["attachments/" + f.name for f in attachments]


def seed_fixture(root: Path) -> dict:
    """Create synthetic-only DB and linked files in a brand-new folder."""
    root = Path(root)
    if root.exists():
        raise ValueError("fixture seed destination must not exist")
    root.mkdir(parents=True, mode=0o755)
    (root / "attachments").mkdir(mode=0o755)
    (root / MARKER_FILE).write_text(SENTINEL + "\n", encoding="utf-8")
    identity = secrets.token_hex(12)
    files = []
    for _ in range(3):
        filename = "fixture-" + secrets.token_hex(6) + ".bin"
        payload = ("synthetic:" + identity + ":" + filename).encode()
        (root / "attachments" / filename).write_bytes(payload)
        files.append((filename, hashlib.sha256(payload).hexdigest()))
    db = root / DB_NAME
    with sqlite3.connect(db) as con:
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("CREATE TABLE fixture_identity (identifier TEXT NOT NULL)")
        con.execute("CREATE TABLE attachment (name TEXT PRIMARY KEY, digest TEXT NOT NULL)")
        con.execute("INSERT INTO fixture_identity VALUES (?)", (identity,))
        con.executemany("INSERT INTO attachment VALUES (?, ?)", files)
    result = verify_state(root)
    if result["identifier"] != identity:
        raise ValueError("synthetic seed identity mismatch")
    return result


def verify_checkpoint(checkpoint: Path) -> dict:
    checkpoint = Path(checkpoint)
    if not checkpoint.is_dir() or checkpoint.is_symlink():
        raise ValueError("checkpoint missing")
    manifest_file = checkpoint / MANIFEST_FILE
    if not manifest_file.is_file() or manifest_file.is_symlink():
        raise ValueError("checkpoint manifest missing")
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    expected = _paths(checkpoint)
    if (manifest.get("format") != MARKER
            or manifest.get("files") is None
            or set(manifest["files"]) != set(expected)
            or not isinstance(manifest["files"], dict)):
        raise ValueError("invalid checkpoint inventory")
    for relative in expected:
        source = checkpoint / relative
        if source.is_symlink() or not source.is_file() or _digest(source) != manifest["files"][relative]:
            raise ValueError("checkpoint integrity mismatch")
    status = verify_state(checkpoint)
    if status["identifier"] != manifest.get("fixture_identity"):
        raise ValueError("checkpoint fixture identity mismatch")
    return status


def capture_fixture(state: Path, checkpoint: Path) -> dict:
    state, checkpoint = Path(state), Path(checkpoint)
    before = verify_state(state)
    if checkpoint.exists() or checkpoint.is_symlink():
        raise ValueError("checkpoint destination must be new")
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".msc-capture-", dir=checkpoint.parent))
    try:
        (staging / "attachments").mkdir()
        shutil.copyfile(state / MARKER_FILE, staging / MARKER_FILE)
        # Online-consistent SQLite DB snapshot; never copy only database.sqlite
        # from a live WAL writer. This controlled fixture has no concurrent
        # attachment writers; a generic provider needs a coordinated boundary.
        with sqlite3.connect(state / DB_NAME) as source, sqlite3.connect(staging / DB_NAME) as target:
            source.backup(target)
        for rel in _paths(state)[2:]:
            shutil.copyfile(state / rel, staging / rel)
        after = verify_state(state)
        if before != after:
            raise ValueError("fixture state changed during capture")
        files = {relative: _digest(staging / relative) for relative in _paths(staging)}
        (staging / MANIFEST_FILE).write_text(
            json.dumps({"format": MARKER, "fixture_identity": before["identifier"], "files": files},
                       sort_keys=True) + "\n",
            encoding="utf-8",
        )
        verify_checkpoint(staging)
        os.rename(staging, checkpoint)
        return verify_checkpoint(checkpoint)
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def restore_fixture(checkpoint: Path, destination: Path) -> dict:
    checkpoint, destination = Path(checkpoint), Path(destination)
    expected = verify_checkpoint(checkpoint)
    if destination.exists() or destination.is_symlink():
        raise ValueError("restore destination must be new")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".msc-restore-", dir=destination.parent))
    try:
        (staging / "attachments").mkdir()
        for relative in _paths(checkpoint):
            shutil.copyfile(checkpoint / relative, staging / relative)
        restored = verify_state(staging)
        staging.chmod(0o755)  # readonly fixture service runs as unprivileged nobody
        if restored != expected:
            raise ValueError("restored synthetic state differs")
        os.rename(staging, destination)
        return restored
    finally:
        if staging.exists():
            shutil.rmtree(staging)
