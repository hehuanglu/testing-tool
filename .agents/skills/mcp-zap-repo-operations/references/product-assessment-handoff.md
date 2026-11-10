# Drive table handoff and retained assessment state

## Required deliverables

The user-facing output is one native Google Sheets file on Drive with one worksheet, one eleven-column assessment table and one row per original catalog criterion. Follow [single-table output](single-table-drive-output.md) for exact labels, visual reference, statuses, severity, evidence links, explanatory notes, synchronization and readback. Retain catalog order and explicit exclusions. The project is the business input; the 50-criterion OWASP 2025 catalog is bundled with the skill. Do not ask the user to author technical JSON or matrices.

Use the [criteria-driven workflow](criteria-driven-workflow.md) for every assessment operation. Track-specific runners and legacy bookkeeping guides supply primitives, never additional assessment workflows or alternative delivery formats. Skill/tool audits and maintenance report their actual changes/checks/limits without inventing product traffic or a spreadsheet.

## Version 3 — fixed criteria and approved plan

Use criteriaWorkflow.version:3 in the private working RUN for every new assessment. Preserve the fixed-catalog criteria revision, approved plan revision, real Gate 2 approval source and content digests, actual operations/semantic observations, limitations, resource/effect state and private continuation references. Review each selected criterion independently even when several use the same case or operation. A worker summary, successful export or zero alerts does not establish a verdict. Historical version 2 RUNs retain their original two approvals and are not templates for new work.

The implemented internal exporter is criteria_reporting.publish_reports, selected by product_scope.compact_results and the CLI:

```sh
"$ZAP_PYTHON" -B "$ASSESSMENT_ROOT/scripts/product_assessment.py" scope criteria-review --run PRIVATE_WORKING_RUN.json
"$ZAP_PYTHON" -B "$ASSESSMENT_ROOT/scripts/product_assessment.py" scope report \
  --run PRIVATE_WORKING_RUN.json --alerts TRIAGED_ALERTS.json --output NEW_DIRECTORY
```

Use configured dependencies/PYTHONPATH from [setup](setup.md). Add --finalize-round only when the current v3 review is eligible. It does not invoke legacy round closure. Legacy inventory/scope CLI arguments are rejected for v2/v3. Exporting a progress snapshot neither authorizes traffic nor makes the assessment complete. The exporter writes local JSON; it does not synchronize Google Sheets.

## Internal evidence projections

Maintain these supported projections as useful to reconciliation, publication or continuation; they are not three additional mandatory user deliverables:

- **RUN.json:** context, approved criteria/plan, current reviewer-derived results, actual operations/observations, controls, failed/partial attempts, missing work, limits, resources and private recovery references.
- **ALERTS.json:** explicitly triaged native-zap-alert or observed-security-alert records with concrete security signal, actual ZAP provenance and stable identity. Healthy controls and bare uncertainty stay in RUN.
- **SCOPE_ALERTS.json:** the exact mapped alert subset, retaining corresponding details plus original criterion ID/text/source and semantic mapping rationale. It contains neither criterion-only rows nor no-alert placeholders.

Apply the [alert boundary](zap-result-boundary.md). Native alerts preserve rule/identity/severity/confidence. Observed alerts preserve expected/observed behavior, legitimate actor/object/role/state, policy basis, linked ZAP operations and tester triage/ratings provenance. No source-only finding or bypass traffic becomes ZAP-derived coverage. The operating agent is the tester and triages observed alerts using actual evidence and business-risk judgment; native alerts/ratings stay as ZAP reported. No extra user risk rubric, independent knowledge validation, per-alert exploit campaign or proof package is added.

Count distinct alerts separately from instances/occurrences and criterion mappings. Multiple rows reusing one finding do not create multiple alerts. Unknown occurrence totals remain unknown; a native ID alone is not an occurrence count. Preserve historical issues not retested and actual grouping/attribution limits.

The v2/v3 publisher checks exact mapped subset, counts, context/generation and sanitized links. New directories are staged then renamed. Overwrite is atomic per file, not crash-atomic across all three files; reconcile generation mismatch after interruption. Preserve raw/journals/pins and historical bundles. Sanitized report projections are not executable working RUNs; retain the private working RUN and coordinator directory. Sanitize arbitrary text and known secret values before any supporting material is shared; a validator does not prove complete secret/PII removal.

## Assessment completion and Drive delivery

Assessment completion follows the canonical criteria reviewer: all selected criteria and approved plan obligations are accounted for, every excluded row retains its selection reason, and effects/resources are controlled with no hidden feasible required work. It can include unmet or product-grounded N/A (`not_evaluable` with reason `not_applicable`) results; selected applicable criteria with insufficient evidence remain pending and prohibit completion. Completion never means product safety or remediation approval.

Delivery completion is separate and agent-maintained. Retain driveOutput with actual run/file/worksheet identity, URL, pending/verified/outdated/failed status, last verified synchronization and reviewed source revision/snapshot. The reviewer does not enforce this metadata. Update the same file by criterion ID, maintain the agreed layout/content in the assessment-managed range and verify values, formatting and evidence access after writing. Human-edit reconciliation is outside scope; sharing stays with the user. New reviewed results mark the old table outdated until verified again. Failed creation with uncertain outcome requires file/metadata reconciliation before replacement.

A successful final user handoff needs the table verified against the final reviewed assessment. If assessment is completed but Drive is pending/outdated/failed, say delivery remains unfinished, preserve local results and perform the exact remaining publication step when possible. Do not rescan to repair publication or replace Drive delivery with local JSON links. If a connector is unavailable, report the actual dependency and continue independent authorized work.

## Final response

Produce consolidated reporting, with no severity-triggered immediate notification/escalation workflow. Lead with the spreadsheet link and interim/final synchronization status, then assessment status, concise criterion outcomes and material limits/next actions. Do not require a three-JSON link list or a fixed Operations/Limitations format. Give supporting report links only when requested or needed to make an evidence citation accessible. Never fabricate EV links, infer met from zero alerts, or present an unfinished row as a final verdict.

For completed work, give only concrete reopening triggers where needed. For an actual unfinished checkpoint, state its real reason, retain private RUN/journal/lease/fixture references and the exact next action, and provide usable continuation guidance under [recovery](retention-stop-and-recovery.md). Do not put credentials or private raw traffic in a resume prompt. Exporting a file, finishing an allocation or changing fixtures does not itself justify stopping.

## Historical compatibility

Existing legacy reports, statuses, approvals, findings and pins stay historical. [Legacy scope](assessment-scope-and-completion.md) and [legacy representations](user-security-scope.md) are readback/compatibility references only. Before new execution, prepare the current v3 fixed-catalog criteria/plan, reuse only explicitly compatible observations and obtain the content-bound Gate 2 approval. Do not run legacy closure/continue commands against v2/v3 or create a parallel legacy assessment workflow. Reclassification and table synchronization are not retests.
