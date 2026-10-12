# Portable project policy v1

The **public skill** is universal. Each project owns its own `maintenance/services.yaml` (or JSON) and adapters. This v1 schema is deliberately small and the validation tool does not silently translate a project-specific policy.

Top level: `schema_version: "1"` and `services` as a sequence or mapping keyed by name.

Minimum declared update candidate:

```yaml
schema_version: "1"
services:
  - name: demo-web
    policy: AUTO_SAFE
    ownership: sandbox
    deployment:
      compose_file: ./compose.yaml
      project: demo
      service: web
    image:
      current: example.invalid/web:1.0.0
    target:
      image: example.invalid/web:1.0.1
    state:
      complete: true
      binds: []
      volumes: []
      databases: []
      user_files: []
      secret_refs: []
    backup:
      required: false
    rollback:
      class: image_only
    health:
      container: healthy
    smoke:
      profile: http
```

`AUTO_GATED` must have `backup.required: true` plus a defined restore/migration runbook before an agent may act. Other rollback classes are `state_restore_required` and `unknown`. Neither is equivalent to a verified automated rollback.

For `PIN_ONLY` the target image must be the same immutable image content, not simply a tag that looks similar. For `MANUAL` or `NO_TOUCH` a minimal record needs `name`, `policy` and `ownership`.

`ownership` is one of `sandbox`, `application_project`, `external_admin` or `unknown`. `application_project` means the project has maintenance authority for the application. Deployment authority must still be confirmed from repo instructions. `external_admin` and `unknown` are blocked from automation.

The bundled validator checks syntax, required fields and some logical contradictions. It does not access upstream release APIs, run data restores, execute smoke probes or run upgrades.

### Runtime evidence

`--live` performs Docker metadata reads and checks one uniquely matched Compose project/service. It does not prove equality of bind contents, target compatibility, or source/Compose render. `--runtime-json` exists for synthetic fixture testing, not as trusted proof of a live server. Never treat a `GATED` result as execution authorization.

### Extending the schema

Project policy may add provenance, release ranges, dependency groups, adapter references, structured backup gates and state-specific checks. The skill must inspect them and fail closed if behavior is unknown, not silently ignore a security-critical rule. Upstream and integration adapters should be explicit, tested and versioned.

A project with a pre-existing differently shaped `services.yaml` must map it to the portable contract or provide a validated adapter. File naming alone does not establish compatibility.
