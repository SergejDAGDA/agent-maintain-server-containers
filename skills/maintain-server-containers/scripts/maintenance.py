#!/usr/bin/env python3
"""Read-only policy checks for the maintain-server-containers Agent Skill.

No command in this module changes Docker, Compose, images, files, or networks.
A plan is not an authorization or proof of backup/recovery readiness.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

POLICIES = {"AUTO_SAFE", "AUTO_GATED", "MANUAL", "PIN_ONLY", "NO_TOUCH"}
OWNERS = {"sandbox", "application_project", "external_admin", "unknown"}
POLICY_VERSION = "1"
NAME = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*$")
SUPPORTED = {"validate", "audit", "status", "plan"}


class PolicyError(Exception):
    pass


def _mapping(value: Any, label: str) -> dict:
    if not isinstance(value, dict):
        raise PolicyError(f"{label} must be a mapping")
    return value


def _list(value: Any, label: str) -> list:
    if not isinstance(value, list):
        raise PolicyError(f"{label} must be a list")
    return value


def load_policy(path: Path) -> dict:
    if not path.is_file():
        raise PolicyError("Policy file does not exist")
    if path.suffix.lower() == ".json":
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, UnicodeError) as exc:
            raise PolicyError("Invalid JSON policy") from exc
    else:
        try:
            import yaml
        except ImportError as exc:
            raise PolicyError("YAML policy requires PyYAML (pip install -r requirements.txt)") from exc
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (yaml.YAMLError, UnicodeError) as exc:
            raise PolicyError("Invalid YAML policy") from exc
    return _mapping(data, "Policy")


def normalize(data: dict) -> tuple[list[dict], list[str]]:
    """Normalize the documented portable v1 schema. Never assume unknown fields are safe."""
    errors: list[str] = []
    version = str(data.get("schema_version", ""))
    if version != POLICY_VERSION:
        errors.append("schema_version must be '1' (explicit migration required)")
    raw = data.get("services")
    if isinstance(raw, dict):
        # Named mapping accepted for simple project configuration.
        entries = [dict({"name": key}, **value) if isinstance(value, dict) and "name" not in value
                   else value for key, value in raw.items()]
    elif isinstance(raw, list):
        entries = raw
    else:
        raise PolicyError("services must be a list or a named mapping")
    normalized: list[dict] = []
    seen: set[str] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            errors.append(f"services[{index}] must be a mapping")
            continue
        name = entry.get("name")
        if not isinstance(name, str) or not NAME.fullmatch(name):
            errors.append(f"services[{index}].name is invalid")
            continue
        if name in seen:
            errors.append(f"{name}: duplicate service identity")
            continue
        seen.add(name)
        policy = entry.get("policy")
        ownership = entry.get("ownership")
        if policy not in POLICIES:
            errors.append(f"{name}: invalid or missing policy")
        if ownership not in OWNERS:
            errors.append(f"{name}: invalid or missing ownership")
        for field in ("deployment", "state", "backup", "rollback", "health", "smoke", "target"):
            if field in entry and not isinstance(entry[field], dict):
                errors.append(f"{name}: {field} must be a mapping")
        normalized.append(entry)
    return normalized, errors


def validate_service(service: dict) -> list[str]:
    name = service["name"]
    policy = service.get("policy")
    owner = service.get("ownership")
    issues: list[str] = []
    if policy in {"MANUAL", "NO_TOUCH"}:
        return issues
    if owner in {"external_admin", "unknown"}:
        issues.append("ownership not eligible for automated maintenance")
    state = service.get("state", {})
    if not isinstance(state, dict) or state.get("complete") is not True:
        issues.append("state contract not proven complete")
    for key in ("binds", "volumes", "databases", "user_files", "secret_refs"):
        if not isinstance(state.get(key), list):
            issues.append(f"state.{key} must be an explicit list, even when empty")
    deploy = service.get("deployment", {})
    if not isinstance(deploy, dict) or not all(
        isinstance(deploy.get(k), str) and deploy[k].strip()
        for k in ("compose_file", "project", "service")
    ):
        issues.append("reproducible Compose deployment identity incomplete")
    if not isinstance(service.get("image"), dict) or not isinstance(
        service["image"].get("current"), str
    ):
        issues.append("current image identity missing")
    if policy not in {"PIN_ONLY"}:
        target = service.get("target", {})
        if not isinstance(target, dict) or not isinstance(target.get("image"), str):
            issues.append("explicit target image not specified")
    else:
        if not isinstance(service.get("target"), dict) or not isinstance(
            service["target"].get("image"), str
        ):
            issues.append("explicit immutable pin target missing")
    rollback = service.get("rollback", {})
    if not isinstance(rollback, dict) or rollback.get("class") not in (
        "image_only", "state_restore_required", "unknown"
    ):
        issues.append("rollback classification missing")
    if policy == "AUTO_SAFE" and rollback.get("class") != "image_only":
        issues.append("AUTO_SAFE requires proven image-only rollback")
    if policy == "AUTO_GATED" and rollback.get("class") == "unknown":
        issues.append("AUTO_GATED rollback contract unresolved")
    if not isinstance(service.get("health"), dict):
        issues.append("health contract missing")
    if not isinstance(service.get("smoke"), dict):
        issues.append("smoke profile contract missing")
    backup = service.get("backup", {})
    if not isinstance(backup, dict) or not isinstance(backup.get("required"), bool):
        issues.append("backup requirement not declared")
    if policy == "AUTO_GATED" and backup.get("required") is not True:
        issues.append("AUTO_GATED requires backup gate")
    return issues


def docker_snapshot(service: dict) -> dict:
    """Read only a uniquely identified Compose service. No shell and no mutation."""
    deployment = service.get("deployment", {})
    if not isinstance(deployment, dict):
        return {"status": "unverified"}
    project = deployment.get("project")
    name = deployment.get("service")
    if not all(isinstance(s, str) and NAME.fullmatch(s) for s in (project, name)):
        return {"status": "unverified"}
    command = ["docker", "ps", "-a", "--quiet",
               "--filter", f"label=com.docker.compose.project={project}",
               "--filter", f"label=com.docker.compose.service={name}"]
    try:
        proc = subprocess.run(command, text=True, capture_output=True, timeout=15, check=False)
        if proc.returncode:
            return {"status": "unverified", "reason": "docker unavailable"}
        ids = [s for s in proc.stdout.splitlines() if s]
        if len(ids) != 1:
            return {"status": "unverified", "reason": "expected exactly one Compose container"}
        proc = subprocess.run(["docker", "inspect", "--format",
                               "{{json .}}", ids[0]],
                              text=True, capture_output=True, timeout=15, check=False)
        if proc.returncode:
            return {"status": "unverified", "reason": "inspect unavailable"}
        obj = json.loads(proc.stdout)
        state = obj.get("State", {})
        return {
            "status": "verified",
            "image_id": obj.get("Image"),
            "configured_image": obj.get("Config", {}).get("Image"),
            "running": state.get("Running"),
            "health": state.get("Health", {}).get("Status", "none"),
            "container_id": obj.get("Id"),
            "mounts": sorted({
                (m.get("Type"), m.get("Name") or m.get("Source"), m.get("Destination"),
                 not bool(m.get("RW", True))) for m in obj.get("Mounts", [])
            }, key=str),
        }
    except (OSError, subprocess.TimeoutExpired, ValueError, TypeError):
        return {"status": "unverified", "reason": "runtime inspection unavailable"}


def assessment(service: dict, runtime: dict | None) -> dict:
    issues = validate_service(service)
    policy = service.get("policy")
    if policy == "NO_TOUCH":
        classification = "EXCLUDED"
    elif policy == "MANUAL":
        classification = "MANUAL_REVIEW"
    elif issues:
        classification = "BLOCKED"
    else:
        classification = "CANDIDATE"
    r = runtime or {"status": "not_checked"}
    if classification == "CANDIDATE" and r.get("status") != "verified":
        issues.append("current runtime not independently verified")
        classification = "BLOCKED"
    if classification == "CANDIDATE":
        expected = service.get("image", {}).get("current")
        observed = r.get("configured_image")
        if expected != observed:
            issues.append("configured image differs from policy (resolve before update)")
            classification = "BLOCKED"
        if not r.get("running"):
            issues.append("service is not currently running")
            classification = "BLOCKED"
    if classification == "CANDIDATE":
        # A generic YAML declaration is never proof of recovery or smoke-test execution.
        issues.append("live backup, upstream, topology, and smoke gates need execution-time proof")
        classification = "GATED"
    return {
        "name": service["name"],
        "policy": policy,
        "ownership": service.get("ownership"),
        "classification": classification,
        "issues": issues,
        "runtime": {
            "status": r.get("status"),
            "running": r.get("running"),
            "health": r.get("health"),
            "configured_image": r.get("configured_image"),
            "image_id": r.get("image_id")
        },
        "proposed_target": (service.get("target", {}).get("image")
                            if isinstance(service.get("target"), dict) else None),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only container maintenance policy tool")
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--live", action="store_true", help="Inspect Docker read-only")
    parser.add_argument("--runtime-json", type=Path, help="Synthetic/runtime evidence for testing")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("operation", choices=sorted(SUPPORTED))
    args = parser.parse_args(argv)
    try:
        data = load_policy(args.policy)
        if data.get("schema") == "sandbox-server-maintenance/v1":
            from native_policy import structure, assess_native
            services, errors, warnings = structure(data)
            if args.runtime_json:
                raise PolicyError("native policy adapter does not accept synthetic runtime evidence")
            if args.operation == "validate":
                result = {
                    "schema": "sandbox-server-maintenance/v1",
                    "services": len(services),
                    "valid": not errors,
                    "errors": errors,
                    "warnings": warnings,
                    "note": "Structural compatibility is not authorization or proof of recovery."
                }
            else:
                records = assess_native(data, services, live=args.live)
                result = {
                    "operation": args.operation,
                    "read_only": True,
                    "schema": "sandbox-server-maintenance/v1",
                    "policy_valid": not errors,
                    "errors": errors,
                    "warnings": warnings,
                    "services": records,
                    "note": "All candidates remain gated until release, backup and recovery evidence is verified."
                }
            if args.format == "json":
                print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
            else:
                for error in errors:
                    print(f"ERROR: {error}")
                if args.operation == "validate":
                    print(f"Native policy structural validation: {'PASS' if not errors else 'FAIL'} "
                          f"({len(services)} services)")
                else:
                    for record in result["services"]:
                        print(f"{record['name']}: {record['classification']} "
                              f"[{record['policy']}]")
                        for issue in record["issues"]:
                            print(f"  - {issue}")
                    print("READ-ONLY. No changes made.")
                for warning in warnings:
                    print(f"NOTE: {warning}")
            return 2 if errors else 0
        services, errors = normalize(data)
        if args.live and args.runtime_json:
            raise PolicyError("--live and --runtime-json cannot be combined")
        evidence = {}
        if args.runtime_json:
            evidence = _mapping(json.loads(args.runtime_json.read_text(encoding="utf-8")),
                                "Runtime evidence")
        if args.operation == "validate":
            for service in services:
                for issue in validate_service(service):
                    # Record blockers for actionable update classes only.
                    if service.get("policy") not in {"MANUAL", "NO_TOUCH"}:
                        errors.append(f"{service['name']}: {issue}")
            result = {"schema_version": POLICY_VERSION, "services": len(services),
                      "valid": not errors, "errors": errors}
        else:
            records = [assessment(s, docker_snapshot(s) if args.live else evidence.get(s["name"]))
                       for s in services]
            result = {"operation": args.operation, "read_only": True,
                      "policy_valid": not errors, "errors": errors,
                      "services": records,
                      "note": "CANDIDATE/GATED is not approval. No Docker mutation is implemented."}
        if args.format == "json":
            print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
        else:
            if errors:
                for error in errors:
                    print(f"ERROR: {error}")
            if args.operation == "validate":
                print(f"Policy: {'PASS' if result['valid'] else 'FAIL'} "
                      f"({len(services)} services)")
            else:
                for record in result["services"]:
                    print(f"{record['name']}: {record['classification']} "
                          f"[{record['policy']}]")
                    for issue in record["issues"]:
                        print(f"  - {issue}")
                print("READ-ONLY. No changes made.")
        return 2 if errors or (args.operation == "validate" and not result["valid"]) else 0
    except (PolicyError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
