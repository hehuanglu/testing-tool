# Shared discovery and research-plan/2.1

This contract represents discovery for five tracks. Backend authenticated, backend anonymous and [BOLA research](bola-research-runbook.md) now consume it through separate compilers and explicitly selected test adapters. The original authenticated-plan contract below remains historical context; a BOLA direct plan never fabricates scanner/auth-session requirements. Synthetic metadata tests do not prove another live product or track.

Agent workflow is in the personal operations skill's
[product-discovery reference](/Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/product-discovery.md).
The manifest schema is `schemas/product-discovery-v1.1.schema.json`; the plan schema
is `schemas/be-authenticated-research-plan-v2.1.schema.json`. `research.admit` dispatches
on the new plan version; schema/admission v1 semantics remain intact. The assurance
profile remains `be-authenticated-research/1.0`, with private local native retention.
Strict P0, shared defaults and upstream Java are unchanged.

```sh
zap-product-assessment/.venv/bin/python zap-product-assessment/scripts/product_discovery.py validate --manifest /absolute/PRODUCT_DISCOVERY.json --executable
zap-product-assessment/.venv/bin/python zap-product-assessment/scripts/be_authenticated_research.py run --adapter finalsource --discovery /absolute/PRODUCT_DISCOVERY.json --output /absolute/new-private-run --jar /absolute/mcp-zap-server/build/libs/mcp-zap-server-0.16.0.jar
```

Validate discovery first; confirm live ownership/binding/resources before running.
These commands require actual authority for fixture creation, direct preparation,
login and bounded active scanning on the selected test deployment. They are not an
implicit authorization. The old CLI without discovery remains available for legacy
reproduction; it cannot count as discovery proof. No product auto-selects an adapter.

`discovery.compile_plan` takes the frozen manifest, independently established actor,
resolved owned fixtures and concrete requests. It rejects missing provenance,
blocking conflicts, unverified origins, identity gaps, source/binding drift and
mutations without preparation/ownership/postconditions. The finalsource adapter
checks its finite supported surface before writes and rechecks runtime inventory;
unsupported metadata fails with an extension reason rather than falling back.

The plan embeds a manifest snapshot/canonical digest. Adapter fixture recipes
supply input values and actual IDs, while agent facts supply inventory, origins,
auth, identity and fixture prerequisites. `DISCOVERY_CONSUMPTION.json` records this
boundary. The adapter binds exact seed/crawl/attack actions into the plan before
ResearchRun; the executor consumes these actions and validates method/path/query/
body before starts. It records the received plan's file hash and refuses file or
in-memory drift. No data file may contain arbitrary executable product code.

JSON reporting is a derived view (`discovery_handoff.build_handoff`) of sealed raw
ZAP alerts. Native severity/confidence remain intact. Guard-destination alerts are
listed separately; BOLA/direct controls are not ZAP app findings. Descriptions,
instances, evidence refs and remediation are retained; unsupported impact is
explicitly unverified. Raw reports/history remain private with byte hashes.

Focused tests: `test_discovery`, `test_research`, `test_research_comparison`.
Use the task evidence's COST_LEDGER and ROOT_CAUSE_LEDGER for actual attempts,
limits and known failures. Readback consistency alone never proves scan/security.
Rollback only the mapped task diffs/backups, preserving prior dirty work and all
historical evidence. Never reset the product/database for rollback or cleanup.

Manifest 1.1 adds stable environment ID/provenance, confidence and explicit execution access points. Independent runtime inspection supplies transportBinding to plan 2.1; verified Docker aliases and current published proxy origins are admitted, without fixed alias substitution. Old manifest1.0/plan2.0 and research v1 remain readable with their original schemas.

Origin inventory can retain multiple aliases. Every authorized/verified execution candidate must match the independently observed selected-deployment transport proof. Compiler, direct fixture client, native auth profile and cleanup choose the first authorized verified candidate in immutable manifest order for each role. Plan admission rejects selection drift. Changing origin order changes the plan/hash; unknown aliases reject the whole admission rather than falling back. The original frozen blind outputs remain unchanged.
