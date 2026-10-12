"""Offline fail-closed tests for the synthetic Restic provider boundary.

No Restic binary, Docker, network or cloud credentials are required.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent / "integration"
sys.path.insert(0, str(ROOT))
from fixture_backup import capture_fixture, seed_fixture, verify_checkpoint  # noqa: E402
from restic_fixture import (  # noqa: E402
    ALLOWED_COMMANDS,
    ResticFixture,
    ResticFixtureError,
    TEST_MARKER,
)


class ResticFixtureContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="msc-restic-offline-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / ".msc-restic-ci-only").write_text(TEST_MARKER + "\n", encoding="ascii")
        self.provider = ResticFixture(self.root, restic=sys.executable)

    def test_unmarked_path_is_refused(self):
        unmarked = self.root / "not-a-real-fixture"
        unmarked.mkdir()
        with self.assertRaises(ResticFixtureError):
            ResticFixture(unmarked, restic=sys.executable)

    def test_path_escape_is_refused(self):
        with self.assertRaisesRegex(ResticFixtureError, "outside"):
            self.provider._inside(self.root.parent / "foreign-state")
        with self.assertRaisesRegex(ResticFixtureError, "outside"):
            self.provider._inside(self.root)

    def test_no_destructive_commands_exposed(self):
        self.assertTrue({"init", "backup", "snapshots", "check", "restore"}.issubset(ALLOWED_COMMANDS))
        for forbidden in ("forget", "prune", "unlock", "repair", "copy", "rm"):
            self.assertNotIn(forbidden, ALLOWED_COMMANDS)
            with self.assertRaisesRegex(ResticFixtureError, "unsupported"):
                self.provider._call([forbidden])

    def test_missing_restic_password_refused(self):
        with self.assertRaisesRegex(ResticFixtureError, "password file absent"):
            self.provider._call(["snapshots", "--json"])

    def test_nonzero_and_unknown_restic_failure_are_denied_without_echo(self):
        self.provider.password.write_text("synthetic-secret-DO-NOT-REPEAT", encoding="ascii")
        self.provider.password.chmod(0o600)
        fake = mock.Mock(returncode=79, stdout="sensitive output", stderr="sensitive stderr")
        with mock.patch("restic_fixture.subprocess.run", return_value=fake):
            with self.assertRaises(ResticFixtureError) as err:
                self.provider._call(["snapshots", "--json"])
        self.assertNotIn("sensitive", str(err.exception))
        self.assertNotIn("DO-NOT-REPEAT", str(err.exception))

    def test_snapshot_id_must_be_full_immutable_hex(self):
        for value in ("latest", "abc123", "0" * 64 + ":/", "--tag", "f" * 63):
            with self.assertRaisesRegex(ResticFixtureError, "invalid immutable"):
                self.provider.check_snapshot(value, staged_checkpoint=self.root / "source-checkpoint")

    def test_capture_refuses_unmarked_files_before_restic(self):
        foreign = self.root / "source-checkpoint"
        foreign.mkdir()
        (foreign / "data.sqlite").write_bytes(b"arbitrary bytes")
        with mock.patch.object(self.provider, "_call") as runner:
            with self.assertRaises((ValueError, OSError, ResticFixtureError)):
                self.provider.capture(foreign)
        runner.assert_not_called()

    def test_capture_refuses_foreign_checkpoint_even_if_valid(self):
        with tempfile.TemporaryDirectory(prefix="msc-foreign-synthetic-") as tmp:
            outside = Path(tmp)
            source = outside / "state"
            seed_fixture(source)
            cp = outside / "source-checkpoint"
            capture_fixture(source, cp)
            with self.assertRaisesRegex(ResticFixtureError, "outside"):
                self.provider.capture(cp)

    def test_missing_key_refusal_does_not_delete_checkpoint(self):
        source = self.root / "source"
        seed_fixture(source)
        checkpoint = self.root / "source-checkpoint"
        initial = capture_fixture(source, checkpoint)
        # Emulate the wrong-password CLI unexpectedly claiming success.
        with mock.patch.object(self.provider, "_call", return_value="[]"):
            with self.assertRaisesRegex(ResticFixtureError, "unexpectedly succeeded"):
                self.provider.reject_incorrect_password()
        self.assertEqual(verify_checkpoint(checkpoint), initial)
        self.assertFalse((self.root / "wrong-fixture-password").exists())

    def test_symlinked_source_is_refused(self):
        source = self.root / "source"
        seed_fixture(source)
        cp = self.root / "source-checkpoint"
        capture_fixture(source, cp)
        link = self.root / "linked-checkpoint"
        link.symlink_to(cp, target_is_directory=True)
        with self.assertRaisesRegex(ResticFixtureError, "symlinked"):
            self.provider._inside(link)


if __name__ == "__main__":
    unittest.main()
