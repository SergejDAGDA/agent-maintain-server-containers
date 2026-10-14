"""Synthetic fixture health/smoke verification; no external services or real data.

Can run from the host for unit tests or within a read-only Compose service.
"""
from __future__ import annotations

from contextlib import closing

import argparse
import hashlib
import re
import sqlite3
import time
from pathlib import Path

ATTACHMENT = re.compile(r"^fixture-[a-f0-9]{12}\.bin$")
DB_NAME = "data.sqlite"
SENTINEL = "MSC_DISPOSABLE_FIXTURE_V1"


def verify_state(root: Path) -> dict[str, str | int]:
    """Check SQLite integrity and references to artificial attachment payloads."""
    root = Path(root)
    if (root / "SYNTHETIC_ONLY").read_text(encoding="utf-8").strip() != SENTINEL:
        raise ValueError("synthetic fixture marker missing or invalid")
    db = root / DB_NAME
    if not db.is_file():
        raise ValueError("fixture database missing")
    # Opening readonly prevents a healthcheck from mutating the DB state.
    with closing(sqlite3.connect(db.as_uri() + "?mode=ro", uri=True, timeout=2)) as con:
        con.execute("PRAGMA query_only=ON")
        if con.execute("PRAGMA quick_check").fetchone() != ("ok",):
            raise ValueError("SQLite integrity check failed")
        markers = con.execute("SELECT identifier FROM fixture_identity").fetchall()
        if len(markers) != 1 or not re.fullmatch(r"[a-f0-9]{24}", markers[0][0]):
            raise ValueError("synthetic fixture identity missing")
        rows = con.execute("SELECT name, digest FROM attachment ORDER BY name").fetchall()
    if len(rows) != 3:
        raise ValueError("synthetic attachment inventory incomplete")
    for name, digest in rows:
        if not isinstance(name, str) or not ATTACHMENT.fullmatch(name):
            raise ValueError("unsafe or invalid synthetic attachment reference")
        path = root / "attachments" / name
        if not path.is_file():
            raise ValueError("synthetic attachment missing")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != digest:
            raise ValueError("synthetic attachment integrity mismatch")
    return {"identifier": markers[0][0], "attachments": len(rows)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--state", type=Path, default=Path("/state"))
    args = parser.parse_args()
    if args.check == args.serve:
        parser.error("choose exactly one of --check or --serve")
    verify_state(args.state)
    if args.check:
        print("SYNTHETIC_SMOKE_PASS", flush=True)
        return 0
    # Compose healthcheck executes the same read-only application-level smoke.
    while True:
        time.sleep(60)


if __name__ == "__main__":
    raise SystemExit(main())
