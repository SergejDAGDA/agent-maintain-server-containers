# Proposed lifecycle, state and recovery contracts

**Design-only proposal.** Nothing in this document changes v0.2.0 policy parsing, the shipped read-only CLI or authorization rules. JSON/YAML shapes below are **illustrative candidate interfaces**, not accepted schemas or runnable executor commands. See [roadmap](ROADMAP.md).

## 1. Managed unit and authority

A **managed application** is a project-owned deployment and coherent recovery boundary, potentially containing several Compose services. Model independently:

- **Application identity:** immutable management ID, ownership, runtime Compose project and services, source/release authority.
- **Dependency relationships:** required startup/runtime dependencies; do not equate these to atomic update membership.
- **Atomic operation group:** explicit named members and ownership aliases, only when updates/recovery really need one operation boundary.
- **Deployment authority:** project-owned Compose/runtime records; do not create competing truth files when authoritative records already exist.
- **State authority:** persistent and externally held data, version compatibility and applicable secret/key recovery responsibility.
- **Independent safety authority:** core rules plus reviewed, pre-registered consuming-project adapters. A policy may claim rules but must never load code.

Ownership classification (`AUTO_SAFE`, `AUTO_GATED`, `PIN_ONLY`, `MANUAL`, `NO_TOUCH`) remains independent from whether an app is inventoried or has passing unit tests. `NO_TOUCH` is excluded from broad inspection/mutation; scoped dedicated work requires distinct approval. External administration is not transferred by discovery.

## 2. State vocabulary (C01/C02)

| Term | Meaning | Default safe treatment |
| --- | --- | --- |
| Persistent state | Data/identity needed after recreate, upgrade or disaster | Recoverable, not disposable |
| User/binary artifacts | Uploads, generated execution assets or attachments in files, DB or object store | Persistent until retention and recovery requirements are explicitly established |
| Database | SQLite/WAL, PostgreSQL or equivalent transactional storage | Requires application-consistent recovery |
| Managed disposable cache | Specifically identified state proven safe to delete and regenerate within the given operation | Disposal allowed only within that proved boundary |
| Temporary workspace | Scratch or intermediate output; may be shared with stateful paths | **Not** automatically a disposable cache |
| Container writable layer | Mutable filesystem not necessarily mounted persistently | Its absence from mounts does not prove safe deletion |
| Volatile memory | In-process state; may contain non-reconstructible in-flight work | May need quiesce; not synonymous with managed cache |
| External storage | Database, queue or object store beyond Compose volume boundary | Must be inventoried with authority and recovery responsibility |
| Unknown | Missing or unverified state behavior, provenance or lifecycle | Blocks the affected mutation gate |

Legacy `unknown` remains unresolved. An explicit `[]` declares *no managed items of that field*, never 'not checked'. Documentation must define the **scope of each inventory**, so applications do not need to prove absence of every internal cache to declare their *managed recovery boundary*. But scope cannot conceal an unknown persistent data location.

Candidate **optional** `storage_semantics` item (pending design review, not legal v0.2.0 policy syntax):

```yaml
state_contract:
  storage_semantics:
    - subject: uploaded_user_files
      backend: database              # filesystem | database | memory | object_storage | container_fs | unknown
      persistence: persistent         # persistent | volatile | unknown
      recovery_required: true        # true | false | unknown
      reference: app-primary-db      # logical identifier only; never a secret
      evidence_ref: verified-record-id
```

Design constraints: validate known values and references; do not accept credentials or raw environment values; explicit unknowns/missing critical evidence block eligibility; legacy omission preserves v0.2.0 safety; no path invented when data resides in a database. Model retention separately from disposability; data may be prunable by application policy while still requiring recovery before prune.

## 3. Evidence levels and freshness (C04)

Do not collapse these distinct statements:

1. `DECLARED`: policy claims source, state, expected paths and required gates.
2. `OBSERVED`: read-only runtime/Compose metadata describes current identities and mounts.
3. `VERIFIED`: selected evidence, source provenance and contracts agree, with bounded scope and timestamp.
4. `RESTORE_TESTED`: a *specific recovery set* was restored into an isolated environment and passed data-consistency and application smoke.
5. `ELIGIBLE`: action-specific authorization **plus** fresh verified prerequisites, targets, backup, migration and rollback gates.

Each claim should carry source, immutable identities/digests where applicable, subject, scope, observation time, freshness policy and verification outcome. A checksum validates bytes, not application restoration. A restored database alone does not verify its linked attachments. An adapter `PASS` cannot override core state/migration gates.

Revocation rules: image/Compose/volume/database schema drift, changed storage backend, expired restore evidence, secret-recovery uncertainty, unresolved group membership or changed ownership invalidates the affected eligibility decision. `OBSERVED` can never automatically become `RESTORE_TESTED`.

## 4. Lifecycle state machine (proposal)

Separate **application lifecycle** from **operation attempt** and **recovery-checkpoint** states; one generic 'success' flag is insufficient.

| Lifecycle transition | Preconditions | On failure |
| --- | --- | --- |
| `DISCOVERED -> ADOPTED` | authoritative owner, reproducible source and scoped state inventory | remain `DISCOVERED/UNRESOLVED` |
| `ABSENT -> DEPLOYED` | approved immutable release, isolated resources, explicit first-install scope | `PARTIAL_INSTALL`; preserve potentially user-created state |
| `DEPLOYED -> UPDATED` | current plan, approved target, backups, safety/compatibility and smoke | `RECOVERY_REQUIRED` or previous confirmed state **only when rollback proven safe** |
| `DEPLOYED -> RECOVERY_VERIFIED` | isolated coherent restore-test of selected checkpoint | retain deployment; mark proof FAILED/UNVERIFIED |
| `DEPLOYED -> DECOMMISSIONED` | scoped decommission plan, checkpoint and runtime-only teardown | stop with partial state; never silently remove user data |
| `DECOMMISSIONED -> PURGED` | **separate explicit destructive** scope, retention/legal holds resolved, surviving restore proof where required | refuse; retain state/checkpoints |

The names above are **proposed** and not current CLI statuses. There must be durable `PREPARED`, `AWAITING_APPROVAL`, `EXECUTING`, `VERIFYING`, `COMPLETED`, `FAILED`, `RECOVERY_REQUIRED` attempt states, including a crash-consistent journal of which mutations actually happened. An attempt that times out after Compose recreation must not claim `COMPLETED`. Safe retry must use operation IDs and idempotency checks; never rerun a migration blindly.

## 5. Future typed ActionPlan and execution boundary (E01/E04)

Proposed phases: **plan -> prepare -> revalidate -> authorize -> execute -> observe -> record**.

A plan will need at least: unique operation ID, kind and exact service/group scope, owner/permissions, immutable current and target digests, Compose/source identity, expected mount/network/security changes, recovery set and latest valid checkpoint, database migration strategy, application-level smoke, rollback class, evidence hashes/freshness and explicit exclusions.

Only a separately implemented and tested executor may mutate Docker. It must:
- compare current metadata to plan identities immediately before each sensitive stage;
- acquire scoped application/group locks and reject concurrent conflicting operations;
- reject unknown/missing/malformed evidence or expanded scope;
- make authorization bound to action ID, set of targets, permitted effects and expiration;
- record actual mutations in project-owned deployment records, distinguishing version/runtime/state/network/schema changes;
- never perform state-aware restore without its own explicit approved procedure;
- stop in `RECOVERY_REQUIRED` if migration renders image-only rollback unsafe.

No automatic operation may broaden to `MANUAL`, `NO_TOUCH`, another Compose project, shared data/ports/networks or host-level changes because a dependency was discovered.

## 6. Backup/recovery contract (B01-B05)

A **recovery set** is the smallest complete, consistent set needed to recover the same application identity and user-relevant data:

- authoritative deployment manifest, resolved Compose identity, immutable release/image digests, required networking/dependencies;
- bind mounts and named volumes with stable volume identity and mount topology;
- DB state captured with DB-specific consistency procedures (SQLite and its WAL; PostgreSQL via reviewed backup/restore procedure);
- uploads, execution/binary data and external object-store assets within the recovery boundary;
- separately protected encryption/key recovery mechanism and any key-rotation identity, **without putting secret values in reports or public plans**;
- explicit exclusions justified as regenerable, and declaration of any unavailable or externally managed state.

A backup provider interface should offer typed `prepare`, `capture`, `list`, `verify_integrity`, `restore_to_isolated_target` and `describe_retention` actions. The actual provider selection requires an ADR comparing maintained OSS tools (e.g. Restic/Kopia/Borg) for encryption, incremental storage, restore, access isolation, cost and external stores. Do **not** create a proprietary archive/crypto engine.

A `capture` result is not sufficient for a `RESTORE_TESTED` proof. A proof must identify snapshot ID, recovery-set version, integrity result, consistency procedure, isolated restore environment, database+related file verification, application smoke, timestamp and privacy boundaries. Synthetic-only restore tests may run automatically in CI; handling real backups requires separate authorization and protected environments.

### Checkpoint classes and protection (B04/B06)

| Class | Event |
| --- | --- |
| `PRE_DEPLOY` / `PRE_UPGRADE` | Before an approved new release or in-place change |
| `PRE_MIGRATION` | Before possible irreversible schema or state change |
| `PRE_DECOMMISSION` | Before runtime removal/archival, with user state protected |
| `POST_VERIFIED_RELEASE` | After successful deployment and application smoke / requisite restore proof |
| `SCHEDULED_RECOVERY` | Between releases, according to an application-specific recovery point objective (RPO) |

Each checkpoint requires unique ID, exact source/image/state/Compose identities, timestamp, consistency method, provider/location, proof and retention status; IDs and protected records must not be overwritten.

**Protection/retention invariants:**
- Protect last-known-good **restore-tested** checkpoint, active rollback checkpoint, outstanding pre-migration checkpoint and any in-use recovery point.
- A newly created or verified-in-archive backup does not automatically supersede a previously restore-tested working checkpoint.
- A failed backup or restore test blocks the dependent mutation. Preserve the previous verified checkpoint and report the block.
- Support configurable event-based checkpoints plus scheduled/GFS-like history, without baking in fixed intervals or retention numbers.
- `forget/prune` is a separate destructive plan with dry-run, exact affected checkpoint IDs, holds, capacity/retention policy, recovery successor validation and explicit approval. Never prune based only on age or apparent duplication.
- Prefer an independent protected/off-host fault domain; a backup on the same disk alone does not protect against disk failure.
- Destruction of Docker runtime resources never implicitly deletes volumes, secrets, databases, user files or backups.

### Rollback and restoration

Image-only rollback is allowed only when a previously verified migration/state contract proves compatibility. A schema change may require **coherent state restoration** of database and associated files; such restoration is a separately reviewed destructive recovery process, not an automatic retry step.

Distinguish:
1. Archive exists.
2. Provider integrity verified.
3. Exact recovery set restored.
4. Application identity, database and file references validated.
5. Application functional smoke passed.

Only the appropriate combination can satisfy the action-specific restore gate. A broken or absent restoration path yields `RECOVERY_REQUIRED`, never optimistic success.

## 7. Decommission semantics

`decommission` must be staged: disable/revoke access as separately scoped, protect pre-decommission checkpoint, stop and remove only agreed runtime resources, preserve named volumes/binds and backups, record ownership and archive state. User-data purge is a separate named operation requiring independent explicit authorization, object-by-object scope, legal/retention hold checks and proof of surviving recovery options. Do not treat stopping an app as permission to delete its data.

## 8. Decisions still open

- Which provider(s) to adopt after OSS comparison and maintenance/supply-chain review.
- How optional state semantics are versioned and whether typed inventories link to existing `uploaded_user_files` fields or supersede them in a later schema.
- Which consistency methods and app-specific hooks are permitted and how they are sandboxed.
- How to express RPO/RTO and off-host storage without encoding credentials into policies.
- How to verify restored business data while keeping actual user datasets and encryption material private.
- Recovery proof freshness windows, explicit authorization grammar, approval expiry and role mapping.

These decisions belong to separate design/implementation PRs; none may be inferred or defaulted into production behavior by this document.
