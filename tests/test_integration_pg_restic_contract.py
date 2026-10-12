"""Offline exact-snapshot refusal tests for synthetic PostgreSQL Restic fixture.

Mocked Restic calls only. Never Docker, network, real credentials or backups.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

FIXTURES = Path(__file__).resolve().parent / "integration"
sys.path.insert(0, str(FIXTURES))
from pg_group_harness import COMPOSE, FORMAT, IMAGE, MEMBERS, _sha_file, verify_package  # noqa: E402
from pg_restic_fixture import PgResticFixture, TAG  # noqa: E402
from restic_fixture import ResticFixtureError, TEST_MARKER, ALLOWED_COMMANDS  # noqa: E402

SID = "a" * 64


class PgResticOfflineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="msc-pg-restic-offline-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / ".msc-restic-ci-only").write_text(TEST_MARKER + "\n", encoding="ascii")
        self.provider = PgResticFixture(self.root, restic=sys.executable)
        self.package = self.root / "pg-recovery-set"
        self.package.mkdir()
        assets = self.package / "assets"
        assets.mkdir()
        self.seed = {"identity": "a" * 24, "files": {}}
        for marker in ("a", "b", "c"):
            name = "asset-" + marker * 12 + ".bin"
            payload = ("synthetic:" + name).encode("ascii")
            (assets / name).write_bytes(payload)
            self.seed["files"][name] = hashlib.sha256(payload).hexdigest()
        dump = b"PGDMP synthetic offline contract only"
        (self.package / "pg.dump").write_bytes(dump)
        (self.package / "manifest.json").write_text(json.dumps({
            "format": FORMAT, "members": list(MEMBERS),
            "image": IMAGE, "source_digest": _sha_file(COMPOSE),
            "identity": self.seed["identity"], "files": self.seed["files"],
            "pg_dump_sha256": hashlib.sha256(dump).hexdigest(),
        }), encoding="utf-8")
        self.verify = lambda package: verify_package(package, expected=self.seed)

    def _record(self, **changes):
        value = {"id": SID, "paths": [str(self.package)], "tags": [TAG]}
        value.update(changes)
        return json.dumps([value])

    def test_full_exact_snapshot_roundtrip_mock(self):
        def fake_call(args):
            if args[0] == "backup":
                return json.dumps({"message_type": "summary", "snapshot_id": SID})
            if args[0] == "snapshots":
                return self._record()
            if args[0] == "check":
                self.assertEqual(args, ["check", "--read-data"])
                return ""
            if args[0] == "restore":
                source = self.package
                target = Path(args[args.index("--target") + 1])
                shutil.copytree(source, target / source.relative_to("/"))
                return ""
            raise AssertionError("unexpected Restic operation")

        with mock.patch.object(self.provider, "_call", side_effect=fake_call) as called:
            self.assertEqual(self.provider.capture_pg(self.package, validate=self.verify), SID)
            recovered = self.provider.restore_pg(SID, package=self.package, validate=self.verify)
        self.assertNotEqual(recovered, self.package)
        self.assertEqual(self.verify(recovered), self.seed)
        self.assertEqual(self.verify(self.package), self.seed)
        cmds = [call.args[0][0] for call in called.call_args_list]
        self.assertEqual(cmds, ["backup", "snapshots", "check", "snapshots", "check", "restore"])

    def test_refuse_short_or_moving_snapshot_id(self):
        with mock.patch.object(self.provider, "_call") as runner:
            for sid in ("latest", "abc123", "f" * 63, "g" * 64, None):
                with self.subTest(sid=sid):
                    with self.assertRaises(ResticFixtureError):
                        self.provider.check_pg(sid, package=self.package)
        runner.assert_not_called()

    def test_snapshot_requires_matching_source_and_tag(self):
        for values in ({"paths": ["/foreign/pg-recovery-set"]}, {"tags": ["not-pg"]},
                       {"id": "b" * 64}, {"tags": None}):
            with self.subTest(values=values):
                with mock.patch.object(self.provider, "_call", return_value=self._record(**values)) as calls:
                    with self.assertRaises(ResticFixtureError):
                        self.provider.check_pg(SID, package=self.package)
                self.assertEqual(calls.call_count, 1)

    def test_missing_or_corrupt_checkpoint_rejected_before_restic(self):
        (self.package / "assets" / ("asset-" + "a" * 12 + ".bin")).unlink()
        with mock.patch.object(self.provider, "_call") as runner:
            with self.assertRaises(ValueError):
                self.provider.capture_pg(self.package, validate=self.verify)
        runner.assert_not_called()

    def test_foreign_checkpoint_refused(self):
        with tempfile.TemporaryDirectory() as outside:
            with mock.patch.object(self.provider, "_call") as runner:
                with self.assertRaises(ResticFixtureError):
                    self.provider.capture_pg(Path(outside) / "pg-recovery-set", validate=self.verify)
            runner.assert_not_called()

    def test_corrupt_restored_package_fails_without_application_restoration(self):
        def fake_call(args):
            if args[0] == "snapshots":
                return self._record()
            if args[0] == "check":
                return ""
            if args[0] == "restore":
                src = self.package
                target = Path(args[args.index("--target") + 1])
                shutil.copytree(src, target / src.relative_to("/"))
                (target / src.relative_to("/") / "pg.dump").write_bytes(b"corrupt")
                return ""
            raise AssertionError("unexpected")
        with mock.patch.object(self.provider, "_call", side_effect=fake_call):
            with self.assertRaises(ValueError):
                self.provider.restore_pg(SID, package=self.package, validate=self.verify)
        self.assertEqual(self.verify(self.package), self.seed)

    def test_second_restore_target_refused(self):
        (self.root / "pg-restic-restore-tree").mkdir()
        with mock.patch.object(self.provider, "_call", side_effect=[
            self._record(), "", "SHOULD NOT BE CALLED",
        ]) as runner:
            with self.assertRaisesRegex(ResticFixtureError, "already exists"):
                self.provider.restore_pg(SID, package=self.package, validate=self.verify)
        self.assertEqual(runner.call_count, 2)

    def test_malformed_json_and_backup_id_do_not_pass(self):
        for text in ("not-json", json.dumps({"message_type": "summary", "snapshot_id": "latest"}), ""):
            with self.subTest(text=text):
                with mock.patch.object(self.provider, "_call", return_value=text) as runner:
                    with self.assertRaises(ResticFixtureError):
                        self.provider.capture_pg(self.package, validate=self.verify)
                runner.assert_called_once()

    def test_no_destructive_restic_commands_allowed(self):
        for op in ("forget", "prune", "rm", "unlock", "repair"):
            self.assertNotIn(op, ALLOWED_COMMANDS)
        self.assertFalse(hasattr(self.provider, "prune"))
        self.assertFalse(hasattr(self.provider, "delete_snapshot"))


if __name__ == "__main__":
    unittest.main()
