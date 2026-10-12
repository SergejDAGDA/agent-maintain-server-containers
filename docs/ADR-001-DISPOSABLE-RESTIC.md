# ADR-001 — First disposable backup provider: Restic

**Date:** 2026-10-12
**Status:** Accepted **for synthetic CI proof only**. This is **not** a decision to replace or reconfigure any consuming project's existing backup system, and is not a production backup provider certification.

## Decision

Exercise real [Restic](https://restic.readthedocs.io/en/stable/) repositories on an ephemeral GitHub-hosted runner alongside our synthetic SQLite + linked-attachment fixture. Keep the generic recovery-set and evidence contract provider-neutral. This adds a provider-backed **test checkpoint** and isolated data restore; it does not expose a Docker mutation command or remote backup interface.

## Alternatives considered

| Requirement | Restic | Kopia | BorgBackup |
| --- | --- | --- | --- |
| Encrypted content-addressed backup / deduplication | Yes | Yes | Yes |
| Local test repository | Yes | Yes | Yes |
| Repository check and recoverability checks | `check --read-data`, then restore | `snapshot verify`, then restore | `check`, then archive extract |
| Supported snapshot/restore CLI | `backup --json` / `snapshots --json` / `restore <id> --target` | `snapshot create` / `snapshot restore` | `create` / `extract` |
| Remote destinations | Multiple documented repository backends | Multiple documented providers | Primarily local/SSH repository deployments |
| First integration tradeoff | Straightforward machine-readable snapshot identity and repository-check separation | Rich policies, more connection/configuration state | Strong local/SSH workflows, different archive/compatibility conventions |

Sources: [Restic quickstart](https://restic.readthedocs.io/en/stable/010_introduction.html), [Restic scripting](https://restic.readthedocs.io/en/stable/075_scripting.html), [Restic restore](https://restic.readthedocs.io/en/stable/050_restore.html), [Kopia quickstart](https://kopia.io/docs/getting-started/), [Kopia command list](https://kopia.io/docs/reference/command-line/common/), [Borg quickstart](https://borgbackup.readthedocs.io/en/stable/quickstart.html).

The alternatives remain viable; no portability decision is made beyond this initial CI provider. Before production support, evaluate repository compatibility/version pinning, threat model, remote access, access key protection, immutable/off-host copies, retention and legal holds, backpressure, simultaneous writers, disaster-recovery RPO/RTO and restore procedures.

## Required synthetic proof

1. Create a *new, unique* encrypted local Restic repository inside the runner-owned disposable sandbox, with a randomly generated CI-only password file (0600) outside the backup source.
2. Prepare the input recovery set with `sqlite3.Connection.backup` and a fixed, synthetic-only attachment inventory. **Restic alone does not establish DB transaction consistency.**
3. Back up the exact prevalidated recovery-set directory; capture and validate a **full immutable snapshot ID**, never `latest`. No source excludes.
4. Verify snapshot presence and run `restic check --read-data`, then restore into a **separate fresh directory**, validate file digests, SQLite integrity and linked synthetic rows, and pass the independent container smoke check.
5. Deliberately use an incorrect CI-only password to verify a blocked restore/list operation; ensure this does not damage the first restorable checkpoint.
6. Perform no retention deletion: **no** `forget`, `prune`, repository repair or global Docker cleanup. Full history retention and protected checkpoint deletion belong to a separate implementation and security review.
7. Fail closed on unknown nonzero Restic exit codes, missing `snapshot_id`, stale/malformed recovery paths, corruption or invalid target; do not leak paths, passwords or full CLI output to reports.
8. Keep the repository, password file and synthetic state only under `RUNNER_TEMP`; after a successful test, use bounded fixture cleanup. Failed tests may retain artifacts only until ephemeral runner destruction.

## Evidence distinctions

`CAPTURED` = backup command reported success with a specific snapshot ID.

`REPOSITORY_CHECKED` = Restic verified repository objects (including data when `--read-data`).

`RESTORE_TESTED` = *that snapshot ID* restored to a separate directory and SQLite + attachments passed semantic checks and fresh Compose service smoke.

Neither `CAPTURED` nor `REPOSITORY_CHECKED` alone authorizes application update. A synthetic `RESTORE_TESTED` result proves the fixture, not real backup consistency, external stores, encryption key recovery, migration safety, production restore capability or unattended updating.

## Rollout

- Implement behind CI-only fixture code; current production-facing `maintenance.py` remains read-only.
- A future provider-neutral contract can map `prepare/capture/list/check/restore`, but must carry scoped state and provenance and keep destructive retention a separate authorization.
- Stop at this synthetic proof before adding PostgreSQL, object storage, off-host repositories or real Docker volumes.
