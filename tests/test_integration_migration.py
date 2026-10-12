"""Synthetic migration fault regressions; no Docker, Restic or live systems."""
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

FIXTURE = Path(__file__).resolve().parent / "integration"
sys.path.insert(0, str(FIXTURE))
from fixture_app import DB_NAME, verify_state  # noqa: E402
from fixture_backup import capture_fixture, restore_fixture, seed_fixture  # noqa: E402
from fixture_migration import (  # noqa: E402
    SyntheticMigrationInterrupted, migrate_v2_then_interrupt, verify_v2,
)
from restic_fixture import TEST_MARKER  # noqa: E402


class SyntheticMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="msc-unit-v2-")
        self.sandbox = Path(self.temp.name)
        (self.sandbox / ".msc-restic-ci-only").write_text(TEST_MARKER + "\n", encoding="ascii")
        self.root = self.sandbox / "original"
        self.seed = seed_fixture(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_interrupted_migration_preserves_pre_migration_restorability(self):
        old = self.sandbox / "checkpoint"
        separate = self.sandbox / "separate"
        self.assertEqual(capture_fixture(self.root, old), self.seed)
        with self.assertRaises(SyntheticMigrationInterrupted):
            migrate_v2_then_interrupt(self.root)
        self.assertEqual(verify_v2(self.root, expected=self.seed), "v2")
        with self.assertRaises(sqlite3.OperationalError):
            verify_state(self.root)
        self.assertEqual(restore_fixture(old, separate), self.seed)
        self.assertEqual(verify_state(separate), self.seed)

    def test_migration_cannot_run_against_unmarked_state(self):
        (self.sandbox / ".msc-restic-ci-only").unlink()
        with self.assertRaises(ValueError):
            migrate_v2_then_interrupt(self.root)
        self.assertEqual(verify_state(self.root), self.seed)

    def test_repeat_migration_fails_closed_without_second_change(self):
        with self.assertRaises(SyntheticMigrationInterrupted):
            migrate_v2_then_interrupt(self.root)
        with self.assertRaises((ValueError, sqlite3.OperationalError)):
            migrate_v2_then_interrupt(self.root)
        self.assertEqual(verify_v2(self.root, expected=self.seed), "v2")

    def test_wrong_directory_is_rejected_before_mutation(self):
        other = self.sandbox / "not-original"
        seed_fixture(other)
        with self.assertRaises(ValueError):
            migrate_v2_then_interrupt(other)
        self.assertEqual(verify_state(other)["attachments"], 3)


if __name__ == "__main__":
    unittest.main()
