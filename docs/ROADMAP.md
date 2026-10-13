# Docker application lifecycle: development roadmap

**Status:** design proposal / backlog, not implemented functionality.
**Baseline:** `maintain-server-containers` v0.2.0 (released 2026-10-12).
**Scope:** generic, reusable Agent Skill and future bounded executor. No real service inventory, deployment credentials, backup data, or consuming-project configuration belongs here.

## Audit checkpoint (2026-10-13)

See [security and architecture audit](SECURITY-ARCHITECTURE-AUDIT-2026-10-13.md)
for the current source-level assessment of the roadmap. PRs through #20
established real **disposable synthetic CI** restore/fault exercises and
experimental signed storage-evidence contracts, not a production provider,
protected independent authority, installed-skill attestation or mutation
executor. E01–E04 and D01 remain open. Do not infer completion of this
roadmap from green H31 tests.

## Goal and boundaries

Provide an evidence-driven, repeatable lifecycle for Docker Compose applications:
**discover / adopt -> install -> verify -> maintain -> update -> checkpoint -> restore or rollback -> decommission**.
An application may own multiple Compose services and one coordinated recovery set.
Automatic actions must be limited to a reviewed, revalidated plan; a declaration, a runtime observation, a verified restore, and execution authorization are **different facts**.

Existing v0.2.0 offers agent-operated runbooks, a read-only `validate/audit/status/plan` CLI, strict policy classes and dependency-group checks, and a trusted opt-in `safety-adapter/v1` contract. **It does not provide a tested Docker mutation executor, backup provider, production restore engine, unattended updates, or safe automatic deletion.** A passing unit or schema test cannot establish those capabilities.

Supporting design documents:

- [Lifecycle and recovery contracts](LIFECYCLE-RECOVERY-DESIGN.md)
- [Disposable integration test harness acceptance specification](DISPOSABLE-TEST-HARNESS.md)

## Prioritized backlog

Items are proposed, not promised or released. Assign version numbers only when implementation PRs are scoped and accepted.

| ID | Priority | Area | Deliverable / acceptance condition |
| --- | --- | --- | --- |
| C01 | P0 | State terminology | Define persistent state, user/binary artifacts, recoverable databases, managed disposable caches and temporary workspaces; unknown never silently becomes an empty inventory. |
| C02 | P0 | Typed storage | Optional versioned storage semantics (memory, database, filesystem, object storage, container filesystem), linked recovery scopes and provenance; legacy v0.2.0 policies retain fail-closed behavior. |
| C03 | P0 | Trusted project entry point | Consuming projects register their own trusted adapter via reviewed code and independent identity/source pins; policy data cannot choose executable imports. |
| C04 | P0 | Evidence | Distinguish DECLARED, OBSERVED, VERIFIED, RESTORE_TESTED and ELIGIBLE, including sources, freshness and invalidation; runtime metadata parity is not recovery evidence. |
| B01 | P0 | Recovery-set contract | Enumerate Compose/source identity, image digests, volumes/binds, databases, files, external stores, key-recovery responsibility and exclusions. |
| B02 | P0 | Backup adapters | Compare maintained OSS providers (for example Restic, Kopia, Borg) via a requirements matrix and record an ADR; no new proprietary backup format. |
| B03 | P0 | Consistent capture | Test DB-aware snapshots (including SQLite/WAL and PostgreSQL), related files and atomic recovery groups; archive success alone cannot pass. |
| B04 | P0 | Release checkpoints | PRE_DEPLOY, PRE_UPGRADE, PRE_MIGRATION, PRE_DECOMMISSION, POST_VERIFIED_RELEASE and SCHEDULED_RECOVERY have immutable identity and protection rules. |
| B05 | P0 | Isolated restore | Restore synthetic database + user files in an isolated disposable environment and verify integrity and application smoke. |
| B06 | P0 | Retention and deletion | Event-linked protected history plus configurable scheduled/GFS-style retention; dry-run and separate authorization for destructive prune. |
| T01 | P0 | Disposable test harness | PR-runnable isolated Compose scenarios with synthetic data and bounded resource ownership, no production daemon/configurations. |
| T02 | P0 | Fault injection | Cover stale plans, interrupted upgrades, corrupt or incomplete backups, missing keys, migration failures, partial groups and storage outages. |
| T03 | P1 | CI tiers | Distinct unit/contract, disposable integration and restore/migration signals; no misleading production safety assertion. |
| E01 | P1 | Typed deterministic executor | ActionPlan -> prepare -> revalidate -> authorize -> execute -> observe -> record; scopes, locks, idempotency, resumption and abort behavior are tested. |
| E02 | P1 | Lifecycle actions | `adopt`, `deploy`, `update`, `rollback`, `decommission` with explicit separation of runtime removal from user-data/backup destruction. |
| E03 | P1 | Operational records | Reconcile project-owned deployment records without inventing a parallel ledger; detect drift and record only actual mutations. |
| E04 | P1 | Approval and isolation | Enforce AUTO_SAFE, AUTO_GATED, PIN_ONLY, MANUAL, NO_TOUCH, trusted adapters, expiry and action/scope-bound approval. |
| D01 | P1 | Skill packaging | Independent installed-tree version/source/digest attestation, reproducible package tests, safe skill upgrade/rollback. |
| D02 | P1 | Documentation | Keep public CLI capabilities distinct from agent workflows and future executor operations; document backup and decommission. |

## Required implementation sequence

1. **Design-only PR:** review state/recovery terminology, lifecycle state machine, evidence, backup interfaces and test acceptance. No runtime mutations.
2. **Harness PR:** disposable Compose fixtures, CI isolation, synthetic seeds, teardown verification, safety failures and no-real-data checks. No production executor.
3. **Storage/evidence PR:** optional typed schema with explicit backward-compatibility and fail-closed tests.
4. **Backup provider PR:** ADR-backed OSS integration, inventory, synthetic checkpoint creation, consistency and idempotency checks.
5. **Restore PR:** isolated recovery tests, immutable/protected checkpoints, retention and dry-run deletion.
6. **Executor PR:** only sandbox `adopt/deploy/update` first; revalidation, approval, locks, journal and recovery states before any production claim.
7. **Decommission PR:** staged runtime removal; data destruction requires separate explicit authorization and tested backup continuity.
8. **Pilot:** one *disposable, wholly synthetic* managed app completes the lifecycle, then a separately authorized limited live adoption can be considered.

Progress must be evidenced by reviewed PRs and tests. Do not treat a design document, passing unit suite or a single successful live deployment as general executor certification.

## Cross-cutting non-negotiable gates

- **Fail closed:** unresolved ownership, dependency membership, state, migration, trusted adapter or recovery proof blocks mutation; no automatic eligibility promotion.
- **No silent data replacement:** mounts, volumes, database schemas, encryption identities and external store ownership remain within an explicit recovery contract.
- **No destructive shortcuts:** forbid broad `prune`, `down -v`, anonymous-volume substitution, unreviewed `latest` changes and implicit state rollback.
- **Immutable target + fresh plan:** compare source, image IDs, relevant Compose/mount topology and evidence immediately before mutation; drift invalidates authorization.
- **Backup != restore:** archiving, provider integrity checks, isolated restoration and successful application smoke are separate statuses.
- **Protected history:** the last independently restore-tested working checkpoint and any active/pre-migration recovery point cannot be silently pruned. Scheduling cadence and retention are project policy, not global defaults.
- **Least privilege and privacy:** no secrets, private configuration, real customer content or production snapshots in public tests or reports.
- **Independent backup domain:** an on-host copy alone cannot mitigate host/disk loss; support off-host or otherwise independent protected storage.

## Release-level definition of done

- **Automated updating** needs verified eligibility, reproducible target, current backup/restore evidence, migration and rollback handling, fresh plan, scoped execution, smoke and durable mutation report.
- **Backup** needs an application-consistent synthetic recovery set restored into an isolated environment, not merely an archive or checksum.
- **Decommission** must leave all user state and backups intact by default. Destructive state/backup deletion is a separate scope-reviewed operation.
- **Universal** means the same generic interface passes positive and denial scenarios across multiple synthetic persistence backends without adding consuming-project specifics to this repository.

## Non-goals for this document

No operational change to an existing server, no upgrade of the installed v0.2.0 skill, no provider selection without comparison, no new policy fields enforced in v0.2.0, no release/version promise and no replacement of existing private operational records.
