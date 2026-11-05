# Triage alerts from available results

Follow the [agreed tester policy](assessment-policy.md#tester-judgment-and-reported-alerts). Catalog/user business knowledge defines the required protection; the operating agent identifies observed alerts and assesses business risk from actual observations. No independent knowledge attestation, user-authored severity rubric or separate expert signature is required. Native alert content, grouping, severity/confidence and triage remain as ZAP reported, including informational/false-positive labels. Observed ratings are tester judgments with explicit basis, not native fields or invented CVSS scores. Reporting is consolidated; do not add severity-triggered immediate escalation.

Apply the [ZAP result boundary](zap-result-boundary.md): native alerts and ZAP-derived observations are distinct; external-tool/source-only findings do not enter this skill’s ALERTS output.

Read returned content with native severity/confidence, bounded interpretation, and limitations. Do not require raw/HTTP archives/hashes/new exploit proof or an additional campaign for every alert. See [handoff](product-assessment-handoff.md).

For injection, inspect route/parameter/vector/baseline and cited responses where available. Distinguish validation/guard rejection, reflection, and observed exploitation. Retain alerts with unconfirmed impact; HTTP 200 or one failed reproduction does not establish false-positive.

For headers/configuration, identify application/document/proxy/guard context where possible. Missing headers do not establish exploitation. Preserve native severity without importing another product's conclusions.

Informational auth/session detection does not itself mean token leakage or broken sessions. Disclosure needs unauthorized receipt observations. Omit token values and do not open expiry/lifecycle campaigns merely to explain informational alerts.

For errors/disclosure, distinguish generic errors from actual stack/secret/meaningful data, bound impact, and protect shared outputs. Do not publish raw data on assumed sanitization.

For observed BOLA/business alerts, inspect actual actor/role/object/owner/relation/state and policy/source expectations, response and available post-state. Separate policy uncertainty from observed failures. Denial status alone does not establish absent side effects; never change expectations to fit outcomes. Observed alerts count as alerts but are not native detector output; identify tester severity/confidence provenance. Supported observations do not close missing endpoint/role coverage under [scope](criteria-driven-workflow.md).

## Separate an alert from an ordinary observation

Include a native alert as reported with its native triage/ratings. Include an observed alert when actual ZAP traffic supports a concrete security issue or credible suspicion; record actor/object/policy basis, actual response/effects and remaining uncertainty. A confirmed exploit is not mandatory. Owner success plus non-owner denial is a normal control result in RUN; unauthorized non-owner access is a potential observed BOLA alert. Bare failure/timeout/unknown result without a security signal is RUN work, not an alert.

Triage legacy zap-derived-observation rows before counting. Keep healthy results, fixture errors and limits in RUN, preserve old raw/history, and do not assume every matched/suspected/inconclusive label identifies an alert. Apply the [canonical alert identity and counting rules](zap-result-boundary.md#alert-counts-and-identities), keeping occurrence and mapping counts separate. Map only semantically relevant original criteria; full criterion coverage is not the purpose of SCOPE_ALERTS.
