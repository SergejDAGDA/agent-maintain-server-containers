# Disposable Docker/Compose integration harness — implementation specification

**Status: proposed acceptance criteria; no harness or mutation executor is implemented by this document.**
Baseline: v0.2.0 currently has synthetic policy/unit tests and a read-only CLI. The first harness PR should create a **strictly disposable** runtime test environment, not turn `maintenance.py` into a Docker mutator.

See [roadmap](ROADMAP.md) and [lifecycle/recovery design](LIFECYCLE-RECOVERY-DESIGN.md).

## Purpose and trust boundaries

Make real Docker/Compose behavior, backup/restore safety and lifecycle failure modes testable in CI without touching production, using **invented test data only**.

- No real application data, credentials, IPs, host paths, names, mount identities, databases or saved Docker state in committed fixtures.
- Use GitHub-hosted ephemeral Linux runners or an equivalently disposable dedicated runner. Never require a developer's live Docker daemon or any production-connected self-hosted runner.
- No SSH, production inventory, cloud access keys, private backup repositories or deployed consuming-project Compose files.
- Use a fresh, collision-resistant Compose project prefix and ownership labels. Every mount, container, network, image artifact and disposable volume must be attributable to the test run.
- Protect host/runtime scope: no host `docker.sock` inside fixture services, no host networking, no privileged containers, no broad host bind mounts, no production volumes, no `down -v` against anything except an independently verified fixture-owned project.
- Restrict network exposure and outbound access during test execution; use local synthetic dependencies. Docker image pulls in the preparation phase must use reviewed/pinned references and normal CI supply-chain rules.
- Keep synthetic tokens deliberately non-sensitive. Do not inject real secrets through CI variables or persist env dumps as artifacts.
- Report only test IDs, synthetic fixture identities, stage results and redacted diagnostic reasons.

## Test tiers and CI gates

| Tier | Trigger | Requires Docker | Signal |
| --- | --- | --- | --- |
| A: unit, schema, CLI security | Every PR | No | Fast static/contract FAIL/PASS; retain existing 125-test baseline as historical, not fixed test count |
| B: disposable Compose integration | Every relevant PR once harness exists | Yes; ephemeral runner | Runtime topology, lifecycle fixture, mount/identity and isolated cleanup checks |
| C: backup/restore and fault injection | Separate gated PR/release job or bounded matrix; expand to PR as runtime allows | Yes; ephemeral runner and disposable repository | Coherent restore, fault and state-protection proofs for *synthetic* fixtures only |

Do not combine these into an unqualified green 'safe for production' badge. No privileged Docker-in-Docker setup should be added simply because it is convenient: start with the runner's normal Docker/Compose capability, and justify any isolated engine separately.

## Initial fixture catalog (100% synthetic)

**F1 — SQLite + user attachments:** one application container, writable DB/volume, WAL mode and referenced attachment files. Generate linked artificial IDs and blobs. No actual Vikunja or private service data.

**F2 — DB + worker + dependency alias:** application and worker with a PostgreSQL (or an equally reviewed local DB) backing service. Explicit atomic group and single owning policy record for multiple Compose services; exercise exact and ambiguous identity handling.

**F3 — external-style object store:** a local dummy S3-compatible fixture or purpose-built object-store emulator with unique synthetic files. Separate state ownership and recovery proof; no external network credentials.

**F4 — disposable scratch versus protected state:** temporary workspace alongside non-disposable execution/history data to demonstrate that names like `/tmp` or 'cache' do not authorize deletion.

**F5 — migration-sensitive release pair:** synthetic schema v1/v2 with a deliberately backward-incompatible migration. Verify that image-only rollback is blocked and requires separately authorized state-aware recovery.

Each fixture needs an immutable synthetic release identity, declared recovery set, expected smoke predicate and an inventory of resources safe to destroy in teardown. Fixtures must not assume an application name alone establishes a dependency group.

## Required scenario/acceptance matrix

| ID | Scenario | Pass condition |
| --- | --- | --- |
| H01 | Provision isolated fixture F1 | Only fixture-owned resources created; healthy/smoke state and all expected DB+file references exist |
| H02 | Capture backup checkpoint | Snapshot describes exact DB+files+source identity, consistency method, timestamp, non-secret key-recovery reference and protected metadata |
| H03 | Restore F1 in separate namespace | Restore reconstructs SQLite rows and linked attachments; application smoke passes; original fixture unchanged |
| H04 | Synthetic update v1 -> v2 | Revalidated immutable target, bounded group and state/health identities; journal records actual changes |
| H05 | Interrupted update / process crash | Resume or abort is deterministic, no duplicate migration or silent overwrite; previous protected checkpoint remains available |
| H06 | Incompatible migration followed by failure | No image-only downgrade onto new schema; block with `RECOVERY_REQUIRED` until separately verified recovery path |
| H07 | Missing or invalid restore key/secret reference | Restore-test blocks with redacted message; no secret values leaked; working snapshot not pruned |
| H08 | Corrupt or partial archive / backend unavailable | Capture/integrity/restore stage fails closed; update not executed; protected checkpoint retained |
| H09 | Stale plan, ambiguous identity or modified mount | Pre-mutation revalidation denies mutation, even when initial policy validated |
| H10 | MANUAL / NO_TOUCH / externally owned dependency | Broad update/cleanup scope excludes these and cannot gain eligibility via adapter PASS |
| H11 | Retention/prune simulation | Dry-run identifies exact checkpoints; protected last-known-good and active pre-migration/recovery snapshots never deleted |
| H12 | Decommission fixture | Runtime removal leaves DB/user files/backups intact; explicit separate destructive approval is required to purge synthetic state |
| H13 | Concurrent action and retry | Scoped locks and idempotent operation IDs prevent overlapping/app-wide or double-applied mutations |
| H14 | Logs and report redaction | Sentinel secrets embedded in deliberately malformed synthetic policies do not surface in CLI text/JSON, CI logs or reports |
| H15 | Teardown and namespace isolation | All and only fixture-owned resources removed; no residual test volumes/networks, no cross-project impact |

H04-H13 depend on future executor/backup modules. The **first harness PR** should establish safe plumbing and implement executable F1/H01, resource inventory, H15 and a basic F1 restoration smoke using a temporary local archive/provider only as a *test fixture*, without claiming B02/B03 production backup support. Other rows initially remain explicit `NOT_IMPLEMENTED` in the roadmap; do not report unimplemented tests as PASS or mark CI green for skipped safety requirements.

## Initial harness PR: narrow delivery contract

Create only:

1. A dedicated `tests/integration/` directory containing Compose fixtures, invented seed data generation, bounded orchestration helpers and explicit cleanup checks.
2. A documented local command or script that **refuses execution unless** an ephemeral test-runner safety marker and isolated Docker context are verified. Default should be dry-run or refuse; no implicit access to a developer's default live Docker daemon.
3. One CI job using ephemeral runner isolation, timeouts, resource limits and a unique fixture namespace. Docker-integration tests must be independent of the ordinary unit job.
4. Executable positive F1/H01 and H03 (basic synthetic SQLite+attachment restore), plus negative scope H10/H15 or an equally small evidence-rich initial set. Keep absent executor behaviors marked as not yet testable.
5. Captured proof that teardown ran both after success and simulated failure, without global Docker prune or accidental deletion of foreign resources.
6. A short harness README explaining how to operate it safely, how artifacts are redacted, and why passing tests are not production-recovery assurance.

No changes to project-host policies, source-of-truth deployment records, installed skills, production backup configuration, public release metadata or unrelated agents.

## Suggested stage flow for one test run

1. **Preflight:** verify runner is ephemeral/approved, Docker context is the test context, Compose plugin present, no credential-dependent target, namespace unused.
2. **Build/prepare:** obtain only pinned fixture images, generate random synthetic IDs and local dummy data, create separate fixture storage under run-owned sandbox.
3. **Start:** validate fixture Compose, inspect effective services/mounts/ports for forbidden privileges, host binds and unexpected external exposure **before** running.
4. **Exercise:** seed synthetic SQLite WAL + artificial attachments; collect baseline hashes and row/file associations; run health smoke.
5. **Checkpoint:** generate temporary test snapshot with DB-consistent mechanism and fake key/metadata, never raw production backup code.
6. **Recover:** restore to an isolated second Compose project, verify schema/rows/attachments/smoke, compare identities expected to persist and those expected to change.
7. **Fault exercise:** simulate a bounded failure and confirm isolation, journal/error reporting and checkpoint preservation as the feature exists.
8. **Cleanup:** always run fixture-scoped teardown, verify only labeled/owned resources are removed; on partial cleanup stop and report residue rather than using broad prune.
9. **Report:** publish per-scenario PASS/FAIL/BLOCKED/NOT_IMPLEMENTED; discard invented file contents and container env.

Any failure in resource isolation, host identity/context, cleanup eligibility, backup/restoration completeness or secret redaction fails the harness. Do not suppress errors to force green CI.

## Backup test specifics and pitfalls

- For SQLite WAL, **do not copy only the main database file** from a live writer; use an appropriate application-consistent backup procedure. Test a linked attachment set captured at a compatible point in time.
- For PostgreSQL fixtures, use an explicit validated dump or other consistent snapshot/restore procedure; attaching an unchecked live data directory is insufficient.
- A backup provider's `check` or repository integrity result is **not** the same as successful isolated restore plus business-level smoke.
- Old checkpoint retention must survive new incomplete checkpoints and destructive failures. `forget/prune` must be separately scoped, reviewed and dry-run first.
- A backup on the same test host is acceptable **only for synthetic CI restore tests**, not as a recommended real disaster-recovery design. Production design must support independent/off-host fault domains.
- Filesystem binary artifacts can move into databases or external object stores. Fixture representations must not invent a filesystem path to satisfy legacy validators.
- Prior migrated state must not be silently paired with an older incompatible image.

## Required CI review evidence

For a harness implementation PR, report:

- exact changed files, fixture inventory, Docker/Compose runner provenance and ownership boundary;
- unique project and volume labels, prohibited mount/privilege checks, CI job timeout and cleanup verification;
- number of executed, passed, blocked and intentionally not-yet-implemented tests by tier;
- proof of synthetic database+file restored in isolation and unchanged original;
- negative tests demonstrating denied scope and preservation of known-good checkpoints;
- sanitized logs and checks that no secret-like synthetic markers are echoed;
- compatibility with unchanged v0.2.0 read-only CLI and policies.

A one-off terminal demonstration is not acceptance: the automated CI job must execute the same checks on a fresh disposable runner.
