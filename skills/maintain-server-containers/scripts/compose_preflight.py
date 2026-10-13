#!/usr/bin/env python3
"""Read-only local Compose source reproducibility preflight.

Run ONLY in the filesystem/environment from which the Compose deployment
was created. Paths from a remote Docker Engine are NOT local paths. This
script never calls Docker daemon mutations; optional rendering invokes
only `docker compose ... config --quiet` for already reviewed Compose files.
It does not print Compose contents, interpolated environment or raw errors.
A successful render is not backup, runtime parity or update authorization.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def _decision(status: str, blockers: tuple[str, ...], checked: int) -> dict:
    return {
        "status": status, "blockers": list(blockers),
        "checked_files": checked,
        "source_reproducible": status == "SOURCE_RENDERED_LOCAL_ONLY",
        "runtime_state_verified": False,
        "update_authorized": False,
        "read_only": True,
    }


def inspect_source(
    files: list[Path], *, project_directory: Path | None = None,
    render: bool = False,
) -> dict:
    if not isinstance(files, list) or not files or len(files) > 64:
        return _decision("BLOCKED", ("source:invalid_file_set",), 0)
    if project_directory is not None:
        if (not isinstance(project_directory, Path)
                or not project_directory.is_dir()
                or project_directory.is_symlink()):
            return _decision("BLOCKED", ("source:project_directory_unavailable",), 0)
    checked: list[Path] = []
    for p in files:
        if not isinstance(p, Path) or not str(p):
            return _decision("BLOCKED", ("source:invalid_file_set",), len(checked))
        path = ((project_directory / p) if project_directory is not None
                else p)
        if path.is_symlink():
            return _decision("BLOCKED", ("source:unreviewed_symlink",), len(checked))
        if not path.is_file():
            return _decision("BLOCKED", ("source:file_missing_or_unreadable",), len(checked))
        checked.append(path)
    if not render:
        return _decision("FILES_PRESENT_NOT_RENDER_VERIFIED",
                         ("source:render_not_checked",), len(checked))
    command = ["docker", "compose"]
    if project_directory is not None:
        command.extend(["--project-directory", str(project_directory)])
    for p in checked:
        command.extend(["-f", str(p)])
    command.extend(["config", "--quiet"])
    try:
        finished = subprocess.run(
            command, capture_output=True, text=True,
            timeout=30, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return _decision("BLOCKED", ("source:compose_cli_unavailable",), len(checked))
    if finished.returncode != 0:
        return _decision("BLOCKED", ("source:render_failed",), len(checked))
    return _decision("SOURCE_RENDERED_LOCAL_ONLY", (), len(checked))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="No-mutation local Compose source preflight")
    parser.add_argument("--file", type=Path, action="append", required=True,
                        help="One of the exact ordered Compose source files")
    parser.add_argument("--project-directory", type=Path)
    parser.add_argument("--render", action="store_true",
                        help="Opt-in: run docker compose config --quiet using local environment")
    parser.add_argument("--format", choices=("json", "text"), default="text")
    args = parser.parse_args(argv)
    outcome = inspect_source(args.file, project_directory=args.project_directory,
                             render=args.render)
    if args.format == "json":
        print(json.dumps(outcome, indent=2, sort_keys=True))
    else:
        print(outcome["status"] + " (files checked: " + str(outcome["checked_files"]) + ")")
        for code in outcome["blockers"]:
            print("  " + code)
        print("READ-ONLY; source check is never an update authorization")
    return 0 if outcome["status"] != "BLOCKED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
