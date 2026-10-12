# Deploying application-project releases

This is the **agent-run** workflow for `deploy-project <project>`. The bundled Python CLI remains read-only and does **not** implement a production deployment executor. It is intended for local, private, self-hosted or otherwise project-managed applications whose approved release may be outside a public registry.

## Separate ownership and authority

- **Application project** owns source, approved release/build, application migration and verification contracts, and maintained product documentation.
- **Deployment project** owns Compose topology, runtime configuration, backup/recovery boundaries and an operational deployment record.
- **Project memory** indexes verified project state and decisions, but is not the authoritative build artifact or runtime record.
- **Documentation** tracks implementation and release-related behavior, not operational handoff or project-memory history.

`project_managed` is a release strategy, **not another update-safety class**. It cannot turn `NO_TOUCH`, `MANUAL` or externally owned projects into `AUTO_SAFE`. A project with `MANUAL` requires a targeted, explicitly approved application deployment workstream; it remains excluded from `update-auto`. An ordinary `deploy-project` request does **not** override `NO_TOUCH`, which requires its own distinct expressly authorized workstream before any mutation. External/unknown ownership requires appropriate external authority.

## Invocation and authorization

`$maintain-server-containers deploy-project <project> [release-id]`

Select an existing **approved deployable** release, never merely the highest Git commit, latest local working tree or newest image tag. The project may publish source outside the server, use a private Git repository, CI build, local package or other accessible release source. If multiple releases fit, ask for the release identity once.

One user request for a named project and release authorizes the bounded expected deployment sequence and records synchronization for that project, subject to its project policies and host permission prompts. Do not ask per-step confirmations for normal backup/pull/build/recreate/health/smoke/safe rollback actions inside the approved scope. Stop at an expanded scope, changed network exposure, uncertain release identity, unapproved migration, destructive recovery or denied project ownership.

## Evidence contract — not a new mandatory handoff file

Discover existing authoritative records before creating anything:

1. Application root and deployment root, established from project instructions, not guessed from container names.
2. Approved release identity, source revision and immutable artifact digest or reproducible build provenance.
3. Validated deployment source and any applicable persistent Compose override (including its durable location).
4. Exact service/group scope, dependency compatibility, topology contract and environment secret **references** (never values).
5. Data/schema migration plan, backup freshness and **restoration evidence** appropriate to the persistent state.
6. Application-specific read-only smoke and state-identity tests.
7. Deployed runtime identity and previous immutable rollback identity.

Accept verified release records, CI attestations, immutable tags/digests, project-owned deployment manifests or equivalent existing evidence. No new `HANDOFF.md` or duplicate release metadata file is required. A release descriptor is optional, although useful for projects without an established deployment interface.

A memory file stating "ready" cannot replace a build/CI acceptance record. A Git `HEAD` may be ahead of the released revision because documentation and other work continued. A Compose image tag is not immutable proof of the running build.

## Deployment phases

**A. Discover and freeze:** Read both projects' instructions, project memory as context, actual release/build records, active Compose source stack and runtime identities. Validate installed supporting skill freshness before planning any of its writes. If a runtime-labeled Compose override is missing, do not deploy until a reproducible active source is established. Do not overwrite unrelated application code or read raw environment secrets.

**B. Validate:** Confirm the targeted project has authorized deployment ownership. Keep `MANUAL` out of generic update waves; refuse `NO_TOUCH` without a separate explicitly scoped workstream. Verify complete persistent-state contract, current compatible backup, isolated restoration evidence, migration and rollback limitations, and Compose topology parity. Do not accept a restic archive integrity check as proof of a database-consistent restore.

**C. Apply:** Stage the exact approved release, preserve the previous immutable runtime/source and a durable copy of the effective deployment inputs, then apply only the approved Compose group. Any generated release override must be durable and reproducible, not an ephemeral temporary file. Treat each stop/start/recreate/restart as a runtime mutation.

**D. Verify:** Observe health/stability; run application-owned smoke and state checks; compare mounted volumes, account state, uploads, configuration/instance identity and runtime IDs. Only perform automatic rollback when image/source rollback is proven safe for the actual migrated state. If state-aware restoration would be required, stop with `RECOVERY_REQUIRED` instead of forcing old code onto new data.

**E. Record only what happened:** Once runtime verification passes, write or update the deployment owner's existing authoritative deployment record with approved release identity, source revision, artifact/image digest, Compose source identity, actual runtime identities, timestamp, smoke checks and recovery references. Do not create a competing ledger when the project already has one.

Read [deployment-record.md](deployment-record.md) for the optional adapter interface, durable operational identity and a precise revalidation-based recovery path for `DEPLOYED_RECORD_SYNC_PENDING`. Its record example is not a required new file or replacement for the project's existing schema.

## Project memory and documentation synchronization

Successful deployment is a meaningful **Checkpoint**, not a new active Handoff:

- Server-side project: use the installed `$maintain-project-memory` **Checkpoint** under its own protocol to record verified operational state, if installed/current and project rules allow. Do not store application architecture or source authority in server memory.
- Application project: use its own project-memory lifecycle, root and approved write policy to record the verified deployed release. Never copy canonical project memory from one project root to another. A separate application-project checkout and write permission may be needed.
- If the release affected user-facing behavior or implementation documentation that is not already current, use `$project-documentation` **update** only for affected maintained files in the application's root. Do not rewrite READMEs merely because the deployment timestamp changed.
- Honor memory skill freshness and optimistic concurrency pre-write checks, along with each project's `notify`, `approve-decisions` or `strict` update policy. Do not silently approve decisions, overwrite active sessions, or treat a deployment as a newly approved architectural choice.
- These skills are optional integrations. If absent or blocked, report pending owner-scoped record actions and provide verified evidence; do not fabricate the skill or bypass a project's coordination contract.

## Partial failures

Deployment and cross-project documentation are **not atomic**. If runtime is verified healthy but record synchronization fails, report `DEPLOYED_RECORD_SYNC_PENDING` and the exact pending updates. Do not roll back a good runtime solely because a documentation or project-memory write failed. If deployment fails, distinguish `BLOCKED_BEFORE_MUTATION`, `FAILED_SAFE_ROLLBACK` and `RECOVERY_REQUIRED` and do not report success.

Report six operational mutation dimensions independently: application version, runtime/container, persistent user state, deployment source, network/access and database schema. Separately report application documentation, application memory and server memory as `UPDATED`, `UNCHANGED`, `PENDING` or `BLOCKED`. Label all evidence as independently verified, declared or not verified; never conflate historical receipts with current observation.

## Practical limits

This workflow does not autonomously execute upgrades via the bundled CLI, deploy all project-managed services during `update-auto`, override security boundaries, or install/update other Agent Skills. Without authorized access to the application source or proven release/restore evidence, stop before mutation and report the precise blocker. The same workflow is usable even if the agent starts in a new chat and has no memory of the application's development conversation.
