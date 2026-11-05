# Single-table Google Sheets output

Apply the [agreed assessment policy](assessment-policy.md). The user has a connected Drive plugin and manages sharing. Build/update the eleven-column design; no bidirectional human-edit or permission-management workflow is part of this task.

## Scope and run identity

The user-facing deliverable for the single project + security catalog workflow is one native Google Sheets file on Drive containing one worksheet and one assessment table. One row represents one original catalog criterion, preserving catalog order. Account for the whole supplied catalog; when the user selects a subset, keep the other catalog rows explicitly outside scope without assigning tests to them. Do not split criteria, test cases and findings into separate tabs. Skill-only discussion, editing and audits do not require a new assessment spreadsheet.

A run means an assessment episode, not a tool invocation, individual scan, retry or chat session. Continue an unfinished run in the same file. Local repair/targeted continuation stays in the same run/file. A separately assigned retest or new assessment gets a new file and a reference to the preceding run when relevant; build drift alone does not mandate a whole-product retest. Preserve historical results; do not create a fresh file merely to retry a failed write. Do not migrate legacy verdicts to v2 through spreadsheet formatting.

Above the table, show product/project, verified target/environment, assessed build/version when known, run ID, assessment status, assessment dates and last successful synchronization time. Mark unknown context explicitly. Use a recognizable file title such as `ZAP — <project> — <environment> — <run ID>`.

## Visual specification

Use the bundled [layout reference](../assets/assessment-sheet-reference.png) as the visual target. All example criteria, ratings, observations and EV references in the image are fictional, not facts or usable evidence links. Replace them with the actual catalog and reviewed evidence. The screenshot is a layout example, not an authoritative severity assessment.

- Keep columns A:K in the order below. B, I, J and K are wide text columns; D:H are compact numeric columns. Suggested starting widths in pixels: 100, 310, 200, 95, 110, 95, 105, 130, 400, 260, 340; adjust for legibility.
- Use a solid dark navy header with bold white text, light gray borders, white body cells and a readable sans-serif font. Use restrained risk colors for D:G and a distinct pale fill for H. Wrap text, vertically center cells, align narrative text left and status/counts centrally. Size rows to show all content; do not truncate evidence or next actions.
- Freeze through the table header, filter the complete table, and avoid merged cells inside the filter range. Metadata above the header may span cells without changing the table schema.
- In C, use status chips or equivalent cell fill and bold text: red for Không đáp ứng, green for Đáp ứng, blue for Đang kiểm tra, amber for Chờ điều kiện, neutral gray for Chưa kiểm tra, Không áp dụng and excluded rows. Colors never substitute for status text.
- Render genuine accessible evidence hyperlinks in I or cell notes. Never fabricate EV URLs to mimic the picture. Inspect available Sheets formatting capabilities and read back formatting or inspect a preview as well as values; report material limitations.

## Eleven columns

Keep these columns in this order, with exact user-facing labels:

1. **Mã:** stable criterion ID; retain catalog name/revision and source location in the criterion cell or a note.
2. **Tiêu chí bảo mật:** original catalog wording; distinguish any approved interpretation and expected behavior from the original. Preserve tested boundary, actors, states, methods, case IDs and material untested portions in a note or I, distinguishing planned from performed work.
3. **Trạng thái:** current progress or supported final verdict under the canonical workflow.
4. **Cao:** count of distinct mapped native ZAP alerts whose native rating is High.
5. **Trung bình:** count of distinct mapped native ZAP alerts whose native rating is Medium.
6. **Thấp:** count of distinct mapped native ZAP alerts whose native rating is Low.
7. **Thông tin:** count of distinct mapped native ZAP alerts whose native rating is Informational.
8. **Only observed:** count only of distinct mapped tester-observed security findings with no corresponding native ZAP detection established. This includes admitted ZAP-derived observations and source/config/runtime findings that support or contradict the criterion. It excludes healthy controls and bare uncertainty. Tester-assigned levels never enter D:G; describe their distribution, evidence origin, IDs and limitations in K and the supporting evidence index.
9. **Quan sát / Căn cứ:** for each mapped native alert or Only observed finding, list its stable ID, origin, rating and rating source, triage status, concrete observation, why it maps to this criterion, and an accessible evidence reference supporting that particular record. Distinguish suspected from confirmed, and record meaningful limits. Summarize healthy/non-finding observations needed to support the criterion verdict, including when there are no findings. Do not fabricate evidence. Where cell space is insufficient, use a clearly linked sanitized accessible supporting item or cell note; preserve the per-finding association.
10. **Việc tiếp theo:** remaining checks, prerequisites, recommended remediation or reopening condition. Distinguish proposed product fixes from authorized testing; do not imply they were performed or assigned.
11. **Ghi chú:** concise explanation for rows whose counts and status can be misread, including non-native Only observed findings, one finding reused across criteria, repeated native records from one detector/root cause, or alerts that do not contradict the criterion's exact oracle.

## Alert counts per criterion

Count distinct stable alert identities with defensible criterion mappings in the reviewed snapshot, following the [result boundary](zap-result-boundary.md). Include admitted suspected and informational alerts; alert counts are not counts of confirmed vulnerabilities. Deduplicate re-reads, not distinct native records, and preserve identities, provenance and grouping. Do not count requests, instances, retries, repeated exports, healthy observations or mapping associations as alerts. An alert can map to multiple criteria and counts once in each relevant row; do not sum row counts as a unique run-wide total.

Use only native ZAP ratings as recorded in D:G; do not silently normalize or change them. Tester-assigned levels for Only observed are descriptive metadata in K and the evidence index, never spreadsheet risk counts. If a native rating does not map defensibly to the four categories, or is absent, do not invent one: list the native alert and unknown/unmapped rating in I, state that the native ZAP risk distribution is incomplete, and give the review next action in J.

Only observed identifies observed security findings without a corresponding native detection established, not all observations manually reviewed. It may include source/config/runtime findings without turning them into ZAP-derived coverage. Its count is independent of D:G because those four columns are native-ZAP-only. Cross-reference possible native/observed duplicates and record uncertainty; do not claim a confirmed absence of native detection when matching has not been reviewed. If matching is incomplete, show `—` in H and explain the gap in I/J rather than guessing. Preserve native and observed records and their distinct counts in internal projections.

Use numeric `0` for a risk category only after the relevant available alerts, mappings and ratings have been reviewed and none belong to that category. Use `—` where the relevant data, mapping or classification is unavailable or not reviewed; explain the gap in I and next action in J. Known reviewed counts may be shown while execution or collection is incomplete, but identify them as **tạm thời** in I and specify remaining work in J. For excluded or not-applicable rows without meaningful mappings, use `—`. Zero alerts or risk counts never prove the criterion passed. Each displayed count must reconcile with the identified alert records and their individual supporting evidence; incomplete evidence must be disclosed and not represented as verified proof.

### Mandatory delivery projection

Before writing the managed table, create one reviewed projection from the retained run and result artifacts. It must contain:

- every retained native alert identity, detector/rule, native rating, confidence, occurrence metadata, source/session provenance and either one or more criterion mappings with rationale or an explicit unmapped reason;
- every admitted observed finding identity, evidence origin (`zap-derived-observation` or `source-config-runtime`), traceable operation/readback, triage status, tester rating and rating basis when assigned, criterion mapping rationale, and native-match state (`matched`, `possible` or `none-established`);
- for each criterion, the exact contributing identities, D:G counts derived only from native ZAP ratings, H derived only from observed findings whose native-match state is `none-established`, the descriptive tester-level distribution for K, and any incomplete mapping/rating/matching flag;
- a reconciliation summary whose mapped and unmapped identities account for the complete reviewed alert population. Occurrence counts stay separate and never replace alert counts.

Do not copy an operation-block alert total into criterion rows. Reconcile alerts across all completed blocks and the retained scanner snapshot, including records discovered before or after a block-specific window. A block-specific review may establish provenance and occurrences without establishing catalog mappings. Preserve it, then add a new derived projection rather than editing the historical review.

If the reviewed projection is incomplete, keep the affected cells as `—`, identify the exact missing review, and do not claim the table is synchronized. Once the projection is complete, a row with no mapped alerts may use numeric `0`; the projection, not absence of prose, is the basis for that zero.

## Status and aggregation

Derive display values from reviewed working state, not from alert counts or the success of a scan/export:

- **Chưa kiểm tra:** no evaluation observations yet; retain pending verdict. A drafted plan or unapproved candidate observation is not a supported final conclusion.
- **Đang kiểm tra:** execution/readback/review is underway or required cases remain unfinished. Preserve any known violation in I even while C remains pending under an all_cases rule.
- **Chờ điều kiện:** a concrete prerequisite/approval/access dependency currently prevents the remaining check; specify it in J. Work on independent ready cases. Do not label unscheduled feasible work as waiting.
- **Đáp ứng:** canonical `met`, limited to the approved scope and sufficient evidence.
- **Không đáp ứng:** canonical `unmet`, supported by a valid contradiction of the approved expected behavior.
- **Không áp dụng:** product-grounded inapplicability with explicit basis; the only final `not_evaluable` representation (reason `not_applicable`). Missing evidence and method/access/capability limits remain **Đang kiểm tra**, **Chưa kiểm tra** or **Chờ điều kiện**, with a pending verdict and an exact next action. Do not use the historical final label “Không đủ điều kiện đánh giá”.
- **Ngoài phạm vi đợt này:** only for an explicit user-selected subset or exclusion. Retain the catalog row and scope basis; it is neither tested nor passed and adds no testing obligation. Missing runner support does not justify exclusion.

Aggregate all planned cases under all_cases for newly prepared criteria; preserve the criterion's evidence obligations. A failed case does not hide other required unfinished cases. Preserve a known violation in the observation cell even if the criterion still has pending work. Zero alerts never implies `Đáp ứng`. Assessment completion and security outcome remain separate.

One operation/observation may appear as evidence in several criterion rows when compatible and semantically relevant. Retain the same operation/finding identity, but derive C, I and J independently for each criterion. An observation reused across rows is not a new request or new alert; different required stages or oracles remain separate case obligations.

## Create, update and verify

Use available connected Google Drive/Sheets tools and their applicable skills when actually creating or editing the file. This reference specifies the output behavior; it does not claim an automatic exporter already exists. The user's instruction to produce this Drive output authorizes creation and content updates for that assessment, not public sharing, permission changes or unrelated publication. Use the supplied destination folder when specified; otherwise use the connected account's default location without inventing a folder or changing access.

Create the file in the final delivery turn if none exists. Reuse the existing file bound to the run and preserve all catalog rows, including explicit exclusions. Record actual file ID, URL, worksheet identity and run association in private `driveOutput` immediately after creation. Retain status pending/verified/outdated/failed, lastVerifiedAt, last synchronized source revision/snapshot and exact remaining publishing action. This metadata is agent-maintained, not an automatic reviewer gate. A sanitized report may include the output URL but never Drive credentials.

Publish once in the final delivery turn after assessment and resource reconciliation. Keep intermediate milestones and usage-limit checkpoints private. If the user explicitly ends the run and requests partial delivery, publish the reviewed snapshot once and label it interim. Update rows by stable criterion ID rather than blindly appending. Write the assessment-managed table range from the reviewed assessment snapshot and preserve the agreed design. Human-edit reconciliation/bidirectional synchronization is out of scope; spreadsheet edits do not create new authority or evidence. Do not alter unrelated ranges/files. Publication reflects the reviewed assessment state and cannot create approvals or alter the oracle.

The coordinator may assign the exact reviewed values and formatting for an existing managed range to the [Drive delivery worker](delegation-policy.md#drive-delivery-worker). The coordinator owns file binding, independent verification and delivery status.

After writing, the coordinator reads back the spreadsheet to verify run identity, exact eleven headers, risk and Only observed counts and their reconciliation to distinct mapped finding identities and individual evidence, criterion IDs/order/row count, displayed conclusions, explanatory notes and material row content against the reviewed source snapshot. Check wrap/freeze/filter/header/status formatting and linked evidence access in the intended location; a bare local pointer or invented `EV-01` URL is not a usable Drive link. Mark an output verified only after successful readback. When new reviewed results differ from the last verified snapshot, mark delivery outdated until synchronized and verified again.

If creation has an uncertain result, reconcile retained file IDs and available Drive metadata before creating a replacement. If a delegated write is uncertain, apply the [single-writer reconciliation rules](delegation-policy.md#drive-delivery-worker) before retrying. If synchronization fails, preserve local results, record what was last verified and the exact remaining publishing action, and report the Drive output as pending or outdated. Continue independent authorized testing when appropriate. Do not rerun tests to repair a spreadsheet write, fabricate a URL or claim successful delivery. Publishing failure is separate from the assessment's evidence-based completion status.

## Evidence and handoff

Keep RUN, ALERTS, SCOPE_ALERTS and private execution state as internal evidence/recovery data under their supported contracts. They are not mandatory additional user deliverables or extra tabs. The spreadsheet is a user-facing projection, not an executable journal, an approval source or a replacement for retained evidence.

Treat column I as an evidence index, not an embedded report. Keep only the criterion's case/operation IDs, alert IDs or grouped range, short disposition and one or more genuine links. Put the detailed observation, proof, limits, per-alert route/message data and rating rationale in sanitized accessible supporting material. Upload only the material needed to make the index usable, within the authorized destination; do not publish tokens, cookies, passwords, sensitive raw traffic, private local paths or secret-bearing query values. A shared index document is acceptable when every criterion and alert is directly searchable by stable ID; separate documents are optional. If an accessible link cannot be supplied, explain the evidence-location limitation rather than displaying a false link.

For concise cells, prefer a shape such as `Cases A01, B01 • native 10038: IDs 571/580/616 • matched • Hồ sơ chứng cứ`. Do not paste every case basis into the cell. Verify that the displayed link opens the intended sanitized item and that each displayed count can be followed from the criterion index to the underlying alert identities.

Lead the product assessment handoff with the verified spreadsheet URL, synchronization status and whether results are interim or final. Give criterion outcomes and exact remaining work concisely; no mandatory three-JSON link list is added. Internal report links may be supplied when requested or necessary for evidence access. If Drive is unavailable, report delivery pending/failed and the exact connection/write/readback needed; a local fallback is not fulfilled Drive delivery. A successful final handoff requires both the appropriate assessment conclusion and a verified table reflecting it. A new link, successful write or completed table does not establish product safety or successful remediation.
