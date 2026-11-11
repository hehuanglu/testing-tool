# Single-table Google Sheets delivery

Deliver one native Google Sheets file, one worksheet and one table with one row per criterion in the assessment catalog or requested list unless the user requests a different format. Build the table from reviewed private [RUN and ALERTS records](reporting-and-completion.md). Preserve criterion IDs, source wording and order. When delivering a full catalog with a selected subset, retain excluded rows and explain the scope decision. Targeted and setup-only requests use their requested deliverables.

Above the table, show project, assessment ID, source revision/worktree state, scope, engine and version, rule versions or checksums, assessment status, interim/final label and last successful synchronization. Use the user's language for report labels and content. The English headers below specify the column order and meaning.

## Visual specification

Use a dark navy base header with bold white labels, light gray borders, white narrative cells and a readable sans-serif font. Use red for High, amber for Medium and blue for Low, with pale fills of the same hues in the count cells. Use a deeper red accent for Critical and a distinct pale rose fill. Keep the navy header and pale lavender count fill for Only observed.

In Status, use exactly four labels: green for Pass, red for Fail, amber for Not evaluable and neutral gray for Out of scope. Keep these labels and Only observed as written. Show interim progress, coverage limits and pending work in Notes and Next steps.

Keep A, C and D:H compact and B, I, J and K wide enough for wrapped text. Center status and count values, align narrative text left and vertically center cells. Freeze through the table header, filter the full range and size rows to show the content.

## Eleven columns

1. **ID** — Stable criterion ID.
2. **Security criterion** — Criterion wording and traceable source. Use a note for the scoped interpretation, expected behavior or source location when needed.
3. **Status** — Display Pass, Fail, Not evaluable or Out of scope under the [criteria workflow](criteria-workflow.md#conclude-independently).
4. **Critical** — Distinct supported Semgrep-detected issues with reviewed risk Critical.
5. **High** — Distinct supported Semgrep-detected issues with reviewed risk High.
6. **Medium** — Distinct supported Semgrep-detected issues with reviewed risk Medium.
7. **Low** — Distinct supported Semgrep-detected issues with reviewed risk Low.
8. **Only observed** — Distinct material observations made solely by the agent during the Semgrep assessment, backed by source or versioned configuration evidence.
9. **Observations / Evidence** — List mapped issue/finding IDs, disposition, provenance (Semgrep, manual source review or both), reviewed risk and rationale when assessed, native rule ID/severity where present, a concise observation and usable evidence references. Include observations of working controls when they support the criterion's conclusion. Use cell notes or a linked sanitized evidence index for details that do not fit.
10. **Next steps** — Remaining verification, prerequisites, proposed remediation or reopening condition.
11. **Notes** — Actual methods, coverage limits and material skips/suppressions. Identify supported Semgrep-detected issues whose risk is unresolved by ID and explain the gap. Note unresolved triage, partial distributions and shared counts where relevant.

Leave **Next steps** and **Notes** blank when a row has no material action, dependency, limitation, skip, unresolved decision or warning. Do not add filler such as “no action,” routine retest-on-change advice, generic method labels, full-coverage statements or repetitions of evidence already present in the row. Preserve important caveats for Fail, partial coverage and externally blocked conclusions only when the caveat changes how the row should be interpreted or acted on.

## Count from reviewed records

Apply [reviewed risk](rules-and-triage.md#assign-reviewed-risk) only when a retained Semgrep match detects a supported issue. Count each stable `issue_id` once per mapped criterion, even when several rule matches or manual reviews support it. An issue found by both methods belongs in its Semgrep risk column once, if rated. Keep original native labels in evidence. Semgrep-detected issues with unresolved risk appear in Evidence and Notes.

Count Only observed once per distinct material agent-only observation per mapped criterion. Use the issue ID for confirmed agent-only violations and a stable finding or evidence reference for other substantiated observations relevant to the criterion, including controls. Group duplicate references to the same observation. A manual review that only confirms or explains a Semgrep detection stays with that detection. Keep unverified candidates, false positives, bare inventory and excluded observations out of the counts. Record unresolved items in Evidence or Next steps. Use `0` for a reviewed empty bucket and `—` when a count is unavailable, unreviewed or inapplicable. On interim rows, known counts reflect the reviewed snapshot.

## Write and verify

Project only evidence admitted by the [source evidence boundary](tester-context.md#working-conditions). When correcting a mixed-provenance report, review the source evidence again, remove unsupported findings from the current projection, and reopen any dependent conclusions. Verify counts, notes and supplementary ranges against the corrected records.

Before writing, reconcile all rows and evidence references against the reviewed records. Check Semgrep risk counts against mapped issue IDs and native evidence. Reconcile Only observed against deduplicated agent-only evidence, check for double counting, and replace any old Needs review header and managed values on refresh. For source locations, use a verified commit permalink when the evidence matches that commit. Otherwise provide a sanitized file/line and source-state label in an accessible evidence record. Keep private raw outputs and sensitive source out of the Sheet. Write imported text as literal values.

Use connected Google Drive/Sheets tools and the applicable Sheets skill. Persist the spreadsheet ID and URL in RUN and update the same file on authorized refreshes. The user manages sharing. Read back the file and worksheet identity, ordered headers and criterion rows, count values, statuses, links and material formatting. Check that superseded managed rows are absent. Return the verified URL and label the snapshot interim or final.

On a refresh request, project the latest reviewed retained state. If writing or verifying fails, preserve the records and known file identity, mark any previous URL stale or unverified and identify the remaining publishing action. Report assessment and delivery statuses separately and resume publishing from the retained state.
