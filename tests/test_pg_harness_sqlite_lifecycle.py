"""CI-only PostgreSQL harness SQLite lifecycle, no Docker or real server."""
from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

INTEGRATION = Path(__file__).resolve().parent / "integration"
sys.path.insert(0, str(INTEGRATION))
from pg_group_harness import _managed_sqlite  # noqa: E402


class PgHarnessSqliteLifecycleTests(unittest.TestCase):
    def test_committed_connection_is_closed_before_sandbox_cleanup(self):
        with tempfile.TemporaryDirectory(prefix="msc-pg-harness-offline-") as temp:
            path = Path(temp) / "state.sqlite"
            with _managed_sqlite(path) as con:
                con.execute("CREATE TABLE marker (value INTEGER NOT NULL)")
                con.execute("INSERT INTO marker VALUES (1)")
            with self.assertRaises(sqlite3.ProgrammingError):
                con.execute("SELECT 1")
            with _managed_sqlite(path) as reader:
                self.assertEqual(reader.execute("SELECT value FROM marker").fetchone(), (1,))

    def test_exception_rolls_back_and_closes(self):
        with tempfile.TemporaryDirectory(prefix="msc-pg-harness-offline-") as temp:
            path = Path(temp) / "state.sqlite"
            with _managed_sqlite(path) as con:
                con.execute("CREATE TABLE marker (value INTEGER NOT NULL)")
            with self.assertRaisesRegex(RuntimeError, "synthetic interrupted"):
                with _managed_sqlite(path) as interrupted:
                    interrupted.execute("INSERT INTO marker VALUES (2)")
                    raise RuntimeError("synthetic interrupted")
            with self.assertRaises(sqlite3.ProgrammingError):
                interrupted.execute("SELECT 1")
            with _managed_sqlite(path) as reader:
                self.assertEqual(reader.execute("SELECT COUNT(*) FROM marker").fetchone(), (0,))


if __name__ == "__main__":
    unittest.main()
