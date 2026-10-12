# Changelog

## 0.1.0 - 2026-10-12

- First public preview of the portable `maintain-server-containers` Agent Skill.
- Codex/Claude compatible packaging with a single canonical skill body.
- English and Russian user documentation.
- Versioned portable policy v1 and read-only validator, audit, status and plan CLI.
- Agent-operated bounded maintenance and rollback runbooks.
- Synthetic regression tests and GitHub Actions checks.
- Explicit distinction between the read-only helper and an unimplemented deterministic update executor.

### Current limitations

- No production mutation executor is bundled in this version.
- Project-specific policy adapters, verified backup/restore and application-level smoke tests remain the responsibility of each consuming project.
- Upstream latest-version discovery is an agent workflow, not a live feature of the read-only CLI.
