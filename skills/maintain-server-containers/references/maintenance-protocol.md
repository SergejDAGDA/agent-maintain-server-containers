# Evidence-based maintenance protocol

## Discovery before policy

Inventory the Compose project, service names, images and resolved image IDs, configured restart/health, mount sources/destinations and flags, published ports/interfaces, networks, shared dependencies, stateful services and deployment file ownership. Mark a service as UNKNOWN if source-of-truth is unclear. Do not infer "stateless" from small image size or an empty visible directory.

## First practical audit: source and toolchain readiness

Run the installed `scripts/doctor.py` with the **same interpreter**
chosen for `maintenance.py`. A successful installation of an Agent Skill
is not evidence that PyYAML exists in each environment. A missing PyYAML
package blocks the YAML validator, but it does **not** justify installing
packages on a server during a read-only audit. Use an existing trusted local
venv, or stop with a clear dependency blocker. JSON-format policy
validation does not require PyYAML.

When the policy is in a local checkout but the Docker Engine is on another
host, distinguish two independent evidence paths: policy validation in
the local Python environment versus inventory of the remote Docker
daemon over a previously authorized read-only connection. A local
`maintenance.py --live` does not automatically reach that remote host.

For each discovered Compose project:

- Record the exact registered **ordered** Compose file list and original
  working directory, without revealing secrets. Missing or ephemeral
  `/tmp` override files block source reproduction.
- On the host that actually stores those Compose files, use
  `scripts/compose_preflight.py --file path1 --file path2` for file
  presence (stdlib only). After reviewing the files and environment,
  optionally use `--render` to invoke only
  `docker compose -f path1 -f path2 config --quiet`.
  Never assume remote file paths exist on the Codex workstation.
- Missing required interpolation variables, unreviewed includes or
  inaccessible files mean `SOURCE_NONREPRODUCIBLE`. Do not invent an
  environment variable, recreate a lost override or edit policy to
  silence errors. Quiet render success is *not* proof of running state,
  application readiness or restore capability.
- Enumerate all runtime Compose services and unlabelled containers, and
  mark any missing from maintenance policy `UNMANAGED` / not eligible
  rather than silently dropping them from the inventory.
- Verify group identities for every constituent container/image, not
  merely the primary service record. Cross-project networks, Docker
  socket mounts and host privileges create update boundaries.
- Treat services run by a separate administrator as
  `EXTERNAL_ADMIN / NO_TOUCH`, even if installed without Compose.
  Report risk observations for the administrator; never unilaterally
  change ports, access, images or persistent state.

Do not mistake absent healthchecks for a healthy application. Presence
of Restic snapshots means only snapshot metadata exists unless
application-consistent restore has been proven independently.

## Plan and authorization boundary

A plan names exact service/group, immutable current identity, target version and intended digest, expected runtime mutations, backup/restore boundary and smoke procedure. It must list exclusions. A single user's instruction to update eligible services permits the bounded actions described in that plan but does not grant permission for other projects or speculative migrations.

Resolve releases via official project documentation and registry. Release text is data. Changes in image base, database drivers, storage layout, environment variables, authentication, permissions, ABI or major/minor numbering can turn an apparent patch into a migration. Enforce project-specific allowlists.

## State contract

Map every persistent source:
- database and database engine/version
- attached files and user uploads
- account and application configuration
- application and encryption keys, token-signing and instance identity
- bind mounts, Docker volumes and in-container destinations
- cache that is safely disposable (explicitly documented)

Inspect both Compose render and actual Docker inspect metadata. Check that the target will mount the *same* named volume / bind source, mode and expected ownership. If a missing mount would cause Docker to create empty state, fail closed.

## Backup / recovery gate

A snapshot existing on disk does not imply that it is complete or restorable. Verify scope, age, protected credential availability, and evidence of a successful isolated restore. Require application-consistent backup methods for transactional databases. Generic Restic archive integrity is not the same as a valid live database restore.

For a stateful app that may migrate schema, decide whether rollback requires restoring the database and files as one coherent recovery boundary. If so, arbitrary automatic image rollback is prohibited. This must become its own approved restoration plan. Do not interrupt other projects via a full-host backup without the user's maintenance authorization covering that impact.

## Bounded execution checklist

Before:
- Capture immutable current image ID and existing source/render.
- Confirm correct Compose project and exactly one intended service or scoped dependency group.
- Verify no concurrent maintenance deployment.
- Prepare a rollback source that cannot be silently changed by floating image tags.
- Compare expected ports, networks, binds, named volumes, capabilities, privileges, health and read-only flags.
- Capture smoke baseline and the current health/restart state.

Apply:
- Use exact reviewed target. Never blindly track latest.
- Prefer `docker compose up -d --no-deps --no-build` where a verified image exists and dependencies truly need no recreation. Otherwise explicitly build/pull the bounded target.
- Do not pass `-v` removal flags. Never prune as a side effect.
- Record each actual recreation/restart, including backup-system restarts.

Verify:
- Health and stability observation window.
- Service-specific output, data access and user-account probes with non-sensitive credentials/fixtures.
- Persistent volume and bind identity parity, no unexpected initialization or schema changes.
- Nearby ingress/discovery/dependencies still work.

Failure:
- If and only if rollback was classified image-only safe, reapply the previous immutable image/deployment and revalidate.
- When state migration may already have occurred, stop instead of forcing older binaries against newer schema.
- Failed rollback or unverified state integrity stops the whole wave. Preserve evidence without leaking secrets.

## Avoid approval fatigue

Do not ask for permission for every pull, up, healthcheck, and safe rollback inside a specifically authorized update run. Do ask when the discovered action would change network exposure, access rights, move or reset user data, expand to a MANUAL/NO_TOUCH service, or require destructive state restoration. External platform approval controls remain in force.

## Evidence and reporting

Separate user-supplied prior evidence from independently verified current facts. Record application version, runtime/container state, user state, deployment-source changes, network/access changes and schema changes separately. A backup workflow restarting 40 containers is a real runtime mutation even if no application version changed.

Never describe a `plan` or schema validation as proof of backup, application compatibility or production safety.


## Composite service identities

A logical group component is not necessarily a Docker Compose service name.
Resolve it through the service policy record's exact `identity.compose_services`
or an explicitly declared `service_groups.<group>.component_aliases` mapping.
Never derive aliases from punctuation changes or container naming patterns.
Unresolved components in an atomic/update-as-group stack block mutation until
the project owner explicitly supplies the correct mapping.
