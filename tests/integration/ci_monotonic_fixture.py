"""Synthetic test-only fixture bootstrap, NEVER a production initializer.

The private test harness creates a new disposable SQLite file and explicitly
constructs the first version, to evaluate the narrow contract in isolation.
Re-bootstrap after state loss is NOT trusted recovery and must not be used by
a runtime or deployment service.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from monotonic_head_contract import _chain_hash, GENESIS_PREVIOUS


def bootstrap_test_only(
    connection: sqlite3.Connection, *, ledger_id: str,
    store_id: str, genesis_anchor: str,
) -> None:
    if connection.in_transaction:
        raise RuntimeError("synthetic bootstrap refused active transaction")
    databases = connection.execute("PRAGMA database_list").fetchall()
    targets = [row[2] for row in databases if row[1] == "main"]
    if (len(targets) != 1 or not targets[0]
            or not Path(targets[0]).is_file()
            or Path(targets[0]).is_symlink()):
        raise RuntimeError("synthetic bootstrap refused nonpersistent file")
    existing = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    if existing:
        raise RuntimeError("synthetic bootstrap refused existing tables")
    # Always commit metadata and genesis history together in a single
    # transaction on an empty temporary test file.
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            "CREATE TABLE synthetic_anchor_store "
            "(store_id TEXT PRIMARY KEY, ledger_id TEXT NOT NULL, "
            "revision INTEGER NOT NULL, anchor_id TEXT NOT NULL)"
        )
        connection.execute(
            "CREATE TABLE synthetic_anchor_history "
            "(revision INTEGER PRIMARY KEY, previous_anchor TEXT NOT NULL, "
            "anchor_id TEXT NOT NULL UNIQUE, chain_digest TEXT NOT NULL)"
        )
        digest = _chain_hash(
            ledger_id, store_id, 0, GENESIS_PREVIOUS,
            genesis_anchor, GENESIS_PREVIOUS,
        )
        connection.execute(
            "INSERT INTO synthetic_anchor_history "
            "(revision,previous_anchor,anchor_id,chain_digest) VALUES (0,?,?,?)",
            (GENESIS_PREVIOUS, genesis_anchor, digest),
        )
        connection.execute(
            "INSERT INTO synthetic_anchor_store "
            "(store_id,ledger_id,revision,anchor_id) VALUES (?,?,0,?)",
            (store_id, ledger_id, genesis_anchor),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
