"""Portable, optional release-management contract validation.

These fields route agent workflows; they never authorize Docker mutation.
"""
from __future__ import annotations

STRATEGIES = {"upstream_managed", "project_managed", "externally_managed"}
AUTHORITIES = {"upstream_project", "application_project", "deployment_project", "external_admin"}


def validate_release_management(service: dict, *, class_field: str) -> list[str]:
    cfg = service.get("release_management")
    if cfg is None:
        return []
    name = service.get("name", "<unnamed>")
    if not isinstance(cfg, dict):
        return [f"{name}: release_management must be a mapping"]
    errors = []
    required = {"strategy", "release_authority", "version_monitoring", "automatic_updates"}
    if missing := required - set(cfg):
        errors.append(f"{name}: release_management missing {', '.join(sorted(missing))}")
    strategy = cfg.get("strategy")
    authority = cfg.get("release_authority")
    if strategy not in STRATEGIES:
        errors.append(f"{name}: unsupported release_management.strategy")
    if authority not in AUTHORITIES:
        errors.append(f"{name}: unsupported release_management.release_authority")
    if not isinstance(cfg.get("version_monitoring"), bool):
        errors.append(f"{name}: release_management.version_monitoring must be boolean")
    if not isinstance(cfg.get("automatic_updates"), bool):
        errors.append(f"{name}: release_management.automatic_updates must be boolean")
    cls = service.get(class_field)
    if strategy == "project_managed":
        if cfg.get("version_monitoring") is not False:
            errors.append(f"{name}: project_managed disables unsolicited version monitoring")
        if cfg.get("automatic_updates") is not False:
            errors.append(f"{name}: project_managed cannot enter update-auto")
        if cls not in {"MANUAL", "NO_TOUCH"}:
            errors.append(f"{name}: project_managed requires MANUAL or NO_TOUCH policy")
        if authority in ("external_admin", "upstream_project"):
            errors.append(f"{name}: project_managed release requires an application/deployment owner")
    if strategy == "externally_managed" and cfg.get("automatic_updates") is not False:
        errors.append(f"{name}: externally_managed cannot enter update-auto")
    return errors
