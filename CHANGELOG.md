# Changelog


## 0.2.0 - Unreleased

- Add `deploy-project <project> [release-id]` as an agent-operated,
  explicitly authorized project-owned release deployment workflow.
- Support local/private application release authority independent of
  public upstream version monitoring.
- Add optional validated `release_management` routing in both policy formats.
- Coordinate post-deploy operational records, `maintain-project-memory`
  Checkpoint and targeted `project-documentation` update without new handoffs.
- Enforce existing MANUAL, NO_TOUCH and external ownership restrictions.
- Synthetic policy fixture and regression tests.
- Harden invalid external inputs: malformed group identities/dependencies and Docker inspect metadata now return explicit errors/unverified rather than crashing; unknown top-level global safety invariants fail validation.
- Prevent malformed optional release-management values from triggering type errors in either policy schema.
- Fix fail-closed regressions: forbid empty collections as backup/rollback/smoke identity evidence, while allowing explicitly empty state inventories; reject unsupported security invariants before live checks; stop all portable-policy live inspection if validation fails.
- Validate selective Docker metadata types, reject unapproved host/container networking and spoofed Docker socket sources; cover both with synthetic regression tests.
- Enforce per-service extended-policy safety semantics (state, migration, rollback, backup, topology and health), and compare only selected read-only Docker metadata. Distinguish metadata parity from proof of a safe deployment.
- Define a portable deployment record discovery/reconciliation contract and local project integration checklist.
- This is an agent workflow, **not a bundled Docker mutation executor**.
- Add bounded `deploy-repository` agent workflow for first-time installation of external Git repositories, including trust, privileges, network exposure, persistent state, secrets, dependency validation and policy adoption.
- Clarify that core deployment and operational records are standalone; `maintain-project-memory` and `project-documentation` integrations are optional, never required.

## 0.1.0 - 2026-10-12

- First public preview of the portable `maintain-server-containers` Agent Skill.
- Codex/Claude compatible packaging with a single canonical skill body.
- English and Russian user documentation.
- Versioned portable policy v1 and read-only validator, audit, status and plan CLI.
- Read-only adapter for richer namespaced project maintenance v1 policies, including policy classes, composite Compose identities and dependency groups. The original project policy is never rewritten.
- Explicit logical-to-Compose `component_aliases` for composite update groups, with fail-closed validation of unresolved or contradictory members.
- Agent-operated bounded maintenance and rollback runbooks.
- Synthetic regression tests and GitHub Actions checks.
- Explicit distinction between the read-only helper and an unimplemented deterministic update executor.

### Current limitations

- No production mutation executor is bundled in this version.
- Project-specific policy adapters, verified backup/restore and application-level smoke tests remain the responsibility of each consuming project.
- Upstream latest-version discovery is an agent workflow, not a live feature of the read-only CLI.
