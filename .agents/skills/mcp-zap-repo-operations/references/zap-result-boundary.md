# ZAP execution and result boundary

For new `criteriaWorkflow.version:3` assessments, [criteria-driven workflow](criteria-driven-workflow.md) owns verdict/completion and the [v3 handoff/exporter](product-assessment-handoff.md#version-3--fixed-criteria-and-approved-plan) implements this alert boundary. References below to incompatible generic scope composition describe the legacy v1 exporter only; `scope report` routes v2/v3 through `criteria_reporting`. Historical reports remain unchanged.

This skill uses ZAP as the assessment tool. Do not automatically open npm/Semgrep or standalone source/config/log audits to fill a catalog. Source/config/deployment reads support inventory, actors, fixtures, expectations and interpretation; source-only or external-scanner results do not become alerts in this workflow. Preserve method limits in RUN; no alerts does not establish compliance.

## Three-file result contract

RUN, ALERTS and SCOPE_ALERTS are internal projections. The user-facing table has one row per original criterion under the [Drive output contract](single-table-drive-output.md). In the internal ALERTS/SCOPE_ALERTS projections, the unit is an **alert**, not a generic finding, test question or healthy observation.

- **RUN.json** truthfully records actual operations and observations with ZAP, including normal/negative controls, errors, failed/partial attempts, blocked/unperformed work, provenance, coverage, criteria applicability, limitations, lifecycle and resource state. Planned actions are not performed actions. No-alert observations still belong here.
- **ALERTS.json** contains the list of security alerts and their corresponding details. Include native ZAP alerts and tester-observed security alerts from ZAP traffic, such as suspected or confirmed BOLA. Mapping to a criterion is not required for inclusion.
- **SCOPE_ALERTS.json** contains the subset of those same alerts that can defensibly map to at least one requirement in the original user scope, together with the mapped criteria and alert details. Its primary list is alerts, not criterion-only rows. It is not a criterion-completion report.

Keep the original catalog and the full per-criterion applicability/questions/coverage/gaps in RUN and private working inputs. Do not insert healthy observations, empty criterion rows or placeholder alerts to fill all criteria in SCOPE_ALERTS. An empty alerts list with alertCount0 is valid. Shared context/source/revision/round metadata can accompany both alert lists without changing their purpose.

## Two result kinds in ALERTS.json

Both kinds count as alerts when they meet their respective inclusion rules:

- **Native alert:** collected from actual native ZAP alert output. Preserve native rule/alert identity, severity, confidence, instances, detector/source and triage status, including informational alerts. Do not turn a tester judgment into a native detector result. Unconfirmed impact does not by itself remove a native alert.
- **Observed finding:** a security issue or credible suspected issue interpreted by the tester without a corresponding native ZAP detection established. It may come from requests/actions through ZAP or from source/config/runtime readback admitted by the criterion. Preserve the exact evidence origin; source/config/runtime findings never become ZAP-derived coverage. For BOLA, record the legitimate actor/role/object/owner/relation/state, policy/expectation basis, actual unauthorized access or effect, relevant operation IDs and limits. Separate observed facts from impact/policy uncertainty, preserve suspected/confirmed/needs-review status, and do not invent native rule IDs or native severity/confidence; any tester rating must be explicitly labeled as such.

A successful owner request, denied non-owner request, unchanged state after valid rejection, JOIN success, ordinary404, setup step, failed fixture or inconclusive test with no security signal is a RUN observation, not automatically an observed alert. An inconclusive impact assessment may accompany an observed alert when a concrete security concern exists; uncertainty alone is not an alert. Do not require a native detector or a full exploit to report a credible observed BOLA alert.

Legacy recordKind `zap-derived-observation` does not distinguish healthy controls from security findings. It must be triaged by actual meaning before inclusion/counting; do not rename every legacy observation into an observed finding. Preserve raw/history and move normal observations to the new RUN projection rather than deleting their history. A request bypassing ZAP or a source-only deduction is not ZAP-derived coverage, but a confirmed source/config/runtime security issue may be counted as **Only observed** with that provenance stated explicitly. For new business cases that require a ZAP message, set `requireZapMessageEvidence: true` at plan approval and use the [session-bound capture contract](runner-routing.md#question-capability-mapping-and-adapter-example).

## Alert counts and identities

Apply the [agreed grouping policy](assessment-policy.md#tester-judgment-and-reported-alerts): preserve native records/session identity/grouping; deduplicate re-reading the same native record, not distinct detector outputs merely sharing a plugin. Group observed occurrences only on a supported common issue/boundary/operation/context. Cross-reference possible native/observed duplicates without silently rewriting native output. Counts describe distinct reported alerts, not guaranteed unique root-cause bugs; mappings/retries never create alerts. Native ratings remain unchanged; observed risk is assessed by the tester using actual evidence and the supplied business requirements.

Report **alertCount**, split into **nativeAlertCount** and **observedAlertCount**. The total counts the distinct alert rows in ALERTS after explicit, justified deduplication. In SCOPE_ALERTS, **mappedAlertCount** counts distinct alert rows with at least one valid mapping. Count one alert once even when it maps to multiple criteria; **mappingCount** is a separate association count. **unmappedAlertCount** is alerts retained only in ALERTS. Reconcile totalAlertCount = mappedAlertCount + unmappedAlertCount for the same bundle.

State the grouping/deduplication basis and preserve occurrence/instance counts separately. Do not silently equate a native plugin/rule count, instance count, HTTP request count, number of test observations, criterion count or mapping count with alertCount. Do not merge all issues under one plugin simply to reduce counts; do not count retries, duplicated exports, mappings or readbacks as new alerts. Counts are alerts reported, not automatically confirmed vulnerabilities; triage status remains visible.

Use stable alert identity across both lists and preserve original native IDs/source/session provenance. Existing `findingId` may remain as a technical compatibility key for joins; it does not make legacy uniqueFindings or len(all mixed records) the user-facing alert count. No new ID migration is required just to change wording.

## Mapping admission

Every SCOPE_ALERTS alert must exist in ALERTS with the same identity and corresponding details, plus at least one criterion mapping containing original criterion ID/text or source reference and a semantic rationale. Alert confidence and mapping relevance are separate: a suspected issue can map clearly to a requirement without becoming a confirmed violation. A broad OWASP category match or copied historical association alone is insufficient.

An alert without a defensible mapping stays in ALERTS with the unmapped reason; do not force it into the scoped list. For example, media membership revocation does not establish password brute-force controls, and LEAVE does not establish token rotation. A criterion with zero mapped alerts is not thereby tested, passed or N/A; keep that assessment in RUN. Mapping an alert is not a requirement to reproduce/fix it or to expand testing authority.

## BOLA through ZAP

ZAP can execute/capture owner/non-owner comparisons without automatically detecting every BOLA. Prefer a suitable native detector when available; otherwise use the admitted ZAP sendRequest/proxy and inspect actual response/effects against legitimate ownership/policy. Report observed security issues as observed alerts. Keep normal controls and the BOLA coverage matrix in RUN. Neither a generic active scan nor zero alerts closes the matrix.

The [Access Control Testing add-on](https://www.zaproxy.org/docs/desktop/addons/access-control-testing/) is a possible native detector; check installed capabilities/auth compatibility and actual coverage. Its absence does not prevent tester-observed BOLA alerts.

## Existing reports and helpers

Preserve historical bundles, native alert IDs, raw observations, attempts and retest history. Reclassification creates a new derived projection, not a fresh scan or edited history. A previous total of mixed findings cannot be asserted as an alert total without actual triage.

The current generic compact_results/security_scope helper still accepts mixed finding records and emits a criterion-first SCOPE_ALERTS projection. That is a legacy internal model, **not the v3 alert projection contract**. Its old validator passing does not prove the new alert inclusion, counts or alert-subset shape. The criteria_reporting publisher implements the alert-oriented checks for v2/v3. Use the unadapted legacy helper only to interpret retained internal scope projections; neither exporter replaces the Drive table. Documentation changes alone do not migrate old reports or establish corrected alert counts.
