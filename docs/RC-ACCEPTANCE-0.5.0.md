# Release candidate acceptance: 0.5.0-rc.1

**Candidate status:** proposed in PR #28. Not merged, tagged, released, installed or deployed on any production host. The previous published version remains v0.4.0. Record the **exact PR head SHA** in the acceptance review; never approve an earlier commit's CI as evidence for a later head.

## Intended minimal deliverable

The existing Agent Skill, run by an authorized Docker-capable agent, supports a reproducible, auditable lifecycle for Docker Compose applications without introducing a custom orchestrator:

1. Read-only audit/status/plan, including known project safety-adapter and runtime-source limits.
2. First install of a third-party application with a stable source, dependencies, state, secrets and project registration.
3. Targeted **clean rebuild of an existing app** with explicit owner choice about disposable state; protected personal data must survive.
4. Bounded update (and project-approved deployment) with recorded source/image identity, compatible state, actual functional smoke and safe rollback.
5. Repeatable site/host layout and optional Git checkout strategy; remote daemon bind paths and source/build files are checked on the server.
6. Next maintenance can start from authoritative files and records, **not** reverse-engineer a running container.

The Python helper deliberately remains **read-only**. Docker mutation is an agent-level, permission-gated workflow using native Docker Compose and the consuming project's real deployment/source/recovery controls.

## Required static/CI gates

- [ ] Skill package VERSION and both plugin manifests are exactly \`0.5.0-rc.1\`.
- [ ] English/Russian README, changelog, SKILL.md and operations agree on supported lifecycle and limits.
- [ ] Main-base diff contains no unrelated framework, host-specific private resource, secret or production state file.
- [ ] Ubuntu and Windows offline unittest suites pass on **the exact candidate SHA**.
- [ ] Real Linux Docker Compose source-fixture check passes with \`--render --check-build-sources\`.
- [ ] Existing disposable Compose/Restic recovery CI passes on the **same SHA**.
- [ ] Required reviewer checks that \`MANUAL\` targeted rebuild is permitted only under explicit scope; \`NO_TOUCH\` and external admin remain protected.
- [ ] Build preflight and reports do not expose Compose interpolation, credentials or raw Docker stderr.
- [ ] Reviewer B-01 regression: plain `--render` with missing Dockerfile must report `compose_render_verified=true`, `source_reproducible=false`, `build_sources_checked=false`; explicit `--render --check-build-sources` blocks missing Dockerfile. Neither mode claims complete source reproducibility or update authority.
- [ ] New/modified source-file and policy contracts fail closed for missing build inputs, unknown ownership, incomplete protected data or unproven rollback.

## Required one-time disposable end-to-end acceptance

Run on **an isolated disposable Linux Docker Compose test environment**, never against existing user data or a protected server service. Use Codex Desktop in a fresh, explicitly named review/test chat, with the exact repo/commit and permission to create/remove **only test-owned resources**.

Exercise these flows and record observations rather than relying on a green healthcheck:

1. **Install:** select the host's existing convention (or default Linux profile), register a pinned source/image, put Compose/build inputs in the authoritative non-secret source, keep state and secrets separate, and run a synthetic functional test.
2. **Rebuild:** identify a protected synthetic document and an explicitly disposable cache. Replace only the cache while demonstrating protected data survival and container UID/GID writability, then run a synthetic functional smoke.
3. **Update:** change to an approved pinned next build/revision, compare complete server Compose/build sources to canonical source and verify image, data, network, app result, records and dashboard/discovery as applicable.
4. **Failure and rollback:** cause a bounded synthetic acceptance failure; restore/check **both** previous running image **and** active canonical/server Compose+Dockerfile or pinned source. A wrong active source is a failure.
5. **Stop rules:** demonstrate \`MANUAL\` excluded from \`update-auto\`, but separately targetable under exact approval; \`NO_TOUCH\`, external-admin and invalid/unknown project gates are not bypassed.
6. **Owner access:** if app onboarding needs interactive owner setup, report \`OWNER_SETUP_REQUIRED\`; do not leave a synthetic owner with a lost password and claim full acceptance.
7. **Cleanup:** remove only exact disposable fixture resources, preserve evidence, and demonstrate no unrelated Compose resources changed.

An environment where Docker is unavailable is **ENVIRONMENT** / not verified, not a passing end-to-end test. If the same acceptance goal fails twice, stop incremental patching, diagnose root cause and reconsider the custom implementation before the next attempt.

## Non-goals and known limits

- **No standalone production mutation executor.** Do not describe \`rebuild\` or \`update-auto\` as built-in Python CLI commands.
- **No unattended scheduled upgrades.** User authorization and site-specific adapter contracts govern actual mutations.
- **No automatic proof of disaster recovery.** Restic archive integrity, a local image and a synthetic restore are distinct from a complete off-host restore.
- **No automatic adaptation of invalid consuming policies.** A policy with unresolved required trusted safety adapters or unknown protected state still fails closed. The SandBox-Server project-specific four known validation errors are not fixed by this portable-skill PR.
- **No forced filesystem migration.** Existing deployment owners and paths supersede default new-host examples.
- **No deployment without owner authority, proven source identity and app-appropriate data boundaries.**

## Decision

- **CODE_CANDIDATE:** all static checks, required CI and source review on exact SHA pass; RC package is ready for independently executed disposable end-to-end acceptance.
- **OPERATIONAL_RC_ACCEPTED:** independent end-to-end review succeeds with exact SHA and no unresolved BLOCKER.
- **RELEASE GO:** explicit owner decision after OPERATIONAL_RC_ACCEPTED; merge first, then verify merged \`main\` SHA and CI, publish a tag/Release separately, and finally explicitly install the new version.
- **NO-GO:** any actual safety blocker, unexplained source drift, incorrect protected-data disposition, failed source+runtime rollback, or false claim of owner access.

Neither PR merge, GitHub tag, GitHub Release, local Agent Skill installation nor testserver changes are automatic consequences of this document.
