# Disposable Docker/Compose integration fixture — initial implementation

This is **test code only**, not a production deployment executor or an operational backup provider. It implements the first executable subset of [the acceptance specification](../../docs/DISPOSABLE-TEST-HARNESS.md): F1/H01 synthetic Compose startup, H03 isolated SQLite + attachment restore, H08 corruption refusal and H15 bounded teardown.

## Safety boundary

- The Docker harness refuses execution unless `--run` is supplied **and** GitHub Actions identifies a Linux `github-hosted` runner with the explicit workflow marker.
- The CI job runs on `ubuntu-24.04`, never on a private, user-selected or production-connected self-hosted runner.
- Docker context must be `default`; custom `DOCKER_HOST`/`DOCKER_CONTEXT`/TLS routing is rejected. The launcher does not offer an override for local machines.
- Every execution generates fresh, random Compose project identifiers and disposable folders under `RUNNER_TEMP`. Existing project names block startup.
- The pinned Python image has a reviewed immutable registry digest. The container is unprivileged, read-only, has no network or ports, drops all Linux capabilities, and sees two read-only binds only: generated fixture state and the fixture health-check script.
- The application health check verifies a synthetic SQLite database and references to three artificial attachments. No application/user data, secrets or sensitive environment dumps are needed.
- Teardown verifies the project's explicit synthetic ownership labels, precise mount sources and security boundary **before** stopping any container. It never invokes broad `prune` or `down -v`.
- Unexpected or partial teardown fails CI; diagnostics are retained only in the ephemeral runner's workspace. A successful run cleans the generated fixture tree.

`fixture_backup.py` rejects inputs without a synthetic-only marker, verifies fixed attachment inventory, captures SQLite with the official Python backup API, creates an immutable *test checkpoint*, and restores into a brand-new path. A damaged second snapshot is refused while a previously verified snapshot remains intact.

## Automated invocation

The GitHub Actions workflow `.github/workflows/integration.yml` supplies the ephemeral-runner context and calls:

```text
python -B tests/integration/harness.py --run
```

Running the harness from a local terminal or against testserver is **unsupported and refused** even with `--run`. Do not manufacture environment markers or connect this harness to a real Docker context.

Only the offline fixture tests are intended for local use:

```sh
python -B -m unittest discover -s tests -p test_integration_contract.py -v
```

The normal read-only CLI and regular suite remain untouched; all fixtures use invented identities and data.

## Provider-backed Restic proof (H16/H17/H18)

The CI harness also installs the distribution-packaged Restic CLI **only** on its hosted Linux runner. It creates a fresh encrypted repository under the same run-owned temporary sandbox, with a random synthetic password file (mode 0600) that is never printed or included in backups.

- **H16:** first prepare an application-consistent synthetic recovery set with SQLite's backup API, then use Restic `backup --json`; demand the full immutable snapshot ID and run `check --read-data`.
- **H17:** restore **that exact ID**, never `latest`, into a new tree; verify the checkpoint manifest and the SQLite/attachment links; boot a *separate* disposable Compose app from that restored data and demand a passing health check.
- **H18:** verify that a deliberately incorrect test password cannot list snapshots; recheck that the known-good snapshot is still readable. No `forget`, `prune`, `unlock` or `repair` is exposed by the fixture Restic wrapper.

The test-only provider source is `restic_fixture.py`. Its allowed command surface is explicitly restricted, it never inherits Restic/cloud credentials and it redacts command failures. Offline refusal tests live in `tests/test_restic_fixture_contract.py`. The provider comparison/decision is [ADR-001](../../docs/ADR-001-DISPOSABLE-RESTIC.md).

An encrypted Restic snapshot and repository `check` are **not** proof that a live database can be recovered without application-coherent capture; only the separate restore + application smoke earns synthetic `RESTORE_TESTED` evidence.

## What this does NOT establish

- No real backup provider, encryption, off-host recovery or production restore exists here.
- A temporary test snapshot on a CI runner is **not** a production-grade protected backup.
- A synthetic SQLite backup test does not prove successful recovery of a live database with concurrent writers or external stores.
- No tested `deploy`, `update`, migration, rollback, decommission or retention executor yet exists.
- There is no automatic permission to access a real host, modify a container, change a policy or prune production state.

Next implementation: expand the harness negative isolation/teardown scenarios, then implement an independently reviewed backup-provider interface and an isolated recoverability proof. Progress toward these gates is tracked in [ROADMAP.md](../../docs/ROADMAP.md).
