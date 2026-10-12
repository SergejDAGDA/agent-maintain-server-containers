#!/usr/bin/env python3
"""CI-only disposable Compose lifecycle and synthetic SQLite restoration smoke.

NOT a production executor, provider, or backup system. Refuses ordinary/local
execution even if Docker is available. No default-Docker host on developer PC.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from fixture_app import verify_state
from fixture_backup import capture_fixture, restore_fixture, seed_fixture, verify_checkpoint
from restic_fixture import ResticFixture, TEST_MARKER

HERE = Path(__file__).resolve().parent
COMPOSE = HERE / "fixture.compose.yaml"
APP = HERE / "fixture_app.py"
IMAGE = "python:3.12.12-slim@sha256:f3fa41d74a768c2fce8016b98c191ae8c1bacd8f1152870a3f9f87d350920b7c"
LABEL = "org.openai.maintain-server-containers.test"
MARKER = "isolated-ci-fixture-v1"


def refuse_unless_ephemeral() -> Path:
    required = {
        "GITHUB_ACTIONS": "true",
        "RUNNER_ENVIRONMENT": "github-hosted",
        "RUNNER_OS": "Linux",
        "CI": "true",
        "MSC_DISPOSABLE_TEST_RUNNER": MARKER,
    }
    if any(os.environ.get(k) != v for k, v in required.items()):
        raise RuntimeError("REFUSED: explicitly approved GitHub-hosted ephemeral runner required")
    if any(os.environ.get(k) for k in ("DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH")):
        raise RuntimeError("REFUSED: custom Docker endpoints or contexts are forbidden")
    temp = Path(os.environ.get("RUNNER_TEMP", ""))
    workspace = Path(os.environ.get("GITHUB_WORKSPACE", ""))
    if not temp.is_absolute() or not temp.is_dir() or temp.is_symlink():
        raise RuntimeError("REFUSED: invalid ephemeral runner temp root")
    if not workspace.is_absolute() or workspace.is_symlink() or not workspace.is_dir():
        raise RuntimeError("REFUSED: invalid GitHub workspace")
    if not HERE.is_relative_to(workspace.resolve()):
        raise RuntimeError("REFUSED: harness is not under the checked-out workspace")
    return temp.resolve()


def _run(args: list[str], *, env: dict | None = None, timeout: int = 90) -> str:
    result = subprocess.run(args, env=env, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=timeout, check=False)
    if result.returncode != 0:
        # Never relay raw Docker/Compose environment, stderr, or runtime values.
        raise RuntimeError(f"fixture command failed ({args[0:2]}, exit {result.returncode})")
    return result.stdout.strip()


def compose_args(project: str) -> list[str]:
    return ["docker", "compose", "--env-file", "/dev/null", "-f", str(COMPOSE),
            "--project-name", project]


def compose_env(state: Path) -> dict[str, str]:
    return dict(os.environ, MSC_STATE_DIR=str(state), MSC_FIXTURE_SCRIPT=str(APP))


def containers(project: str) -> list[str]:
    raw = _run(["docker", "ps", "-aq", "--filter", f"label=com.docker.compose.project={project}"])
    return [line for line in raw.splitlines() if line]


def verify_ownership(project: str, *, expected_state: Path | None = None) -> list[str]:
    """Refuse destructive teardown if any container has a mismatched owner label."""
    ids = containers(project)
    for identifier in ids:
        info = json.loads(_run(["docker", "inspect", identifier]))[0]
        labels = info.get("Config", {}).get("Labels", {})
        if labels.get("com.docker.compose.project") != project or labels.get(LABEL) != "true":
            raise RuntimeError("REFUSED: a project-scoped container lacks synthetic ownership")
        if expected_state is not None:
            host = info.get("HostConfig", {})
            mounts = info.get("Mounts", [])
            sources = {m.get("Source") for m in mounts}
            if (host.get("Privileged") or host.get("ReadonlyRootfs") is not True
                    or host.get("NetworkMode") != "none"
                    or sorted(sources) != sorted([str(expected_state), str(APP)])
                    or any(m.get("RW") is not False for m in mounts)):
                raise RuntimeError("REFUSED: fixture runtime security or mount boundary drift")
    return ids


def validate_rendered_compose(project: str, state: Path, env: dict) -> None:
    cfg = json.loads(_run(compose_args(project) + ["config", "--format", "json"], env=env))
    if set(cfg.get("services", {})) != {"fixture"}:
        raise RuntimeError("REFUSED: unreviewed Compose services")
    service = cfg["services"]["fixture"]
    volumes = service.get("volumes", [])
    targets = {(v.get("source"), v.get("target")) for v in volumes}
    approved = {(str(state), "/state"), (str(APP), "/fixture/app.py")}
    # Report only allowlisted preflight rule identifiers (no raw Compose,
    # environment, paths or secret-bearing Docker output).
    rules = {
        "image_pin": service.get("image") == IMAGE,
        "network_isolation": service.get("network_mode") == "none",
        "read_only_root": service.get("read_only") is True,
        "unprivileged_user": service.get("user") == "65534:65534",
        "no_privilege": not service.get("privileged", False),
        "capabilities_dropped": set(service.get("cap_drop", [])) == {"ALL"},
        "no_new_privileges": "no-new-privileges:true" in service.get("security_opt", []),
        "resource_limits": bool(service.get("pids_limit")) and bool(service.get("mem_limit")),
        "fixture_owner_label": service.get("labels", {}).get(LABEL) == "true",
        "exact_bind_paths": targets == approved and len(volumes) == 2,
        # Compose may omit an explicit create_host_path: false when rendering
        # JSON. Both source paths are pre-created and exact-match allowlisted.
        "read_only_binds": state.is_dir() and not state.is_symlink()
        and APP.is_file() and not APP.is_symlink() and all(
            v.get("type") == "bind" and v.get("read_only") is True
            and v.get("bind", {}).get("create_host_path") in (False, None)
            for v in volumes
        ),
        "no_unsafe_options": not any(key in service for key in (
            "build", "ports", "secrets", "devices", "env_file", "pid", "network",
            "extra_hosts", "group_add"
        )),
    }
    denied = [key for key, passed in rules.items() if not passed]
    if denied:
        raise RuntimeError("REFUSED: Compose isolation contract: " + ", ".join(denied))


def start_fixture(project: str, state: Path) -> None:
    env = compose_env(state)
    if containers(project):
        raise RuntimeError("REFUSED: disposable Compose project name already in use")
    validate_rendered_compose(project, state, env)
    _run(compose_args(project) + ["up", "-d", "--no-build", "--pull", "never"], env=env)
    if len(verify_ownership(project, expected_state=state)) != 1:
        raise RuntimeError("fixture container count unexpected")
    end = time.monotonic() + 55
    while time.monotonic() < end:
        state_id = containers(project)
        if len(state_id) != 1:
            raise RuntimeError("fixture container disappeared")
        status = _run(["docker", "inspect", "--format", "{{.State.Health.Status}}", state_id[0]])
        if status == "healthy":
            return
        if status == "unhealthy":
            raise RuntimeError("synthetic application health check failed")
        time.sleep(2)
    raise RuntimeError("synthetic application health timed out")


def teardown_fixture(project: str, state: Path) -> None:
    ids = verify_ownership(project, expected_state=state)
    if ids:
        _run(compose_args(project) + ["down", "--remove-orphans"], env=compose_env(state))
    if containers(project):
        raise RuntimeError("synthetic teardown left project containers behind")


def run_harness() -> None:
    temp = refuse_unless_ephemeral()
    if _run(["docker", "context", "show"]) != "default":
        raise RuntimeError("REFUSED: unexpected Docker context")
    _run(["docker", "compose", "version"])
    _run(["docker", "info", "--format", "{{.ServerVersion}}"])
    sandbox = Path(tempfile.mkdtemp(prefix="msc-disposable-", dir=temp))
    sandbox.chmod(0o755)
    suffix = secrets.token_hex(6)
    original_project = "msc-fixture-original-" + suffix
    restored_project = "msc-fixture-restored-" + suffix
    restic_project = "msc-fixture-restic-" + suffix
    original = sandbox / "original"
    restored = sandbox / "restored"
    good = sandbox / "checkpoints" / "known-good"
    corrupted = sandbox / "checkpoints" / "damaged"
    restic_source = sandbox / "source-checkpoint"
    restic_restored = sandbox / "restic-restored"
    fatal: Exception | None = None
    try:
        seed = seed_fixture(original)
        # All images use immutable reviewable digest. Only this synthetic
        # preparation step pulls a base image; fixture network is disabled.
        _run(["docker", "pull", IMAGE], timeout=180)
        start_fixture(original_project, original)
        captured = capture_fixture(original, good)
        if captured != seed:
            raise RuntimeError("checkpoint does not match running synthetic application")
        restore = restore_fixture(good, restored)
        if restore != seed or verify_state(restored) != seed:
            raise RuntimeError("restored state does not match original synthetic state")
        start_fixture(restored_project, restored)
        if verify_state(original) != verify_state(restored):
            raise RuntimeError("restoration smoke disagrees with original")
        # Negative: corrupt a *second* synthetic checkpoint; reject restore
        # without damaging the previously tested and protected checkpoint.
        capture_fixture(original, corrupted)
        targets = sorted((corrupted / "attachments").iterdir())
        targets[0].write_bytes(b"SYNTHETIC_CORRUPTION_ONLY")
        failed_target = sandbox / "must-not-be-restored"
        try:
            restore_fixture(corrupted, failed_target)
        except ValueError:
            pass
        else:
            raise RuntimeError("corrupt checkpoint was accepted")
        if failed_target.exists():
            raise RuntimeError("failed restore created visible target")
        if verify_checkpoint(good) != seed:
            raise RuntimeError("known-good checkpoint damaged during negative test")
        # Exercise an actual encrypted Restic repository against the same
        # synthetic data after application-consistent SQLite backup capture.
        marker = sandbox / ".msc-restic-ci-only"
        marker.write_text(TEST_MARKER + "\n", encoding="ascii")
        restic = ResticFixture(sandbox)
        restic.initialize()
        if capture_fixture(original, restic_source) != seed:
            raise RuntimeError("synthetic Restic source does not match original")
        snapshot_id = restic.capture(restic_source)
        evidence = restic.restore_and_verify(snapshot_id, staged_checkpoint=restic_source,
                                             restored_state=restic_restored)
        if not evidence.repository_checked or not evidence.restore_tested:
            raise RuntimeError("Restic recovery evidence incomplete")
        start_fixture(restic_project, restic_restored)
        if verify_state(restic_restored) != seed:
            raise RuntimeError("Restic-restored fixture health differs")
        restic.reject_incorrect_password()
        restic.check_snapshot(snapshot_id, staged_checkpoint=restic_source)
        print("H16 PASS encrypted Restic snapshot and repository data check", flush=True)
        print("H17 PASS exact Restic snapshot restored and Compose smoke healthy", flush=True)
        print("H18 PASS invalid Restic key refused; known-good retained", flush=True)
        print("H01 PASS synthetic isolated Compose app", flush=True)
        print("H03 PASS SQLite + attachments restored and healthy in separate project", flush=True)
        print("H08 PASS damaged snapshot refused, known-good intact", flush=True)
    except Exception as error:
        fatal = error
    finally:
        # All cleanup targets were uniquely generated on this CI run. NEVER
        # docker system prune, docker volume prune or generic down -v.
        for project, state in ((restic_project, restic_restored),
                               (restored_project, restored), (original_project, original)):
            try:
                teardown_fixture(project, state)
            except Exception as error:
                if fatal is None:
                    fatal = error
                print("FAIL fixture ownership-aware teardown", file=sys.stderr)
        if fatal is None:
            # Synthetic test-only artifacts, not customer backups.
            shutil.rmtree(sandbox)
            print("H15 PASS only owned synthetic runtime and data cleaned", flush=True)
        else:
            print("FAIL synthetic harness, preserving run-owned diagnostics in runner temp",
                  file=sys.stderr)
    if fatal is not None:
        raise RuntimeError("synthetic CI harness failed safely") from fatal


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true",
                        help="run only on explicitly marked GitHub-hosted ephemeral CI")
    args = parser.parse_args()
    if not args.run:
        parser.error("REFUSED: --run and ephemeral CI approval are required")
    run_harness()
