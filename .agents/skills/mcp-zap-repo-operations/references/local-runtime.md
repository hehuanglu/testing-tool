# Local runtime or configured connector

Discover the current runtime rather than assuming developer endpoints/ports/Compose projects/profiles/images. Read [setup](setup.md) to distinguish bundled resources, scanner, and product.

## Inspect current state

Use native `zap_passive_scan_status` where appropriate to check the connector/backlog. This establishes current connectivity/backlog only, rather than stopped producers or completed assessment. Client→MCP auth differs from ZAP→product auth.

Use Docker preflight only when the selected executor/deployment needs Docker. An unavailable daemon blocks dependent traffic, rather than independent source discovery. Do not change context/restart/rebuild to pass preflight.

For authorized local-runtime inspection:

```sh
docker context show
docker version
docker compose version
docker ps --format '{{.Names}} {{.Image}} {{.Status}} {{.Ports}}'
```

Inspect only relevant Compose working_dir/config_files/project labels, container/image IDs, state, and mount destinations. Do not print Config.Env/full inspect/secrets. Scanner/product ownership differs; do not stop the product to obtain ports.

With verified `MCP_ZAP_REPO`, inspect `bin/self-serve-doctor.sh` help/source and use the correct endpoint/credential without API keys on argv. Doctor does not start scans/recreate stacks; readiness is not capability qualification.

## Start/stop the correct installation

Mutate runtime only when required and after verifying ownership/configuration/ports. Use the installation's exact Compose project, env file, and full file set; do not assume dev/auth overrides. `config --quiet` validates without printing secrets. Identify active runs/operations before stopping; zero backlog does not authorize canceling others' scans.

Prefer starting existing stopped containers and data-preserving stops where suitable. Build/up requires task need and before/after source/status/image inspection. Do not default to force-recreate, bootstrap --force, down -v, key changes, or experimental auth. Release/dev/auth/OpenAPI-content topologies differ; inspect current scanner documentation.

Executors admit required Docker/browser/images/JARs. Do not alter pins/gates or treat an existing binary as source-to-image proof. Follow [resource preflight](resource-preflight.md); do not prune/reset databases to pass.

## Bounded diagnosis

Identify port listener/container/project without stopping unrelated apps. Diagnose health/auth against the correct transport/profile without speculative key/surface changes. Compare actual tool schemas/scopes/guided/expert before inferring missing engine capability. For queue restarts inspect backend/lease/fence/operation identity; in-memory does not ensure resume. Missing scanner source blocks build/doctor/source checks only; an adequate connector remains usable.
