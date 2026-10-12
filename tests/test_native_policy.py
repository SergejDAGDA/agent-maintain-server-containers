"""Synthetic tests for extended project-maintenance policies."""
import importlib.util
import sys
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
SCRIPT = BASE / "skills" / "maintain-server-containers" / "scripts"
sys.path.insert(0, str(SCRIPT))
import maintenance  # noqa: E402
import native_policy  # noqa: E402


class ExtendedPolicyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = BASE / "examples" / "native-policy.yaml"

    def test_synthetic_fixture_is_structurally_valid(self):
        data = maintenance.load_policy(self.path)
        services, errors, warnings = native_policy.structure(data)
        self.assertFalse(errors, errors)
        self.assertEqual(len(services), 3)
        self.assertFalse(warnings, warnings)

    def test_vendor_namespaced_schema(self):
        data = maintenance.load_policy(self.path)
        data["schema"] = "independent-host-maintenance/v1"
        _, errors, _ = native_policy.structure(data)
        self.assertFalse(errors, errors)

    def test_unknown_schema_rejected(self):
        data = maintenance.load_policy(self.path)
        data["schema"] = "anything-goes/v3"
        _, errors, _ = native_policy.structure(data)
        self.assertTrue(errors)

    def test_safety_rule_cannot_be_downgraded(self):
        data = maintenance.load_policy(self.path)
        data["safety_invariants"]["security_release_gate_bypass"] = "allowed"
        _, errors, _ = native_policy.structure(data)
        self.assertTrue(any("security_release_gate_bypass" in x for x in errors))

    def test_manual_group_member_blocks_auto_safe(self):
        data = maintenance.load_policy(self.path)
        services, errors, _ = native_policy.structure(data)
        self.assertFalse(errors)
        records = native_policy.assess_native(data, services)
        self.assertEqual(records[0]["classification"], "BLOCKED")
        self.assertTrue(any("MANUAL" in x for x in records[0]["issues"]))

    def test_protected_stack_never_inspected_even_live(self):
        data = maintenance.load_policy(self.path)
        services, _, _ = native_policy.structure(data)
        protected = services[2]
        observed = native_policy.assess_native(data, [protected], live=True)
        self.assertEqual(observed[0]["classification"], "EXCLUDED")
        self.assertEqual(observed[0]["runtime"]["status"], "NOT_CHECKED")

    def test_explicit_state_contract_required(self):
        data = maintenance.load_policy(self.path)
        del data["services"][0]["state_contract"]["named_volumes"]
        _, errors, _ = native_policy.structure(data)
        self.assertTrue(any("named_volumes" in x for x in errors))

    def test_unknown_owner_blocks_auto_mode(self):
        data = maintenance.load_policy(self.path)
        data["services"][0]["ownership"] = "external_admin"
        _, errors, _ = native_policy.structure(data)
        self.assertTrue(any("external/unknown" in x for x in errors))

    def test_native_cli_validate_and_plan(self):
        self.assertEqual(maintenance.main(
            ["--policy", str(self.path), "validate"]), 0)
        self.assertEqual(maintenance.main(
            ["--policy", str(self.path), "plan"]), 0)

    def test_mutation_script_has_no_updater(self):
        self.assertNotIn("update-auto", maintenance.SUPPORTED)
        self.assertNotIn("update", maintenance.SUPPORTED)

    def test_sensitive_values_not_emitted(self):
        data = maintenance.load_policy(self.path)
        data["services"][0]["state_contract"]["secrets"] = ["secret_reference_only"]
        records = native_policy.assess_native(data, data["services"])
        self.assertNotIn("secret_reference_only", str(records))


if __name__ == "__main__":
    unittest.main()
