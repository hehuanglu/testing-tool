# Assessment library documentation boundaries

For a new assessment, start with the skill's [criteria-driven workflow v3](../../../references/criteria-driven-workflow.md), [runner routing](../../../references/runner-routing.md) and [setup](../../../references/setup.md). Those references govern criteria, approval, execution selection, completion and Drive delivery. This directory documents versioned technical contracts; its legacy approval, status, release and local-bundle rules do not replace the current assessment workflow or grant traffic authority.

## Technical contract guides

- [Product discovery](PRODUCT_DISCOVERY.md): discovery schemas and legacy research compiler.
- [Common backend](multi-product-backend.md): finite recipe CLI and native/direct execution contracts.
- [Anonymous frontend](fe-anonymous-research.md) and [authenticated frontend](fe-authenticated-research.md): separately admitted browser research lanes.
- [BOLA research](bola-research-runbook.md): legacy direct-client and populated continuation contracts. Direct traffic is not automatically ZAP-derived evidence.
- [Operator quickstart](operator-quickstart.md) and [existing target](existing-target-runbook.md): versioned isolated pilot contracts, not ordinary assessment prerequisites. Their owner/issuer/reviewer fields belong to those technical inputs; do not request approver identity for the v2 assessment.

Reinspect the selected entrypoint, schema and current admission before using a guide. A guide describing a compiler or prior runtime result does not establish present deployment compatibility. Bundled commands use the external Python environment and `PYTHONPATH` described in setup; `.venv` and a scanner checkout are not packaged here.

## Capability registry

The [generated capability summary](remediation/CAPABILITIES_GENERATED.md) describes the library's source contracts and execution limits. It does not attest a deployment or establish a criterion verdict.
