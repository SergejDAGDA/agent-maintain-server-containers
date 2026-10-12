# Experimental recovery-set evidence contract

**Status:** draft and automated CI contract only. Not a deployed backup manager, Docker executor, stable API, or new v0.2.0 policy schema. See [roadmap](ROADMAP.md), [lifecycle design](LIFECYCLE-RECOVERY-DESIGN.md), and [Restic fixture ADR](ADR-001-DISPOSABLE-RESTIC.md).

Source: `skills/maintain-server-containers/scripts/recovery_contract.py`. It uses only Python's standard library; no connection to Docker, Restic, storage backends, SSH, secrets or cloud APIs.

## What this contract distinguishes

1. **Recovery-set declaration:** precisely identified application, Compose source digest, immutable image digests, typed assets (database, volumes, filesystem, object store and external key-recovery reference), documented consistency method. `validate_recovery_set` generates a canonical SHA-256 fingerprint for a valid declaration. A hash proves **declaration identity**, not the integrity of underlying data.
2. **Checkpoint evidence:** immutable provider snapshot ID tied to that fingerprint, event class, full capture flag, repository check flag, isolated restore check flag and successful application smoke. `RESTORE_TESTED` requires all actual checks; a syntactically complete declaration is insufficient.
3. **Retention dry-run:** no deletion occurs. `plan_retention_dry_run` rejects unknown/malformed IDs, mismatched recovery fingerprints, missing recovery tests and incomplete inventory. Independently verified snapshots, pre-migration/pre-decommission checkpoints, active rollback references and legal/manual holds are protected.

Strictly separating **declared**, **captured**, **repository checked** and **restore tested** avoids making 'backup exists' interchangeable with 'application can recover'.

## Example (invented values only)

```python
from recovery_contract import validate_recovery_set, validate_checkpoint, plan_retention_dry_run

declared = {
    "schema": "recovery-set/v1",
    "application": "artificial-demo",
    "compose": {
        "project": "isolated-fixture",
        "source_digest": "sha256:" + "a" * 64,
    },
    "images": {"app": "sha256:" + "b" * 64},
    "assets": [
        {"id": "sqlite", "kind": "database", "backend": "sqlite",
         "consistency": "sqlite_backup_api",
         "reference": "logical-test-database", "recovery_required": True},
        {"id": "uploads", "kind": "user_files", "backend": "filesystem",
         "consistency": "snapshot_quiesced",
         "reference": "artificial-attachments", "recovery_required": True},
        {"id": "key-authority", "kind": "secret_reference",
         "backend": "external_reference", "consistency": "immutable_reference",
         "reference": "approved-key-source", "recovery_required": True},
    ],
}
result = validate_recovery_set(declared)
assert result.valid
```

**This sample is not runnable backup execution.** Checkpoints are evaluated only after a separate provider has produced and independently verified real proof. Never set the booleans to `True` merely to satisfy validation. An attacker-controlled checkpoint document cannot self-attest a restore test: a future trusted executor must bind those fields to independently captured evidence and approved verification authority.

## Supported failure handling

- Invalid asset type, duplicate identity, unknown consistency method, unproven required state or absent external key-recovery responsibility -> invalid recovery-set declaration.
- Missing/restored-without-check/negative smoke/foreign recovery fingerprint -> not restore-tested; contradictory proof -> invalid checkpoint.
- Any unknown retention target, invalid checkpoint inventory, missing restore-tested reference or unauthorized class -> no automatic candidate deletion.
- All successfully restore-tested points are conservatively protected because the experimental contract has **no trusted timestamp, replacement-proof or independent removal authorization yet**.
- `permitted_candidates` are advisory candidates for a *future* separately approved deletion plan; they are **not permission to delete**. There is no deletion function.

## Currently tested with Restic

The GitHub-hosted disposable integration runner uses a synthetic SQLite application with three artificial attachments. It prepares a consistent checkpoint using SQLite's backup API, captures it into an encrypted local Restic repository, validates the exact snapshot ID and repository contents, restores into a fresh project and runs application smoke. The harness then produces a provider-neutral checkpoint evidence declaration and confirms that retention does **not** consider the only verified working checkpoint deletable.

See `tests/integration/harness.py` and `tests/test_recovery_contract.py`. This proves a synthetic CI recovery set, **not** a live or remote Docker recovery guarantee.

## Important future gates

- A production implementation must independently verify evidence, record timestamps/freshness, failure domains, storage ownership, secrets authority and application-consistent DB capture.
- Support off-host/immutable backup destinations, repository access controls and emergency key recovery.
- Define retention holds and legal constraints with an independently authorized deletion workflow (with dry-run and restored replacement), never blindly call `restic forget --prune`.
- Determine coherent capture of databases + user files under concurrent writes, grouped Compose services, external object stores, PostgreSQL, and restore compatibility across migrations.
- Version the resulting stable contract and plugin manifests together at release time. Merely landing source on `main` does not automatically update installed skills.

The current shipped `maintenance.py` remains read-only.
