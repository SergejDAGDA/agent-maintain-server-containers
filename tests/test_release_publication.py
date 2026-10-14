"""Mocked GitHub release tests, offline and cross-platform."""
from __future__ import annotations
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / ".github/scripts/publish_v040.py"
spec = importlib.util.spec_from_file_location("publish_v040_test", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
SHA = "a" * 40


class FakeAPI:
    def __init__(self):
        self.main = SHA
        self.tag = None
        self.releases = []
        self.ok = True
        self.calls = []
        self.corrupt_tag = False

    def get(self, path):
        if path == "branches/main":
            return {"commit": {"sha": self.main}}
        if path.startswith("git/matching-refs/tags/"):
            return [] if self.tag is None else [{"ref": "refs/tags/v0.4.0"}]
        if path.startswith("releases?"):
            return self.releases[:]
        if path.startswith("actions/workflows/"):
            return {"workflow_runs": ([{"head_sha": SHA, "head_branch": "main",
                                       "event": "push", "status": "completed",
                                       "conclusion": "success"}] if self.ok else [])}
        if path == "git/ref/tags/v0.4.0":
            return {"object": {"type": "commit", "sha": self.tag}}
        if path == "releases/tags/v0.4.0":
            return self.releases[0]
        raise AssertionError(path)

    def post(self, path, body):
        self.calls.append((path, body))
        if path == "git/refs":
            self.tag = "b" * 40 if self.corrupt_tag else body["sha"]
            return {"ref": body["ref"]}
        if path == "releases":
            created = {"id": 1, "tag_name": "v0.4.0", "draft": False,
                       "prerelease": False, "published_at": "2026-10-14"}
            self.releases.append(created)
            return created
        raise AssertionError(path)


class PublicationContractTests(unittest.TestCase):
    def test_happy_path_exact_ci_sha(self):
        api = FakeAPI()
        self.assertEqual(module.publish(api, SHA, ROOT)["id"], 1)
        self.assertEqual(api.tag, SHA)
        self.assertEqual([x[0] for x in api.calls], ["git/refs", "releases"])

    def test_wrong_main_or_missing_ci_refused_without_mutation(self):
        for defect in ("main", "ci"):
            with self.subTest(defect=defect):
                api = FakeAPI()
                if defect == "main":
                    api.main = "b" * 40
                else:
                    api.ok = False
                with self.assertRaises(module.ReleaseRefused):
                    module.publish(api, SHA, ROOT)
                self.assertFalse(api.calls)

    def test_any_existing_tag_refused(self):
        for tag in (SHA, "b" * 40):
            api = FakeAPI()
            api.tag = tag
            with self.assertRaises(module.ReleaseRefused):
                module.publish(api, SHA, ROOT)
            self.assertFalse(api.calls)

    def test_any_release_state_refused(self):
        for draft, prerelease in ((True, False), (False, True), (False, False)):
            api = FakeAPI()
            api.releases = [{"tag_name": "v0.4.0", "draft": draft,
                             "prerelease": prerelease}]
            with self.assertRaises(module.ReleaseRefused):
                module.publish(api, SHA, ROOT)
            self.assertFalse(api.calls)

    def test_tag_identity_error_blocks_release(self):
        api = FakeAPI()
        api.corrupt_tag = True
        with self.assertRaises(module.ReleaseRefused):
            module.publish(api, SHA, ROOT)
        self.assertEqual([x[0] for x in api.calls], ["git/refs"])

    def test_repeated_manual_dispatch_never_republishes(self):
        api = FakeAPI()
        module.publish(api, SHA, ROOT)
        with self.assertRaises(module.ReleaseRefused):
            module.publish(api, SHA, ROOT)
        self.assertEqual(len(api.calls), 2)

    def test_invalid_sha_and_source_identity(self):
        for bad in ("", "x", "a" * 39):
            with self.assertRaises(module.ReleaseRefused):
                module.publish(FakeAPI(), bad, ROOT)
        module.verify_source(ROOT)


if __name__ == "__main__":
    unittest.main()
