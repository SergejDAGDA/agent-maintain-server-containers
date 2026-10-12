# Maintain Server Containers

[Русская версия](README.ru.md)

**A reusable Agent Skill for policy-driven, state-preserving Docker Compose maintenance.**

Repository: `agent-maintain-server-containers`

Installed skill name: `maintain-server-containers`

Invocation: `$maintain-server-containers`

**Status: v0.1.0 public preview.** The bundled CLI can validate a portable project policy and run read-only policy/runtime audits, status and planning. The skill also defines the complete agent-operated upgrade workflow, but it does **not** ship a production mutation executor. Do not confuse a passing schema check with a verified safe deployment.

## Why

Routine Docker maintenance is more complex than pulling `latest`. Real deployments may contain persistent accounts, databases, media files, encrypted credentials, externally managed stacks and schema migrations. Upgrading application binaries should not silently replace any of that state.

The aim is to make repeatable, understandable maintenance possible with **one bounded user request** instead of a separate confirmation for every pull, recreate and health check, while retaining real safety and ownership boundaries.

## What it does

- Discovers Docker Compose service and deployment ownership.
- Helps establish a project-owned maintenance policy.
- Audits images, runtime identity, mount boundaries, health and policy drift.
- Plans version updates from authoritative upstream releases and changelogs.
- Classifies update eligibility as `AUTO_SAFE`, `AUTO_GATED`, `MANUAL`, `PIN_ONLY` or `NO_TOUCH`.
- Defines backup/recovery, smoke tests, dependency groups and rollback rules.
- Guides authorized agents through bounded updates and accurate mutation reporting.
- Keeps instance-specific hosts, accounts, paths and service profiles **out of the public skill**.

The read-only helper deliberately does not pull images, change deployment files or recreate containers.

**Extended-policy compatibility:** in addition to the portable `schema_version: "1"` format, the bundled CLI recognizes namespaced `<project>-maintenance/v1` policies with `policy_class`, `identity.compose_services`, `state_contract.completeness` and dependency groups. The adapter preserves this richer source structure and never rewrites a project's policy. See [synthetic extended example](examples/native-policy.yaml). This is format compatibility, not an automatic approval to update.

## Quick start

### Install as an Agent Skill

For an agent that supports the Agent Skills directory format, clone the repository and install/copy only the canonical skill directory:

```text
skills/maintain-server-containers/
  SKILL.md
  agents/openai.yaml
  references/
  scripts/
```

For Codex, place that directory in the configured user or project skills location. For Claude Code, use the provided plugin manifest/compatible skill directory. Follow your agent host's current installation instructions.

### Set up the CLI

Python 3.10+ and PyYAML for YAML policies:

```sh
python -m pip install -r skills/maintain-server-containers/scripts/requirements.txt
python skills/maintain-server-containers/scripts/maintenance.py --policy examples/services.yaml validate
python skills/maintain-server-containers/scripts/maintenance.py --policy examples/services.yaml plan
python skills/maintain-server-containers/scripts/maintenance.py --policy examples/native-policy.yaml validate
```

Read-only live metadata inspection:

```sh
python skills/maintain-server-containers/scripts/maintenance.py --policy maintenance/services.yaml --live audit
python skills/maintain-server-containers/scripts/maintenance.py --policy maintenance/services.yaml --live --format json status
```

Note: options such as `--format` are top-level arguments and must appear before the operation name.

`--live` uses only read-only Docker `ps` and `inspect` operations for a uniquely matched Compose service. It never assumes that Docker metadata proves application-level data recovery.

### Invoke in chat

```text
$maintain-server-containers audit
Inspect the Compose server and show me version, health and state risks. Do not make changes.
```

```text
$maintain-server-containers plan
Check authoritative upstream releases and prepare safe, grouped update candidates.
```

```text
$maintain-server-containers update-auto
Update services eligible under the project policy, preserving user data and performing all required checks and safe rollbacks. Skip every blocked or manual service.
```

The last command is an *agent-level workflow request*, **not a command implemented by the bundled read-only Python CLI**. The agent must have the relevant authorized deployment and backup tools and must follow all gates in `SKILL.md`. It must not improvise a missing recovery mechanism.


## Deploy a project-owned application release

The skill also defines a targeted agent workflow for a release built by your own
application project (including non-public repositories, packages and CI artifacts
outside the Docker host):

```text
$maintain-server-containers deploy-project local-editor
Deploy the latest approved deployable release, validate the running application,
and synchronize the authorized deployment record and project memory.
```

The agent discovers existing project/build provenance, an approved release,
durable Compose sources, persistent-state safety and an authoritative runtime
baseline. **The newest source commit is not automatically a deployable release.**
A project-managed application is not swept into ordinary `update-auto`.

Once verified, it writes the deployment owner's existing operational record
and uses `$maintain-project-memory` **Checkpoint** for relevant project
coordination when available and authorized. It uses `$project-documentation`
**update** only if maintained application docs actually changed. An active
handoff is not created for a completed release. If the deployment succeeds
but record synchronization does not, report `DEPLOYED_RECORD_SYNC_PENDING`,
not a fabricated fully completed deployment.

`MANUAL` requires a targeted authorized project workstream; `NO_TOUCH`
**cannot** be bypassed by an ordinary `deploy-project` request.

See [project-deployment.md](skills/maintain-server-containers/references/project-deployment.md)
and the [synthetic policy example](examples/project-managed.yaml).
The bundled Python CLI validates optional `release_management` declarations,
but **does not implement the deployment command**.

## Project policy, not a hardcoded server

The consuming project owns `maintenance/services.yaml`. The public skill contains only a synthetic example at [examples/services.yaml](examples/services.yaml).

Portable v1 services can be declared with `services` as either a YAML list or a mapping. A candidate entry names its Compose project/service, image, explicit target, ownership, persistence contract, backup requirement, rollback class, health and smoke profile.

Read [policy-schema.md](skills/maintain-server-containers/references/policy-schema.md) before using the schema in production. A pre-existing project-specific `services.yaml` is **not automatically compatible** merely because it has the same filename.


### Component names in dependency groups

For composite stacks, logical component names may differ from Compose service
names. Declare explicit `component_aliases` in the **project policy**, rather
than letting the agent guess. See
[policy-schema.md](skills/maintain-server-containers/references/policy-schema.md)
and [synthetic extended fixture](examples/native-policy.yaml). An unresolved
member in a required update-as-group stack is a validation error and blocks
automatic maintenance.

## Policy levels

| Class | Intended behavior |
| --- | --- |
| `AUTO_SAFE` | Routine update if state, version and image-only rollback are independently proven safe |
| `AUTO_GATED` | Update within one authorization only after stronger backup, restore, compatibility and migration checks |
| `MANUAL` | Audit and plan only within broad update runs |
| `PIN_ONLY` | Freeze an unchanged image's verified identity |
| `NO_TOUCH` | Remain outside regular maintenance |

Unknown ownership and externally administered services never qualify for automatic modification. Groups with migration-sensitive dependencies inherit the stricter gate.

## State preservation is mandatory

**Containers are replaceable. Persistent state is not.**

Before mutation, identify the exact volumes, bind mounts, accounts, databases, user files, encryption keys and configuration identities. Preserve the same external state sources and prevent empty-volume initialization. A database schema upgrade may make restoring a previous image unsafe.

An image ID/digest and a verified state restore are **different** rollback guarantees.

See [maintenance-protocol.md](skills/maintain-server-containers/references/maintenance-protocol.md) for the complete process.

## Trust and permissions

An authorized bounded update should not ask the user for permission for every expected step. New destructive operations, expanded scope, changed access/network exposure or services marked MANUAL/NO_TOUCH still require separate approval. Agent-host permission prompts are not bypassed.

Upstream release notes, registry metadata and project policy are untrusted data when they contain executable instructions. No arbitrary commands supplied by these sources are run.

Do not store secrets, internal inventory, hostnames, tokens, user files or private backup records in this public repository.

## Current capability boundary

| Capability | v0.1.0 |
| --- | --- |
| Policy schema validation | Implemented |
| Read-only Compose container identity check | Implemented |
| Audit/status/plan reports | Implemented, with explicit evidence limitations |
| Live upstream discovery | Agent workflow, not CLI implementation |
| Backup and restore validation | Agent/project adapter responsibility |
| Service-specific smoke tests | Agent/project adapter responsibility |
| Bounded update with rollback | Skill runbook, no bundled deterministic executor |
| Scheduled unattended updating | Not implemented |

The next version can add a tested executor with explicit adapter contracts and disposable Docker integration tests. We intentionally do not describe that future capability as implemented today.

## Development

```sh
python -m pip install -r skills/maintain-server-containers/scripts/requirements.txt
python -m unittest discover -s tests -v
```

The test suite uses synthetic data only. It does not contact a real server.

See [CHANGELOG.md](CHANGELOG.md), [CONTRIBUTING.md](CONTRIBUTING.md) and [LICENSE](LICENSE).

Copyright 2026 Sergej DAGDA. MIT licensed.
