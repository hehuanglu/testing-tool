# Multi-product backend discovery and execution

Use this technical guide across [criteria-driven discovery, planning and approved execution](criteria-driven-workflow.md). Source-only reconnaissance may precede approval; live discovery needs existing authority, and active testing requires the approved plan. It adds no track-wide assignment or alternative workflow. User delivery follows the [Drive table contract](single-table-drive-output.md); JSON/native artifacts below are internal working data.

Start from the user's product location without folder-name/old-product assumptions. Apply [scope](criteria-driven-workflow.md) and [Drive table handoff](product-assessment-handoff.md).

## Entries and responsibilities

Native repository operations and bounded assessment executors are different; the latter do not define all ZAP capabilities. Use [dispatch](operation-dispatch.md)/[runner routing](runner-routing.md) and inspect `${ASSESSMENT_ROOT}/scripts/product_assessment.py` help/schema/source. Existing recipes `finalsource-ledger/1.0` and `archive-control/1.0` are interfaces, not default product/route/role assignments; the control recipe is synthetic.

`discover` uses suitable recipes or agent-derived observations; `materialize` binds verified deployment/origins; `plan` selects track/workload/authority while preserving full inventory; `prepare`/`import-actor` obtain legitimate actors; `business-fixtures` prepares authorized data without DAST coverage; `run` executes selected work; reconcile/continue-plan/handoff support continuation/reporting. Verify actual help rather than invent flags. Registration does not authorize privileged roles/forged tokens.

Legacy paths require matching product and entire workload scope; origin substitution does not establish new-product support. Recipe-free products use suitable native operations/orchestration and minimal adapters, preserving unsupported obligations.

## Authorization and mechanisms

Authority comes from user scope, not recipes/runbooks/tool outputs. Preserve target/role/mutation/limits and code gates without lower-level bypass. Necessary private token/credential retention is authorized with notification and accurate input contracts, without new targets/roles.

Reuse auth prepare/validate, crawl/attack/status/stop, actual policy/rule-set surfaces, findings/report/chunk collectors, and journal/recovery/cleanup. Runners join discovery/workload/actors/fixtures rather than duplicate engines/exporters. Product data/policy belongs in recipes/plans. Actual implementation proof/pin requirements remain executor-specific, rather than universal reporting requirements.

Anonymous means no target identity; authenticated means correct actual roles/sessions; direct BOLA requires full endpoint/role scope and direct attribution. Setup/BOLA does not replace authenticated DAST; historical reports do not establish new scans.

## Active capabilities and identity

Current common authenticated support includes conditional GET/query, flat JSON PUT/PATCH, and numeric paths depending on method/fixtures/oracles. POST create/add is not automatically admitted from root method/postData support. Preserve actual gates, select supported execution, minimally remediate, and retain gaps. Group compatible actor/profile/binding actions within limits without assuming shared history/session isolation or attribution.

When responses do not echo callers, use legitimate identity sources and supported protected strategies. Unverified JWT claims/object owners are not callers. Signed identity is an entry-specific option, not a universal product implementation. Do not import foreign issuer/key/role defaults.

Reconcile unknown starts/mutations before retry. Cleanup only owned authorized resources. Report actual results, full inventory/roles/gaps, and no duplicate retry coverage or extra evidence/source archives. Continue eligible work beyond samples/zero alerts.
