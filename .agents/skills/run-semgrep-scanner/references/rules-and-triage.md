# Select rules, extend checks, and triage

## Starting local library

Read the [catalog](rule-catalog.md). Five bundled YAML files preserve IDs/severity/confidence and have TypeScript/NestJS/TypeORM, React/browser, Docker/Compose/nginx/npm limits. They are not a multilingual library or default policy. Bcrypt <10 and MinLength 0..7 are policy-dependent heuristics; name regexes and path filters have blind spots.

Select by [question bases](track-intents.md) and actual source. Inspect languages/paths/patterns/taint/engine. For other stacks, inspect repository/local rules → applicability → useful custom rules with fixtures → feasible manual review → remaining gaps. Missing rules do not imply N/A. Generic regex does not provide the same semantics as structured-language/taint analysis.

## Select or create a question-specific rule

1. Inspect available repository/local configuration and rules, including remote references, autofix, engine requirements, filters, and suppressions.
2. Select a security detector for a specific hypothesis, or a search detector for sink/call-site inventory. Record inventory purposes separately from vulnerability claims.
3. Read product abstractions before declaring sources/sinks/sanitizers. Keep product mappings outside the shared core; do not reuse another product's route/role/ID assumptions.
4. Use code structure/metavariables where appropriate; regex can suit text/configuration but does not imply parser/semantic coverage. Uninspected names such as “safe”/“sanitize” do not justify exclusions.
5. Test new/changed rules on representative positives and negatives. Taint tests include untrusted-to-sink and correctly controlled cases, plus literals when relevant. Record the fixture cases and observed results. Label product-specific rules written by the agent as `agent-authored` and record rule ID, version or checksum, and limits. Then scan actual source and triage. Synthetic tests establish only those cases.

Extend the local library when assigned. Do not automatically fetch Registry rules, use private source in Playground, or upgrade engines. Use a Registry rule only as an authorized, inspected local copy with recorded provenance and version or checksum. Record additional rule provenance/engine rather than calling it the checked bundled set.

## Triage a match

Read full context and enough call paths to answer: who controls input; whether it is constant/server-generated; which SQL/shell/HTML/path/network/credential/persistence sink matters; whether validation/encoding/authz applies to the same data/path/context; where policy originates; whether global guards/repositories add constraints; whether another path bypasses them; whether source is actually relevant implementation; and which parts the engine versus tester observed. A missing caller in one search does not establish dead code.

Retain native IDs/locations/severity/confidence and necessary messages. Redact sensitive interpolation without changing meaning. Use minimal sanitized evidence and leave existing suppressions and target code intact.

- `needs-review`: insufficient context or material uncertainty, with next steps.
- `supported`: source supports the stated issue/risk, with verification level and assumptions; does not imply runtime exploitation.
- `false-positive`: incorrect pattern or effective inspected control, with a concrete rationale.
- `not-applicable`: grounded scope/feature applicability decision; preserve the record and reason.

Accepted risk requires a supplied authoritative decision and differs from false-positive. Low severity does not authorize acceptance. Needs-review is valid but affects completion when assigned triage remains unfinished.

## Manual findings

Record supported manual discoveries as `manual-source-review`, with null rule ID/native severity/native confidence. Keep tester judgments separate; never invent native traces or inflate Semgrep coverage. When native/manual observations support one issue, link them and retain original occurrences rather than counting independent bugs.

## Assign reviewed risk

Rate supported issues detected by Semgrep using the evidenced security impact, affected scope, exposed actors, required privileges and other prerequisites, and the effective controls in the assessed source state. Include evidence IDs and assumptions in the rationale. Require a retained Semgrep match that actually detects the same issue. Manual source review can verify or contextualize the detection. Reconcile the rating at the issue level and project it once per mapped criterion. Record findings and material observations made solely by the agent in Only observed without assigning a reviewed risk.

- **Critical** — Exceptionally severe impact across a broad boundary with few prerequisites, such as unauthenticated disclosure of sensitive data across many tenants.
- **High** — Serious impact within an established boundary, such as an ordinary account accessing sensitive data belonging to another tenant.
- **Medium** — Clear security impact with narrower reach or substantial prerequisites.
- **Low** — Supported weakness with limited security impact in the assessed context.

Use the internal `unrated` value for a supported Semgrep-detected issue whose risk cannot yet be assigned. Explain it in the evidence and Notes. Record the missing fact and how it could change the rating. Keep observations with insufficient evidence to establish the issue as **Needs review**. A supported static issue can carry a reviewed rating with explicit source-based limits and assumptions about runtime. When those assumptions prevent a defensible rating for a Semgrep-detected issue, use `unrated`.

Keep the original rule severity as a source fact. Semgrep's legacy aliases are ERROR for HIGH, WARNING for MEDIUM and INFO for LOW. Use rule severity as a triage input and record the reviewed risk independently. Informational observations can support criterion evidence without entering risk counts.

## Counting and retesting

Use `RUN.coverage.inventory_candidate_reviews` under the [contract](reporting-and-completion.md), including round/rule/location/index, questions/reviews, candidate kind, inspected context, disposition, and next step even without an ALERT. Collector grouping by location preserves every occurrence/native-message reference; tester review determines shared callers/controls and root causes. Same line/rule does not establish one issue, and receiver/path names do not automatically establish false-positive.

Separate native matches/occurrences, aggregated observations, and unique issues. Multiple rules/rounds do not necessarily mean multiple vulnerabilities; document grouping and do not merge distinct root causes solely by rule. Preserve native severity; tester priority/impact needs separate rationale rather than arbitrary WARNING-to-CVSS conversion. A disappearing match caused by filtering/rule changes is not a verified fix.

Follow [evidence](evidence.md) and [v2 reporting](reporting-and-completion.md). Manual call paths remain source-review; native-dataflow requires an actual inspected native trace.
