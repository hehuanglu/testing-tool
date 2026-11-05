# Assessment library documentation boundaries

For a new assessment, start with the skill's [criteria-driven workflow v2](../../../references/criteria-driven-workflow.md), [runner routing](../../../references/runner-routing.md) and [setup](../../../references/setup.md). Those references govern criteria, approvals, execution selection, completion and Drive delivery. This directory documents versioned technical contracts and retained implementation history; its legacy approval, status, release and local-bundle rules do not replace the current assessment workflow or grant traffic authority.

## Technical contract guides

- [Product discovery](PRODUCT_DISCOVERY.md): discovery schemas and legacy research compiler.
- [Common backend](multi-product-backend.md): finite recipe CLI and native/direct execution contracts.
- [Anonymous frontend](fe-anonymous-research.md) and [authenticated frontend](fe-authenticated-research.md): separately admitted browser research lanes.
- [BOLA research](bola-research-runbook.md): legacy direct-client and populated continuation contracts. Direct traffic is not automatically ZAP-derived evidence.
- [Operator quickstart](operator-quickstart.md) and [existing target](existing-target-runbook.md): historical isolated pilot contracts, not ordinary assessment prerequisites. Their owner/issuer/reviewer fields belong to those technical inputs; do not request approver identity for the v2 assessment.

Reinspect the selected entrypoint, schema and current admission before using a guide. A guide describing a compiler or prior runtime result does not establish present deployment compatibility. Bundled commands use the external Python environment and `PYTHONPATH` described in setup; `.venv` and a scanner checkout are not packaged here.

## Historical records and unavailable artifacts

[Decisions](decisions.md), [capability matrix](capability-matrix.md) and `remediation/*.md` retain milestone decisions, counts, limitations and evidence references as recorded. Statements such as “current”, “v2”, “blocked” or “verified” inside those records refer to that milestone and its contract, not automatically `criteriaWorkflow.version:2` or the current deployment. The capability registry is an assurance-profile index, not a criterion verdict engine.

The standalone skill does not contain the original workspace's `review/`, `runs/`, `docs/evidence/`, implementation-status documents or external planning documents. Historical relative links to them remain provenance references and cannot be read or treated as fresh evidence here. No missing artifact may be replaced with an invented receipt or success claim.

Some historical qualification drivers are also absent, including `scripts/remediation_w2_campaign.py`, `scripts/verify_finalsource_p0.py`, `scripts/verify_finalsource_fixture_state.py`, `scripts/multi_product_control.py`, `scripts/bola_research_qualification.py`, `scripts/remediation_w4_campaign.py`, `scripts/w7_ui_controls.py`, `scripts/w8_active_controls.py`, `scripts/w10_regression_controls.py` and `scripts/w11_acceptance_controls.py`. Their documented commands are not runnable from this package. Their absence does not remove the corresponding library modules, but prevents claiming the original campaign is reproducible from the bundle alone. Use existing offline tests for their actual assertions; restoring a campaign requires its inspected source and a separate runtime assignment.
