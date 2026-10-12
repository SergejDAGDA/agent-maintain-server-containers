"""Offline synthetic PostgreSQL recovery-package contract tests, no Docker."""
from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent / "integration"
sys.path.insert(0, str(FIXTURES))
from pg_group_harness import (  # noqa: E402
    COMPOSE, FORMAT, IMAGE, MEMBERS, _sha_file, verify_package, restore_files,
)


class PgGroupPackageContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="msc-pg-contract-")
        self.root = Path(self.tmp.name)
        self.package = self.root / "cp"
        self.package.mkdir()
        (self.package / "assets").mkdir()
        self.identity = "a" * 24
        self.name = "asset-" + "a" * 12 + ".bin"
        self.names = [self.name, "asset-" + "b" * 12 + ".bin", "asset-" + "c" * 12 + ".bin"]
        self.files = {}
        for name in self.names:
            body = ("synthetic:" + name).encode("ascii")
            (self.package / "assets" / name).write_bytes(body)
            self.files[name] = hashlib.sha256(body).hexdigest()
        payload = b"PGDMP fake bytes, NOT a real DB dump"
        (self.package / "pg.dump").write_bytes(payload)
        self.record = {
            "format": FORMAT, "members": list(MEMBERS), "image": IMAGE,
            "source_digest": _sha_file(COMPOSE), "identity": self.identity,
            "files": dict(self.files),
            "pg_dump_sha256": hashlib.sha256(payload).hexdigest(),
        }
        self.store()

    def tearDown(self):
        self.tmp.cleanup()

    def store(self):
        (self.package / "manifest.json").write_text(
            json.dumps(self.record), encoding="utf-8",
        )

    def expected(self):
        return {"identity": self.identity, "files": self.files}

    def test_valid_inventory_and_read_only_restore_of_files(self):
        self.assertEqual(verify_package(self.package, expected=self.expected()), self.expected())
        target = self.root / "new-files"
        restore_files(self.package, target, expected=self.expected())
        self.assertEqual(sorted(p.name for p in target.iterdir()), sorted(self.names))

    def test_partial_group_membership_blocks(self):
        self.record["members"] = ["db"]
        self.store()
        with self.assertRaises(ValueError):
            verify_package(self.package)

    def test_foreign_image_identity_blocks(self):
        self.record["image"] = "postgres:latest"
        self.store()
        with self.assertRaises(ValueError):
            verify_package(self.package)

    def test_incorrect_compose_source_blocks(self):
        self.record["source_digest"] = "0" * 64
        self.store()
        with self.assertRaises(ValueError):
            verify_package(self.package)

    def test_modified_dump_blocks_before_restore(self):
        (self.package / "pg.dump").write_bytes(b"DAMAGE")
        target = self.root / "must-not-create"
        with self.assertRaises(ValueError):
            restore_files(self.package, target, expected=self.expected())
        self.assertFalse(target.exists())

    def test_missing_attachment_blocks_before_restore(self):
        (self.package / "assets" / self.name).unlink()
        target = self.root / "must-not-create"
        with self.assertRaises(ValueError):
            restore_files(self.package, target, expected=self.expected())
        self.assertFalse(target.exists())

    def test_wrong_identity_blocks(self):
        wrong = copy.deepcopy(self.expected())
        wrong["identity"] = "b" * 24
        with self.assertRaises(ValueError):
            verify_package(self.package, expected=wrong)

    def test_symlinked_package_is_rejected(self):
        alias = self.root / "alias"
        alias.symlink_to(self.package, target_is_directory=True)
        with self.assertRaises(ValueError):
            verify_package(alias)

    def test_manifest_has_no_runtime_execute_operation(self):
        self.assertFalse(hasattr(verify_package, "deploy"))
        self.assertFalse(hasattr(restore_files, "prune"))


if __name__ == "__main__":
    unittest.main()
