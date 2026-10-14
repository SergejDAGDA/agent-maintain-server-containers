"""Public release package invariants; no network, Docker or credentials."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "maintain-server-containers"
VERSION = "0.3.0"


class PublicReleasePackagingTests(unittest.TestCase):
    def test_manifests_and_installed_skill_version_agree(self):
        self.assertEqual(json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))["version"], VERSION)
        self.assertEqual(
            json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"],
            VERSION,
        )
        self.assertEqual((SKILL / "VERSION").read_text(encoding="utf-8").strip(), VERSION)
        for path in ("SKILL.md", "scripts/maintenance.py",
                     "references/policy-schema.md",
                     "references/maintenance-protocol.md"):
            self.assertTrue((SKILL / path).is_file(), path)

    def test_release_notes_and_changelog_cover_limitations(self):
        notes = (ROOT / "docs" / "releases" / "v0.3.0.md").read_text(encoding="utf-8")
        change = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn("## 0.3.0 - 2026-10-13", change)
        self.assertIn("H20", notes)
        self.assertIn("H31", notes)
        self.assertIn("read-only", notes.lower())
        self.assertIn("off-host", notes)
        self.assertIn("no bundled deterministic production", notes.lower())
        self.assertIn("## 0.2.0 - 2026-10-12", change)

    def test_release_docs_explain_controlled_codex_upgrade(self):
        content = (ROOT / "docs" / "CODEX-INSTALL-UPDATE.md").read_text(encoding="utf-8")
        for term in ("tree/v0.3.0/skills/maintain-server-containers",
                     "back up", "VERSION", "restart", "read-only"):
            self.assertIn(term.lower(), content.lower())
        for filename in ("README.md", "README.ru.md"):
            data = (ROOT / filename).read_text(encoding="utf-8")
            self.assertIn("v0.3.0", data)
            self.assertIn("CODEX-INSTALL-UPDATE.md", data)

    def test_publication_requires_both_ci_gates(self):
        workflow = (ROOT / ".github" / "workflows" / "release-v0.3.0.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_run:", workflow)
        self.assertIn('workflows: ["Disposable Compose recovery fixture"]', workflow)
        self.assertIn("conclusion == 'success'", workflow)
        self.assertIn("head_repository.full_name == github.repository", workflow)
        self.assertIn('actions/workflows/tests.yml/runs?', workflow)
        self.assertIn('.event == "push"', workflow)
        self.assertIn('contents: write', workflow)
        self.assertIn('existing tag points to a different commit', workflow)
        self.assertIn('git/matching-refs/tags/$RELEASE_TAG', workflow)
        self.assertIn('select(.ref == $full)', workflow)
        self.assertNotIn('git/ref/tags/$RELEASE_TAG', workflow)
        self.assertIn('gh release create', workflow)
        self.assertIn('Published v0.3.0 is frozen', workflow)
        self.assertIn('de1708213dbaf2895719120023d5bddfe42715e3', workflow)
        self.assertIn('docs/releases/v0.3.0.md', workflow)


if __name__ == "__main__":
    unittest.main()
