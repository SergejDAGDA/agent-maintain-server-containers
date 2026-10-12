"""Read-only adapter for extended project maintenance policies, version 1.

This is a *format* adapter, not a server-specific implementation. It never
copies project hostnames, paths or credentials to the public skill.

Do not turn a declarative state contract into verified runtime safety.
"""
from __future__ import annotations

import re
import subprocess
import json
from typing import Any

POLICIES = {"AUTO_SAFE", "AUTO_GATED", "MANUAL", "PIN_ONLY", "NO_TOUCH"}
OWNERS = {"sandbox", "application_project", "external_admin", "unknown"}
SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
REQUIRED_TOP = {
    "schema", "policy_revision", "authority", "classes",
    "safety_invariants", "mutation_reporting", "version_policy",
    "backup_defaults", "service_groups", "smoke_profiles", "services"
}
REQUIRED_STATE = {
    "completeness", "binds", "named_volumes", "databases",
    "uploaded_user_files", "account_state", "secrets", "instance_identity",
    "disposable_caches"
}
EXPECTED_DIMENSIONS = {
    "application_version_modified", "runtime_container_state_modified",
    "persistent_user_state_modified", "deployment_source_modified",
    "network_access_modified", "database_schema_modified"
}


def _obj(value: Any) -> bool:
    return isinstance(value, dict)


def _safe_name(value: Any) -> bool:
    return isinstance(value, str) and SAFE_NAME.fullmatch(value) is not None


def resolve_group(group_name: str, group: dict, services: list[dict]) -> tuple[list[dict], list[str]]:
    """Resolve exact policy or Compose identities with explicitly declared aliases.

    An alias always identifies both the policy record and its exact Compose
    service. We never guess name normalization (hyphens, underscores, etc.).
    """
    problems: list[str] = []
    members = group.get("services")
    aliases = group.get("component_aliases", {})
    if not isinstance(members, list) or not members or not all(_safe_name(x) for x in members):
        return [], ["services must be a non-empty list of component names"]
    if len(set(members)) != len(members):
        problems.append("duplicate group member")
    if not _obj(aliases):
        return [], problems + ["component_aliases must be a mapping"]
    by_name = {service["name"]: service for service in services}
    resolved: list[dict] = []
    for alias_key in aliases:
        if alias_key not in members:
            problems.append(f"alias {alias_key}: not listed in group services")
    for member in members:
        exact_name = by_name.get(member)
        exact_compose = [s for s in services
                         if member in (s.get("identity", {}).get("compose_services") or [])]
        if member in aliases:
            alias = aliases[member]
            if exact_name or exact_compose:
                problems.append(f"component {member}: unnecessary/conflicting alias")
                continue
            if not _obj(alias) or set(alias) != {"policy_service", "compose_service"}:
                problems.append(f"component {member}: alias requires policy_service and compose_service")
                continue
            policy_name = alias.get("policy_service")
            compose_name = alias.get("compose_service")
            owner = by_name.get(policy_name) if _safe_name(policy_name) else None
            if owner is None or not _safe_name(compose_name):
                problems.append(f"component {member}: alias owner or Compose name invalid")
                continue
            owner_services = owner.get("identity", {}).get("compose_services") or []
            if compose_name not in owner_services:
                problems.append(f"component {member}: alias Compose service not in owning record")
                continue
            target_group = owner.get("dependencies", {}).get("update_group")
            if target_group != group_name:
                problems.append(f"component {member}: alias policy owner belongs to another group")
                continue
            resolved.append(owner)
        elif exact_name:
            resolved.append(exact_name)
        elif len(exact_compose) == 1:
            resolved.append(exact_compose[0])
        elif len(exact_compose) > 1:
            problems.append(f"component {member}: ambiguous Compose service identity")
        else:
            problems.append(f"component {member}: unresolved; declare an explicit component_aliases entry")
    unique = {s["name"]: s for s in resolved}
    return list(unique.values()), problems


def structure(policy: dict) -> tuple[list[dict], list[str], list[str]]:
    """Validate structural shape. Return service records, fatal errors and warnings.

    Compatibility does not mean that an update is authorized.
    """
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(policy.get("schema"), str) or not re.fullmatch(r"[a-z][a-z0-9-]*-maintenance/v1", policy["schema"]):
        errors.append("unsupported native policy schema")
    if policy.get("policy_revision") != 1:
        errors.append("unsupported native policy revision")
    for key in sorted(REQUIRED_TOP.difference(policy)):
        errors.append(f"missing policy field: {key}")
    for key in ("authority", "classes", "safety_invariants", "mutation_reporting",
                "version_policy", "backup_defaults", "service_groups", "smoke_profiles"):
        if key in policy and not _obj(policy[key]):
            errors.append(f"{key} must be a mapping")
    classes = policy.get("classes", {})
    if _obj(classes):
        if set(classes) != POLICIES:
            errors.append("classes must define all five supported policies without unknown classes")
        else:
            for name, expected in (("AUTO_SAFE", True), ("AUTO_GATED", True),
                                   ("MANUAL", False), ("PIN_ONLY", True),
                                   ("NO_TOUCH", False)):
                settings = classes[name]
                if not _obj(settings) or settings.get("mutation_allowed") is not expected:
                    errors.append(f"classes.{name}.mutation_allowed contradicts policy")
            if (_obj(classes["PIN_ONLY"]) and
                    classes["PIN_ONLY"].get("application_content_upgrade_allowed") is not False):
                errors.append("PIN_ONLY must forbid application content upgrades")
    invariants = policy.get("safety_invariants", {})
    if _obj(invariants):
        required = {
            "no_proven_state_contract": "no_update",
            "image_rollback_is_not_state_rollback": True,
            "external_or_unknown_ownership": "never_automatic",
            "security_release_gate_bypass": "prohibited",
        }
        for key, expected in required.items():
            if invariants.get(key) != expected:
                errors.append(f"required safety invariant missing or changed: {key}")
    report = policy.get("mutation_reporting", {})
    if _obj(report):
        dims = report.get("dimensions")
        if not isinstance(dims, list) or not EXPECTED_DIMENSIONS.issubset(
                {x for x in dims if isinstance(x, str)}):
            errors.append("six independent mutation reporting dimensions required")
    default_backup = policy.get("backup_defaults", {})
    if _obj(default_backup) and default_backup.get("required_for_runtime_mutation") is not True:
        errors.append("global backup default must require backup before runtime mutation")
    raw = policy.get("services", [])
    if not isinstance(raw, list):
        return [], errors + ["services must be a list"], warnings
    seen: set[str] = set()
    services: list[dict] = []
    for idx, service in enumerate(raw):
        if not _obj(service):
            errors.append(f"services[{idx}] must be a mapping")
            continue
        name = service.get("name")
        if not _safe_name(name):
            errors.append(f"services[{idx}] has invalid service name")
            continue
        if name in seen:
            errors.append(f"duplicate service: {name}")
            continue
        seen.add(name)
        services.append(service)
        cls = service.get("policy_class")
        owner = service.get("ownership")
        if cls not in POLICIES:
            errors.append(f"{name}: unsupported policy_class")
        if owner not in OWNERS:
            errors.append(f"{name}: unsupported ownership")
        for key in ("identity", "deployment", "image", "upstream",
                    "version_policy", "state_contract", "backup", "migration",
                    "topology", "health", "smoke", "rollback", "dependencies", "no_touch"):
            if not _obj(service.get(key)):
                errors.append(f"{name}: {key} must be a mapping")
        state = service.get("state_contract")
        if _obj(state):
            for key in REQUIRED_STATE.difference(state):
                errors.append(f"{name}: state_contract.{key} missing")
            if state.get("completeness") not in (
                "complete", "partial", "unknown", "not_required_for_no_touch"
            ):
                errors.append(f"{name}: invalid state completeness")
            if not isinstance(state.get("binds"), (list, str)):
                errors.append(f"{name}: state_contract.binds invalid")
            if not isinstance(state.get("named_volumes"), (list, str)):
                errors.append(f"{name}: state_contract.named_volumes invalid")
            if cls in ("AUTO_SAFE", "AUTO_GATED") and state.get("completeness") != "complete":
                warnings.append(f"{name}: incomplete state blocks automatic updates")
        ident = service.get("identity")
        if _obj(ident):
            names = ident.get("compose_services")
            if not isinstance(names, list) or not names or not all(_safe_name(x) for x in names):
                errors.append(f"{name}: identity.compose_services invalid")
        if cls == "NO_TOUCH" and (_obj(service.get("no_touch")) and service["no_touch"].get("enabled") is not True):
            errors.append(f"{name}: NO_TOUCH must have no_touch.enabled=true")
        if owner in ("external_admin", "unknown") and cls in ("AUTO_SAFE", "AUTO_GATED", "PIN_ONLY"):
            errors.append(f"{name}: external/unknown ownership cannot be automatic")
        if cls in ("AUTO_SAFE", "AUTO_GATED"):
            b = service.get("backup")
            if _obj(b) and b.get("required") is not True:
                errors.append(f"{name}: automatic mutation requires service backup")
            if _obj(service.get("deployment")) and not service["deployment"].get("source_reproducible", False):
                warnings.append(f"{name}: deployment not proven reproducible")
    groups = policy.get("service_groups", {})
    if _obj(groups):
        for group_name, group in groups.items():
            if not _safe_name(group_name) or not _obj(group):
                errors.append("service group name/definition invalid")
                continue
            _, problems = resolve_group(group_name, group, services)
            for problem in problems:
                message = f"group {group_name}: {problem}"
                # An update-as-group declaration is an enforceable safety boundary.
                if group.get("update_as_group") is True:
                    errors.append(message)
                else:
                    warnings.append(message)
    return services, errors, warnings


def _runtime(service: dict) -> dict:
    """Inspect uniquely named live Compose containers. Read-only and bounded."""
    ident = service["identity"]
    project = ident.get("compose_project")
    names = ident.get("compose_services", [])
    if not _safe_name(project) or not isinstance(names, list):
        return {"status": "UNVERIFIED", "reason": "Compose runtime identity unavailable"}
    results = []
    for name in names:
        if not _safe_name(name):
            return {"status": "UNVERIFIED", "reason": "Compose service identifier invalid"}
        try:
            p = subprocess.run(
                ["docker", "ps", "-a", "--quiet", "--filter",
                 f"label=com.docker.compose.project={project}", "--filter",
                 f"label=com.docker.compose.service={name}"],
                capture_output=True, text=True, timeout=15, check=False
            )
            if p.returncode:
                return {"status": "UNVERIFIED", "reason": "Docker unavailable"}
            ids = [s for s in p.stdout.splitlines() if s]
            if len(ids) != 1:
                return {"status": "UNVERIFIED", "reason": "Compose service not unique"}
            q = subprocess.run(
                ["docker", "inspect", "--format", "{{json .}}", ids[0]],
                capture_output=True, text=True, timeout=15, check=False
            )
            if q.returncode:
                return {"status": "UNVERIFIED", "reason": "Docker inspect unavailable"}
            obj = json.loads(q.stdout)
            results.append({
                "service": name,
                "image_id": obj.get("Image"),
                "configured_image": obj.get("Config", {}).get("Image"),
                "running": obj.get("State", {}).get("Running"),
                "health": obj.get("State", {}).get("Health", {}).get("Status", "no_healthcheck")
            })
        except (OSError, subprocess.TimeoutExpired, ValueError, TypeError):
            return {"status": "UNVERIFIED", "reason": "Docker inspection unavailable"}
    return {"status": "OBSERVED", "services": results}


def _records_for_group(policy: dict, service: dict, services: list[dict]) -> tuple[list[dict], list[str]]:
    dep = service.get("dependencies", {})
    group_name = dep.get("update_group") if _obj(dep) else None
    groups = policy.get("service_groups", {})
    if not group_name or not _obj(groups) or group_name not in groups:
        return [], []
    group = groups[group_name]
    if not _obj(group):
        return [], ["dependency group definition invalid"]
    return resolve_group(group_name, group, services)


def assess_native(policy: dict, services: list[dict], *, live: bool = False) -> list[dict]:
    results = []
    for service in services:
        name = service["name"]
        cls = service.get("policy_class")
        owner = service.get("ownership")
        issues = []
        observed = {"status": "NOT_CHECKED"}
        if cls == "NO_TOUCH":
            result = "EXCLUDED"
        elif cls == "MANUAL":
            result = "MANUAL_REVIEW"
        else:
            result = "GATED"
            if owner in ("external_admin", "unknown"):
                issues.append("ownership excludes automatic maintenance")
            state = service.get("state_contract", {})
            if not _obj(state) or state.get("completeness") != "complete":
                issues.append("state contract incomplete")
            if not service.get("deployment", {}).get("source_reproducible", False):
                issues.append("deployment not proven reproducible")
            if _obj(service.get("backup")) and not service["backup"].get("required", False):
                issues.append("backup requirement missing")
            group, group_errors = _records_for_group(policy, service, services)
            if group_errors:
                issues.append("dependency group membership unresolved")
            if any(s.get("policy_class") in ("MANUAL", "NO_TOUCH") for s in group):
                issues.append("dependency group includes MANUAL/NO_TOUCH member")
            if cls == "PIN_ONLY":
                image = service.get("image", {})
                if not image.get("declared_reference") or not image.get("immutable_identity"):
                    issues.append("immutable source pin identity unresolved")
            else:
                version = service.get("version_policy", {})
                if not version.get("target_candidate"):
                    issues.append("no explicit reviewed upgrade target declared")
                if cls == "AUTO_GATED":
                    issues.append("migration/restore/compatibility gates require live evidence")
            if live and cls != "NO_TOUCH":
                observed = _runtime(service)
                if observed.get("status") != "OBSERVED":
                    issues.append("live runtime identity unverified")
                elif not all(x.get("running") for x in observed["services"]):
                    issues.append("one or more Compose services not running")
            else:
                issues.append("live runtime not inspected")
            if cls == "PIN_ONLY":
                issues.append("PIN_ONLY may not change application contents")
            if issues:
                result = "BLOCKED" if any(
                    x in issues for x in (
                        "ownership excludes automatic maintenance",
                        "state contract incomplete",
                        "deployment not proven reproducible",
                        "backup requirement missing",
                        "dependency group includes MANUAL/NO_TOUCH member",
                        "dependency group membership unresolved",
                        "one or more Compose services not running",
                        "live runtime identity unverified",
                    )
                ) else "GATED"
        results.append({
            "name": name,
            "policy": cls,
            "ownership": owner,
            "classification": result,
            "issues": issues,
            "runtime": observed,
            "target_candidate": service.get("version_policy", {}).get("target_candidate"),
        })
    return results
