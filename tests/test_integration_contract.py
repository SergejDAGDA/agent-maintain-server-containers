"""Local unit tests of synthetic-only fixture semantics; never call Docker."""
from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent / "integration"
sys.path.insert(0, str(FIXTURES))
from fixture_app import verify_state  # noqa: E402
from fixture_backup import (  # noqa: E402
    capture_fixture,
    restore_fixture,
    seed_fixture,
    verify_checkpoint,
)


class SyntheticRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="msc-synthetic-unit-")
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_complete_roundtrip(self):
        original = self.root / "original"
        checkpoint = self.root / "cp"
        restored = self.root / "restored"
        seed = seed_fixture(original)
        self.assertEqual(capture_fixture(original, checkpoint), seed)
        self.assertEqual(restore_fixture(checkpoint, restored), seed)
        self.assertEqual(verify_state(original), verify_state(restored))

    def test_corrupt_attachment_checkpoint_is_rejected_before_restore(self):
        original = self.root / "original"
        checkpoint = self.root / "cp"
        seed_fixture(original)
        capture_fixture(original, checkpoint)
        target = sorted((checkpoint / "attachments").iterdir())[0]
        target.write_bytes(b"synthetic corruption")
        dest = self.root / "dest"
        with self.assertRaises(ValueError):
            restore_fixture(checkpoint, dest)
        self.assertFalse(dest.exists())

    def test_missing_db_is_rejected(self):
        original = self.root / "original"
        seed_fixture(original)
        (original / "data.sqlite").unlink()
        with self.assertRaises(ValueError):
            capture_fixture(original, self.root / "cp")

    def test_no_overwrite_existing_state_or_checkpoint(self):
        original = self.root / "original"
        cp = self.root / "cp"
        seed_fixture(original)
        with self.assertRaises(ValueError):
            seed_fixture(original)
        capture_fixture(original, cp)
        with self.assertRaises(ValueError):
            capture_fixture(original, cp)
        already = self.root / "existing"
        already.mkdir()
        (already / "user-file").write_text("do not remove", encoding="utf-8")
        with self.assertRaises(ValueError):
            restore_fixture(cp, already)
        self.assertTrue((already / "user-file").exists())

    def test_unmarked_data_cannot_be_backed_up(self):
        original = self.root / "arbitrary-state"
        original.mkdir()
        (original / "data.sqlite").write_bytes(b"arbitrary bytes")
        with self.assertRaises((ValueError, OSError)):
            capture_fixture(original, self.root / "cp")
        self.assertFalse((self.root / "cp").exists())

    def test_known_good_is_preserved_when_second_snapshot_corrupts(self):
        state = self.root / "original"
        seed = seed_fixture(state)
        first = self.root / "good"
        second = self.root / "bad"
        capture_fixture(state, first)
        capture_fixture(state, second)
        (second / "data.sqlite").write_bytes(b"SYNTHETIC_BROKEN_DATABASE")
        with self.assertRaises(ValueError):
            verify_checkpoint(second)
        self.assertEqual(verify_checkpoint(first), seed)

    def test_no_unexpected_attachment_paths(self):
        state = self.root / "original"
        seed_fixture(state)
        (state / "attachments" / "untracked.txt").write_bytes(b"x")
        with self.assertRaises(ValueError):
            capture_fixture(state, self.root / "cp")

    def test_restore_rejects_malformed_manifest(self):
        original = self.root / "original"
        checkpoint = self.root / "cp"
        seed_fixture(original)
        capture_fixture(original, checkpoint)
        (checkpoint / "checkpoint.json").write_text('{"format": "bad", "files": {}}')
        with self.assertRaises(ValueError):
            restore_fixture(checkpoint, self.root / "target")

    def test_clone_checkpoint_does_not_change_source(self):
        original = self.root / "original"
        checkpoint = self.root / "cp"
        seed = seed_fixture(original)
        capture_fixture(original, checkpoint)
        target = self.root / "copy"
        restore_fixture(checkpoint, target)
        shutil.rmtree(target)
        self.assertEqual(verify_checkpoint(checkpoint), seed)


if __name__ == "__main__":
    unittest.main()
