# Scanner repository and runner map

Paths below are relative to the verified external `mcp-zap-server` checkout, except assessment paths. Inspect current files before use: this is a source map, rather than proof every mode has run.

## Source, build, and tests

Java/Spring source: `src/main/java/mcp/server/zap/core/`; configuration: `src/main/resources/application.yml`; build contracts: `build.gradle`, `gradle.properties`, `settings.gradle`. The inspected snapshot requires JDK25 and Gradle wrapper 9.8.1. Gateway adapters connect ZAP; `service/*McpToolsService.java` exposes tools, `GuidedScanWorkflowService.java` routes workflows, and authz/policy/configuration/queue/jobstore/history handle scope, execution, and records. Do not replace gateway dependencies or engines merely for setup.

`./gradlew test` excludes docker-tagged tests. `./gradlew dockerTest` runs Docker/Testcontainers fixtures; build does not automatically run dockerTest. On macOS, after verifying the installed JDK:

```sh
JAVA_HOME="$(/usr/libexec/java_home -v 25)" ./gradlew test --no-daemon
```

Choose build/dockerTest/jacoco tasks as needed without changing shell profiles, blindly cleaning history, or adding build scans/Sonar uploads. Results are under `build/test-results/{test,dockerTest}` and `build/reports/tests/`. Record actual command/time/source/image/tests/failures/errors/skips; XML reflects the latest task rather than all current source. Preserve prior results where history matters.

`python3 -m unittest discover -s tests/python -p 'test_*.py'` covers CI/webhooks/contracts/Compose/Helm. Groups require actual PyYAML (historical CI pin 6.0.3), Compose, or Helm; missing tools may skip tests and do not establish full pass. Do not install dependencies just to inspect this map.

`tools/healthcheck/` is the embedded Go healthcheck, not a scan runner. Dockerfile/signature verification qualifies its stated base/image scope, rather than the entire app/source. `.github/workflows/ci.yml` defines remote checks/uploads; existence does not prove remote CI success or authorize publishing/dispatch.

## Runners with side effects

Read [local runtime](local-runtime.md) for bootstrap/doctor/dev scripts. `.github/actions/zap-security-gate/mcp_zap_gate.py` implements MCP crawl/optional active/passive/findings/report/diff; inspect help/action contracts and `docs/integrations/GITHUB_ACTIONS_INTEGRATION.md`. `run-gate.sh` provisions/cleans Compose, adjusts workspace permissions, and requires modern Bash (`${value,,}` is unsupported by macOS Bash 3.2). Use isolated projects/workspaces for intentional local runs rather than an active shared scanner.

GitLab wrappers reuse the Python runner under their integration contract. Webhook scripts send external communications and are not automatically authorized local checks; read WEBHOOK_CALLBACKS guidance. AutomationPlanService/AutomationPlanTargetPolicy may execute traffic/scans: importing/reviewing plans does not authorize execution. AWS EC2/EKS/firewall/cloudformation examples are separate deployment work.

## CI contracts

Read `docs/scanning/CI_GATE_CONTRACTS.md` and `SEEDED_API_GATE_PLAYBOOK.md`. Inspected versions: result v2, snapshot/diff v3, seed/manifest/suppressions v1. v3 records ZAP/add-ons; different/unknown compatibility cannot establish new/resolved comparisons. Seed mode creates candidates rather than accepting baselines for reviewers. Root gate main exits 0/1; separate assessment 0/1/2/3 semantics do not apply.

The root artifact manifest does not universally require copied-native-report hashes; separate strict assessment verifiers may require full readback/hashes. Generated reports do not establish independent coverage/provenance.

## Documentation, packages, and extensions

`docs/` uses Astro/Starlight with npm ci/check/build when needed. `docs/scripts/sync-docs.mjs` generates pages from maintained Markdown: edit canonical source. Keep private machine/rollout notes outside public docs.

`packaging/claude-desktop/` requires Node >=20.18.1; follow its README for npm ci --ignore-scripts --no-audit --no-fund, test, and build. Builds may fetch/package distributions and are not status-only. verify:status checks the Node connector rather than native client-session proof.

`packaging/macos/` contains package/launcher/tunnel/notices; inspect its README and MACOS_PACKAGE guidance, actual bootJar/source-manifest/licensing. Tunnels change reachability and are not default. `plugins/mcp-zap-connect/` provides onboarding and marketplace manifests rather than this full operations skill.

Extension API lives under `src/main/java/mcp/server/zap/extension/api/`; inspect extensionApiJar/samplePolicyMetadataExtensionJar/standalonePolicyMetadataExtensionJar and `docs/extensions/` contracts. The inspected status is experimental-local; standalone builds stage local Maven. A built JAR does not establish Maven Central/stable binaries/runtime loading/multi-engine support.

## Shared operations

`helm/mcp-zap-server/` contains deployment/migrations/storage/network/HPA/PDB variants. Keep chart migration copies aligned with `src/main/resources/db/migration/`. Render tests do not establish live cluster acceptance. Operations docs/observability files/runbooks describe logging/policies/queues/history/production/EC2/HA; configuration existence does not prove metrics or deployment. HA needs shared jobs/leases/node IDs/affinity/revocation/history/ZAP recovery rather than replica counts. The inspected public repository has no runnable HA Compose.

## Bundled assessment library

`$ASSESSMENT_ROOT` is a separate bounded executor library using Python 3.13/dependencies. CLI anonymous planner/pilot/recover/verify, basic BOLA, owned synthetic login/read, and borrowed Docker lanes have distinct contracts. Integration/binding/fault/BOLA campaigns may create fixtures/traffic; fake fault transports do not prove ZAP. Do not run them for status. Some builders/verifiers write or overwrite outputs (including historical default paths); use read-only saved-data helpers for audits and inspect actual commands before invocation.
