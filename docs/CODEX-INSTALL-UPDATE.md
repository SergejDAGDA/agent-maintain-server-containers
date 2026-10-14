# Codex installation and update — Maintain Server Containers v0.4.0

Canonical public repository:
`https://github.com/SergejDAGDA/agent-maintain-server-containers`

Exact release source:
`https://github.com/SergejDAGDA/agent-maintain-server-containers/tree/v0.4.0/skills/maintain-server-containers`

## Safety-first update (recommended)

The v0.4.0 tag and GitHub Release are created through a separately authorized **manual GitHub publication** after both workflows pass on the exact merged `main` commit SHA. There is no custom release workflow for v0.4.0. Do not install from a PR or from `main` before that published Release exists.

For an existing v0.3.0 installation, keep the current copy active until the
v0.4.0 GitHub Release and tag are verified. This is an explicitly authorized
local Codex skill upgrade, not a server maintenance task.

Tell Codex to perform a controlled, **local-only** installation:

> Update my existing Codex skill `maintain-server-containers` to exactly
> `v0.4.0` from the GitHub release linked above. First inspect all existing
> user/project skill locations and the installed skill content. Do not edit
> the internal Codex runtime cache, unrelated skills, project-owned
> `maintenance/services.yaml`, or any Docker services. Verify the GitHub
> release exists and that both plugin manifests and
> `skills/maintain-server-containers/VERSION` say `0.4.0`.
> Download or clone the **tagged** repository into a temporary directory,
> validate the canonical skill folder, then back up the currently installed
> copy **outside all active skill discovery paths**. Replace only the
> `maintain-server-containers` directory using a safe staged update.
> Preserve unrelated files, and roll back to the backup if installation or
> verification fails. Avoid two active copies in different skill locations.
> Run the Python example policy validation tests in the cloned repository
> without contacting Docker, and report the release tag, commit SHA, final
> installed `SKILL.md` path, installed `VERSION`, and any problems.
> Do not modify servers, volumes, running containers, secrets, or Git repos
> except the intended local skill installation and its local backup.

This prompt intentionally leaves platform-specific install locations for
Codex to discover: Codex versions and skill-install methods can differ.
The source is **pinned to a tag**, not to `main`.

## New installation (when the skill is absent)

If your Codex environment offers `$skill-installer`, you may request:

```text
$skill-installer install https://github.com/SergejDAGDA/agent-maintain-server-containers/tree/v0.4.0/skills/maintain-server-containers
```

The official installer generally **refuses to overwrite** an existing
directory. For updates, use the controlled backup-and-replace prompt above,
rather than deleting a skill blindly. If your Codex does not provide
`$skill-installer`, an agent may clone the tagged repository and place
**only** `skills/maintain-server-containers/` in the active user or
repository skills directory. Check available paths in the current Codex
version; do not guess where the installed skill currently lives.

## Verification

1. The public GitHub release is actually published (not merely a commit or
   proposed tag), and the source is exactly the `v0.4.0` tag.
2. Both repository manifests have version `0.4.0`; the installed
   `maintain-server-containers/VERSION` contains only `0.4.0`.
3. `SKILL.md`, `scripts/maintenance.py`, and the `references/` documents
   are present in the **same installed skill folder**.
4. The standalone source checkout passes:
   ```sh
   python skills/maintain-server-containers/scripts/doctor.py --format json
   python -m unittest discover -s tests -v
   python skills/maintain-server-containers/scripts/maintenance.py --policy examples/services.yaml validate
   python skills/maintain-server-containers/scripts/maintenance.py --policy examples/native-policy.yaml validate
   ```
   For YAML policies, use an existing reviewed local virtual environment with PyYAML. A controlled, explicitly approved local test-environment setup may install the declared requirements separately. Never install packages on the inspected server as a side effect of read-only acceptance. For JSON policies, check `json_policy_ready` even if doctor returns 2 for YAML readiness.
5. Restart the Codex session if skill discovery does not refresh. Invoke
   `$maintain-server-containers` first with a **read-only** request.

## First acceptance prompt (no service changes)

```text
Use $maintain-server-containers to audit the Docker Compose projects
available in this environment in read-only mode. Discover the project-owned
policy, existing server instructions and the exact Compose service/volume
identities. Do not pull images, stop/recreate containers, modify Compose
files, run backup captures, restore data or change network/access. Report
what was verified, what remains unknown, blocked services and a suggested
next maintenance plan. Do not infer authorization from a passing policy.
```

**Warning:** v0.4.0 does not include a deterministic production Docker
updater or protected independent disaster-recovery service. Synthetic CI
success is not proof that real applications are safe to upgrade.
