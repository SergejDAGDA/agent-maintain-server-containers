"""Release-management policy routing tests (all fixtures are synthetic)."""
import io
import contextlib
import sys
import unittest
from copy import deepcopy
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "skills" / "maintain-server-containers" / "scripts"
sys.path.insert(0, str(SCRIPT))
import maintenance
from release_management import validate_release_management


CONFIG = {
    "strategy": "project_managed",
    "release_authority": "application_project",
    "version_monitoring": False,
    "automatic_updates": False,
}


class ReleaseManagementTest(unittest.TestCase):
    def test_targeted_manual_release_configuration_accepted(self):
        row = {"name": "private-app", "policy_class": "MANUAL",
               "release_management": deepcopy(CONFIG)}
        self.assertEqual(validate_release_management(row, class_field="policy_class"), [])

    def test_no_touch_is_not_override(self):
        row = {"name": "protected-app", "policy_class": "NO_TOUCH",
               "release_management": deepcopy(CONFIG)}
        self.assertEqual(validate_release_management(row, class_field="policy_class"), [])

    def test_project_managed_cannot_be_auto_safe(self):
        row = {"name": "private-app", "policy_class": "AUTO_SAFE",
               "release_management": deepcopy(CONFIG)}
        self.assertTrue(validate_release_management(row, class_field="policy_class"))

    def test_project_managed_rejects_automatic_updates(self):
        cfg = deepcopy(CONFIG)
        cfg["automatic_updates"] = True
        row = {"name": "private-app", "policy_class": "MANUAL", "release_management": cfg}
        self.assertTrue(any("update-auto" in x for x in validate_release_management(
            row, class_field="policy_class")))

    def test_project_managed_rejects_unsolicited_monitoring(self):
        cfg = deepcopy(CONFIG)
        cfg["version_monitoring"] = True
        row = {"name": "private-app", "policy_class": "MANUAL", "release_management": cfg}
        self.assertTrue(any("monitoring" in x for x in validate_release_management(
            row, class_field="policy_class")))

    def test_missing_authority_and_unknown_strategy_rejected(self):
        cfg = deepcopy(CONFIG)
        cfg["strategy"] = "guess"
        cfg.pop("release_authority")
        issues = validate_release_management(
            {"name": "private-app", "policy_class": "MANUAL", "release_management": cfg},
            class_field="policy_class")
        self.assertTrue(any("unsupported" in x for x in issues))
        self.assertTrue(any("missing" in x for x in issues))

    def test_external_admin_is_not_app_owner(self):
        cfg = deepcopy(CONFIG)
        cfg["release_authority"] = "external_admin"
        self.assertTrue(validate_release_management(
            {"name": "private-app", "policy": "MANUAL", "release_management": cfg},
            class_field="policy"))

    def test_portable_policy_rejects_project_managed_auto_safe(self):
        path = Path(__file__).resolve().parents[1] / "examples/services.yaml"
        policy = maintenance.load_policy(path)
        policy["services"][0]["release_management"] = deepcopy(CONFIG)
        _, issues = maintenance.normalize(policy)
        self.assertTrue(any("requires MANUAL or NO_TOUCH" in x for x in issues))

    def test_existing_policies_remain_compatible(self):
        base = Path(__file__).resolve().parents[1] / "examples"
        for example in ("services.yaml", "native-policy.yaml"):
            with self.subTest(example=example):
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    rc = maintenance.main(["--policy", str(base / example), "validate"])
                self.assertEqual(rc, 0, out.getvalue())

    def test_cli_has_no_deploy_mutation_command(self):
        self.assertNotIn("deploy-project", maintenance.SUPPORTED)


if __name__ == "__main__":
    unittest.main()
