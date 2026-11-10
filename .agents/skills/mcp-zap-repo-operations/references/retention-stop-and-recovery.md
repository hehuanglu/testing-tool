# Working-session checkpoints, retention, and recovery

Preserve recovery state throughout [criteria-driven authoring and execution](criteria-driven-workflow.md), including incomplete drafts and stopped or revised plans. Recovery does not authorize fresh effects; execution still needs current approvals and admission. User delivery follows the [Drive table contract](single-table-drive-output.md); JSON/native artifacts below are internal working data.

Before approved v3 execution effects, preserve the official state directory, exact packet and coordinator directory. Verify the Gate 2 binding and retained executor evidence on continuation. Original packet readback, reconciliation and cleanup remain bound to durable task ownership after stop or revision. Fresh dispatch requires current approval and admission. Historical v2 continuation still verifies both of its approval bindings. The legacy inspect-resume helper validates v1 continuation fields.

Use for checkpoint/resume and complicated attempts, rather than automatic fault/HA/repeatability campaigns. Deliver the [Drive assessment table](product-assessment-handoff.md); retain RUN/ALERTS/SCOPE_ALERTS internally without extra proof packages.


On worker handoff, retain the task and artifact references, unresolved work, and any intent/ACK and lease bindings before retiring or replacing the worker. Follow the [retirement rules](delegation-policy.md#retire-workers-after-handoff). For an uncertain Drive write, use [delivery reconciliation](delegation-policy.md#drive-delivery-worker) before scheduling another writer.

## Operator schedule and crash checkpoint

Use private intake notes for authorized reconnaissance before a valid v3 plan structure exists. Record authority, target, intended action and readback before traffic. Store registration accepts draft state and preserves the single Gate 2 plan approval.

For a managed workflow, the explicit registry and verified current pointer identify the working generation. RUN holds workflow content and evidence. OPERATOR holds schedule, repairs and delivery outside the approval digest. Journal and executor receipts record effects and ownership. `state-render` regenerates the checklist and continuation prompt as projections. A process can resume from the store and journals even if projection generation or the final message was interrupted.

1. Resolve the known assessment and inspect the store and coordinator. Use the bundled interpreter and helper contract below.
2. For an interrupted acquire or release transaction, use `state-recover-leases --state-dir DIR --packet PATH` with the retained original packet. Recovering a lease only updates ownership metadata. Reconcile pending effects from retained executor evidence. An ACK leaves terminal state and evidence sufficiency to readback.
3. Run `state-next` against the current state directory. Review its reason, dependencies and pending effects. Evidence-index entries are lookup hints. A future `nextWakeAt` is a scheduling fact. Runtime admission still checks the same subject, credentials, fixture, version, effects and controls.
4. Persist reviewed worker evidence with `state-merge` and coordinator metadata with `state-commit`, each against the expected generation and a stable commit ID. On ambiguous response, retry with the same ID and input. Stale generation requires reading and reconciling current state before a different commit. Continue independent preparation or source review while a branch waits.
5. Repeat selection through resource review and final delivery. Verify the same Sheet by connected readback and commit the bound receipt. A completed block or a projection is progress. Apply the stopping rule using actual dependencies and user boundaries.

Lease transactions acquire the assessment lock before the shared resource lock. Durable acquire intent precedes lease files. Release intent precedes cleanup and the release commit follows cleanup. Legacy release leftovers can be cleaned with the matching original packet. Quarantine a legacy orphan with no journal intent and verify active legacy claims with missing leases before intervening.

A torn or corrupt journal allows forensic inspection of its valid prefix. Inspect recovery reports incomplete certainty, journal path and hashes. Open a journal-integrity repair with those refs and reconcile them with retained executor evidence. Writable journal repair requires separate evidence and a recovery decision. Keep effects, lease mutation and final completion blocked in degraded state while independent offline work proceeds. The callback still holds the assessment lock.

Legacy raw `--run` v2 consumers remain available. Report projections remain reporting artifacts. Use explicit registration from an authorized private RUN. Avoid selecting a fallback by filename, size or mtime when the registered pointer fails.

## Working-session checkpoints

The assessment is the user's assignment across working sessions/context windows. A local work unit addresses a useful question or preparation/diagnosis objective. A technical round/allocation is bounded executor work; assessmentRound is the separate stable lifecycle of the assigned testing round across such allocations. An attempt/authentication session identifies actual execution or login history. An agent work session is none of the ZAP, application, or authentication sessions; changing context neither renews those sessions nor changes permission.

Default to continuing valuable, feasible work within assigned scope while the available context supports safe execution. A technical round/allocation bounds scan/mutation impact and enables readback; ending it does not end the agent session or require a user continuation prompt. After reconciliation, select the next related question, preparation or repair and execute it autonomously, reusing current actors, fixtures, runtime and knowledge.

Before a voluntary context handoff, identify the next useful block and what relevant knowledge is still usable: product/route/role semantics, expectations, fixture mappings, verified repairs and current readback. Continue when these support safe work. Explain the concrete context difficulty when they do not, for example unresolved conflicting bindings that cannot be tracked safely through the next dependent sequence. No precise capacity estimate or exhaustion proof is required. Merely changing fixture, vector, role, lifecycle or topic, finishing the opening objective, or saying “avoid confusion” without the specific difficulty is insufficient by itself. Persist/reconcile state and continue when that resolves the difficulty; do not manufacture a blocker to justify a handoff.

Keep journals and pending state current throughout execution, and keep intermediate reconciliation private. Reserve Sheets writes for final delivery. These recovery saves are not end-of-turn handoffs. Checkpoint to hand off when remaining usable context is unsuitable for the next coherent work block, a real dependency prevents further useful work, the user requests a stop/handoff, or a specific operational reason requires it (for example, owned producer supervision cannot continue safely). A dependency affecting one branch does not stop independent work. State the actual reason; completing a small round, preparation step or report export alone is insufficient.

For a dependency-based stop, apply [open-work decisions](local-remediation-and-continuation.md#decisions-for-open-work): distinguish agent-owned diagnosis/preparation still feasible within authority from missing access or a user policy decision. Name the remaining investigation or exact external condition rather than requiring the user to produce unspecified “new data”. A stop for context may leave that investigation feasible; record the context difficulty and do not relabel the investigation as externally blocked.

Preparation can be valid progress at such a checkpoint without a fabricated scan. Do not require completing the whole assessment in one window or wait until context is nearly exhausted to save state. No fixed track order, window count, request/round/token quota, context percentage or exhaustion proof is required. Use judgment about the next block, without claiming precise remaining capacity. When expiry applies, establish the subject, deadline and pre-expiry control early, then reserve post-expiry readback for the last execution group before delivery. Continue independent ready work while waiting and follow the [TTL scheduling and resumption rules](business-work-blocks.md#put-ttl-readback-last).

Eligible work may remain at checkpoint. Preserve it as feasible next work with preparation and a concrete first step; do not relabel it blocked or seek renewed permission merely to hand off a local work unit. Open obligations keep `taskCompletion: partial` and `handoffClosesTask: false`. Checkpoint metadata cannot promote observations, coverage, security verdicts or task completion. Complete a current assignment or explicitly assigned stage under the [v2 verdict/completion rules](criteria-driven-workflow.md#verdicts-and-completion). A user stop or diagnosed absence of valid continuation ends work with unresolved scope still partial; neither supplies obligation coverage or a security conclusion. A fully reviewed legacy round may historically carry completed-with-limitations with partial legacy coverage; this does not override v2 criterion verdict/completion rules.

### Distinguish a request to operate from a request to stop

“Continue”, “run again” or “a new operating pass” normally initiates useful work in the assigned assessment; it does not by itself mean stop after the first objective, a chosen scan count or report export. Do not turn an agent-selected block into a user-requested stage boundary. When useful authorized work remains and the context knowledge supports it, announce the next objective and proceed rather than asking for another continuation prompt.

Honor actual user boundaries: an explicit stop, a specified time/operation budget, “only this endpoint/stage”, or “stop and report after this block”. Complete narrow assignments without expanding them. Record the actual restriction when citing a user-imposed boundary; absent such a restriction, use only the established context/dependency/operational checkpoint reasons. If a prior RUN labels a selected block as user-requested, check that interpretation against the actual request; preserve historical results but do not inherit that label as a new stopping rule. A genuine earlier stop does not forbid a subsequently authorized resume.

### Official location and minimum data

During intake, resume from private notes and discovery records. For managed v3 execution (or retained v2), keep the official locator in the explicit registry or retained state directory; the Drive table and sanitized reports may reference it but never replace it. The older convention of moving a user-facing continuation pointer to the three-file bundle applies only when interpreting legacy checkpoints; it does not make a report projection executable. Keep scope/questions/observations in their existing structures and reference executor journals/native outputs for actual ACK/state. No duplicate operation journal or additional user-facing handoff file is required.

Compact reports omit technical provenance such as `evidenceRefs`. Keep references to the existing working inventory/plans/journals needed by an executor in `nextActions.readFirst`; do not fabricate missing provenance or treat sanitized report inventory as an admitted plan. Those working artifacts remain outside the three-file handoff directory.

Illustrative metadata, prepared by the agent rather than supplied by the user:

```json
{
  "version": 1,
  "status": "checkpointed",
  "reason": "external-dependency",
  "updatedAt": "2026-10-31T08:00:00Z",
  "currentFocus": {
    "objective": "Answer whether changed titles reach owned update processing.",
    "questionIds": ["q-update"],
    "closureConditions": ["Read actual changed-title processing with valid owner identity and current object version."],
    "objectiveOutcome": "partly-met",
    "progress": "Owner baseline read; version-dependent processing remains open."
  },
  "nextActions": [{
    "questionIds": ["q-update"],
    "action": "Read current object version, then prepare a valid sibling for the missing processing test.",
    "readFirst": ["private fixture ledger reference"],
    "dependsOn": []
  }],
  "revalidate": [{
    "subject": "actor/fixture binding",
    "reason": "Membership, version, expiry and quota can change.",
    "readVia": "private actor/fixture reference",
    "affects": ["q-update"]
  }],
  "userGuidance": {
    "contextRecommendation": "continue-here",
    "reason": "The owner and processing model remain understood; only the externally supplied actor credential is unavailable.",
    "userAction": "After the credential is available privately, send resumePrompt in this chat.",
    "resumePrompt": "Use $mcp-zap-repo-operations to continue from /absolute/official/RUN.json. First reconcile pending operations, then read the object version and prepare the missing processing test. Revalidate only required live dependencies; do not replay completed or unknown starts/mutations."
  },
  "pendingOperations": [],
  "resourceDisposition": [{
    "resourceRef": "owned fixture ledger reference",
    "disposition": "retain",
    "reason": "Needed next; recheck ownership/state/expiry before reuse."
  }]
}
```

`currentFocus` objective/closure/outcome fields above illustrate additive agent-authored metadata, not a mandatory new schema or machine-verified truth. Preserve the original objective and outcome if later blocks are selected; use existing progress/operation records rather than replacing an unmet goal with a successful easier one. Missing legacy fields need selective recovery, not a fresh assessment. `status` describes the work session only. Retain provenance for stable product/source/deployment/route/role/schema facts, expected behavior and labeled assumptions. Keep last-observed actor/fixture ownership, status, version, quota and credential/session expiry through private references. Retain results with actual method/role/input/state and observation meaning: auxiliary/site-wide requests or zero input probes remain such, regardless of terminal status/counts. Never copy required units into observed units.

Keep the current conclusion distinct from historical limitations. When verified policy, build, readiness or retest results supersede a continuation statement, update the relevant current summary/limitation/next action and identify the prior statement as historical with its context and reason for replacement. Preserve raw results, original findings and earlier coverage gaps; a new successful fixture does not retroactively complete an old blocked objective. On resume, resolve contradictory summaries from linked policy/results and matching build/state rather than reopening a superseded question or choosing the newest sentence alone. Use existing fields and references; no new schema or history file is required.

Use `nextActions` for specific work, its question/responsibility links where known, initial readback references and dependencies. No placeholder operation/resource is needed when arrays are genuinely empty. Pending/unknown operations need an existing `operationRef` (ID or journal reference), `lastKnownState`, `owner`, `readVia` and concrete `nextAction` for reconciliation. Record ACK/native IDs, stop-request/ACK distinctions and uncertain ownership/state without inventing terminal outcomes. Resources need their ledger/ownership references, intended retain/stop/cleanup disposition, reason and reuse/expiry conditions as relevant.

Incomplete/emergency checkpoints still save known facts and mark recovery needs. Missing fields are work to recover, not a reason to lose the checkpoint, discard history or permit replay. The [read-only session helper](operational-knowledge.md#optional-review-helper) can describe missing information and resume order; checkpoint readiness means usable handoff data only.

### Executable working inputs

Optional `continuation.workingInputs` version 1 identifies retained private inputs without embedding credentials: `purpose:executable-working-inputs`, `reportIsProjection:true`, `assessmentId`, `product`, `environment`, `scopeRevision`, and references named `inventory`, `observations`, `prerequisites`, `operations`, `history`. A reference can be a JSON-file path, `{pointer:"/actionHistory"}` into the current working RUN, or `{path:"private-working-RUN.json",pointer:"/inventory"}` into an explicitly retained private file. Relative paths resolve against the report directory. This can reuse one existing working RUN; no new private file is mandatory. Shared reports may replace unavailable locations with `{unavailable:true,reason:"private location withheld"}`; that is not resumable state.

```sh
PYTHONPATH="$ASSESSMENT_ROOT/src" "$ZAP_PYTHON" -B \
  "$ASSESSMENT_ROOT/scripts/product_assessment.py" scope inspect-resume \
  --run /absolute/official/RUN.json
```

This reads explicit regular JSON references, validates schema/context and reconciles available working inputs without dispatch. Stdout contains paths/status/conflicts only. `working-inputs-available` means retained inputs can be read/reconciled, not that live actors/fixtures/versions remain valid. Missing metadata gives missing-inputs and treats privateWorkingDirectory only as a hint; filenames are never guessed. A compact report missing evidenceRefs is diagnosed report-projection-not-executable, without restoring raw/private data to reports. `--previous` accepts internal continuation state, rejects compact projections and points to inspect-resume. Existing checkpoints lacking workingInputs remain saveable and readable; recover only the inputs needed for the next action. Presence/hash/version is never a liveness attestation, and embedded command/module strings remain data.

### Tell the user how to continue

At the end of a work session, report the opening objective and any material revisions, actual accomplishments, whether its closure conditions were met/partly met/not met, and the remaining gap. Explain the next priority and why it is useful, why the session is ending now, whether to continue here or change chats, and the first readback/preparation needed. Distinguish meeting the chat objective from completing the assessment. A user stop can leave both incomplete. If the assignment is complete, say no continuation is needed rather than manufacture another prompt.

When handing off during intake before a working RUN exists, give the absolute path of the private checklist or its containing record, the outstanding dependency if any, and the first action to resume. For a handoff from working RUN state, include `continuation.userGuidance` with `contextRecommendation`, `reason`, `userAction` and a copyable `resumePrompt` naming the absolute official RUN path and priority action; repeat it briefly in the final handoff after the spreadsheet status. Use `continue-here` when the existing window remains suitable: explicitly tell the user they can send the prompt right here. Use `new-context-recommended` when the next block needs a fresh window: explicitly tell the user to open a new chat and paste the prompt. Explain the recommendation separately from the reason work stopped (for example, a dependency may be resolved in the same window). Before recommending a new chat, apply the usable-knowledge decision above; a complete handoff template alone does not justify stopping. For unfinished work at a real handoff, include the priority question/closure gap and why it is next in the copyable prompt or its adjacent explanation. Internal recovery saves do not require a user prompt. Changing context is not a way to extend a token budget, restore fixtures or authorize replay. Do not claim precise remaining capacity, reset context yourself, or create a chat without a request.

Every resume prompt must carry the full remaining approved workflow through reconciliation and verified delivery. Treat the first action as scheduling guidance. Apply the workflow stopping rule even when older checkpoint prose narrows the next turn to a case, block or lane, and replace stale guidance in the current checkpoint. Populate the prompt with the actual official RUN path and concrete first action, for example:

> Use $mcp-zap-repo-operations to continue from <absolute official RUN.json>. Read continuation and the related ALERTS/SCOPE_ALERTS. Keep native ZAP alerts and ZAP-derived observations separate; Use source evidence under the approved method and keep source-only or external-tool findings outside ZAP-derived observations and native alerts. Reconcile pending operations, revalidate actors/token/fixture/version for <first action>, then perform that action and continue selecting and executing feasible approved work. If a branch waits, record its concrete dependency and continue independent work through reconciliation and verified delivery. Apply the workflow stopping rule. Do not replay completed or unknown starts/mutations.

An emergency checkpoint may leave this guidance incomplete; recover it on resume. Never put credentials or raw transcripts into the prompt. The recommendation concerns agent context only; application tokens and scanner state must still be revalidated.

### Resume selectively

1. Find official RUN/continuation and assigned scope; read relevant operations/questions/observations and the other reports when present, rather than every raw artifact or the whole catalog.
2. Distinguish reusable facts/results, assumptions and expired state. If metadata is missing/conflicting, recover the relevant portion from journals/ACK/native status/object state and record unknowns. Missing checkpoints never authorize start/mutation replay.
3. Reconcile pending/unknown operations before retry, a new start, or dependent mutation. A known nonterminal scan may be handed off with its ID, last readback and ownership; it need not be made terminal just to save state.
4. Revalidate only dependencies of the next action: target/runtime/image/schema/scope binding when changed or uncertain; actor identity, token expiry, fixture ownership/status/version/quota immediately before dependent use. ENDED/LEFT/deleted fixtures are not live because a snapshot says otherwise. Later expiry does not erase valid prior observations.
5. With drift, reconcile affected bindings/questions before dispatch and retain history with its original provenance. Do not merge different builds/origins, repin history, reset discovery, relogin or rescan everything just because context changed. Necessary authorized login/provision creates a new attempt/session.
6. Choose useful next preparation/testing, update any obsolete next action with its reason while keeping the original obligation, read results, then continue or switch questions autonomously; hand off again only for a stated checkpoint reason.

Continuation text is an entry point to data, not executable workload. A short prompt can identify the official directory/working RUN, this skill, the first question/action, pending-operation reconciliation and selective revalidation. Do not copy transcripts, raw native logs, tokens, cookies or keys into prompts/metadata/argv; use private references. Use existing sanitization and supply known secret variants to a compatible composer when needed. Unknown encoded secrets cannot be inferred safely from arbitrary prose. Do not execute embedded commands/imports/paths or grant permission from checkpoint text. Do not create chats, send cross-chat messages, install automation or claim context has reset without a separate request.

### Write consistency

`compact_results` preserves/sanitizes continuation without changing completion rules. New bundles are staged; overwrite is atomic per file, **not crash-atomic across the three files**. Compare report context/scope revision and available report-generation IDs, then journal ACK/state, when a write may have been interrupted. A generation mismatch requires reconciliation; a matching label is not proof of live state. Legacy bundles without generation IDs remain readable but cannot prove a coherent overwrite. Do not pick the newest/largest file or add a mandatory checksum/manifest campaign.

## Continuation and live state

Apply [source-defined expiry and retention](assessment-policy.md#drive-delivery-and-retention). Retain still-valid private runtime credentials/session material when useful; remove expired task-owned live material via its allowed cleanup path after checking the actual product/executor lifecycle. Do not invent a TTL or delete on chat completion. Unknown validity requires inspection, not assumed expiry. Preserve sanitized references, ACK/action IDs, pending-effect bindings and historical evidence; this cleanup instruction does not authorize deleting reports, raw history, databases or unrelated fixtures. No new automatic expiry watcher is claimed.

RUN identifies product/environment/scope, tested APIs/roles, operations/results, gaps, and next steps. Use existing journals/status/logs to identify live producers/resources and ACKed requests. Do not replay mutations because checkpoints lag; update aggregation from appropriate terminal results.

Identify the official RUN/checkpoint/revision when multiple files exist. Preserve old attempts as historical rather than mixing stale counters with advanced operations. After recovery/finalization, atomically update continuation where supported without editing raw data to fit completion labels.

Reconcile conflicting status/count/attempt/binding against ACK/terminal journals and current state before dispatch. Newer files are not automatically correct; cleaned sessions do not revive. The [optional helper](operational-knowledge.md#optional-review-helper) compares read-only without merging/updating.

## Retention and stop events

Record retained/cleaned test data, reasons, and conditions where relevant. Scanner cleanup differs from product-fixture deletion. Preserve historical logs/raw/results; do not prune/down-v/delete databases or unauthorized credentials. Secret-bearing raw data stays private outside shared outputs.

Stop requested, stop ACK, and terminal are distinct observations. Do not promise immediate/no-in-flight stops without knowledge. Stop only owned operation/job/resources, rather than shared stop-all or project-name-only ownership. Auth/scope/resource loss stops dependent branches with partial results retained.

Retaining fixtures, stopping producers and scanner cleanup are separate decisions. Saving reports or completing a block does not require stopping/loading the scanner; keep using it within authorization/resources when continuing. Choose stop/retain based on supervision, ownership, resources and actual handoff needs. On resume, use the verified current snapshot/lineage entry rather than adding another helper solely because a new chat or block began; repair mappings only when needed and preserve old data/pins. Do not end a one-use fixture merely to make a checkpoint clean. Do not leave producers needing continuous supervision unbounded after observation ends: use owned executor stop/budget controls or an actual replacement monitor as appropriate. If stop is only requested/ACKed, retain that state and make readback a resume action. Never claim monitoring continues without a real mechanism; passive backlog zero does not establish producer/job/scan termination. Do not change bind/network/TLS/auth or weaken resource gates for resume.

## Caps and unknown outcomes

Respect entry count/rate/time/resources without raising caps/lowering reserves to force completion. Deadline expiry still needs authorized stop/cleanup. Ordinary scans need no fault injection/process kills/ACK-loss/zero-in-flight proof unless assigned or required by actual executor contracts.

Inspect status/ACK/object state/resources before retrying unknown POST/DELETE/start. If unresolved within authority, retain unknown/partial with impacts and resumption information. New login/fresh runs are new attempts rather than fabricated same-session resume. Repair locally under [remediation](local-remediation-and-continuation.md), then continue eligible branches. One producer's cap/gate/stop does not end the inventory-wide [responsibility loop](responsibility-loop.md).

## Legacy round readback and selective reopening

When reading legacy evidence, an assessmentRound ID persists across chats, fixtures and CLI allocations; interpret these statuses under their original contract only. New v2 completion is governed by the canonical criteria workflow. Distinguish checkpointed (pause/context/temporary conditions), stopped-by-user (explicit stop source), completed (no unanswered testing duty) and completed-with-limitations (all residuals accounted with no useful feasible action, but gaps remain). For the current handoff, lead with the spreadsheet URL and synchronization/interim-final status, then assessment lifecycle, coverage and security outcome; legacy round metadata is supporting historical context, not a replacement headline. A properly closed round needs concrete reopen triggers, not an automatic continuation prompt. taskCompletion partial does not itself require more work.

A closed round retains workingInputs and native/journal/unknown-effect history. Reopen for changed scope/build/results/known duties, actor/policy or capability/fixture resolving a dependency, newly found assigned feature, or a new method/remediation assignment; re-evaluate closure without replaying old effects. Finalization is an offline report action and cannot stop or clean resources. Resource stopped status requires actual readback refs matching saved terminal values; no live liveness inference from timestamps. Unknown effect with an available reader must be reconciled. A contained but unreadable effect stays unknown with exact last state/impact/unavailable-reader/no-replay/resource/reopen details; producer possibly still live and uncontained requires checkpoint/escalation.

Implementation-only offline limits are a handoff boundary, not evidence that runtime work is impossible. Retain an unfinished round and the exact input/fixture/readback/cleanup workload for useful runtime facts. No fixed retry count, proof of impossibility, mandatory reviewer or permission-to-conclude flow is introduced.

Commit the optional runtime execution binding before acquire. After acquire or
lease recovery, recompute `state-next` from the official state directory and
continue using the retained packet if the binding verifies. If the selector
asks to resolve a missing binding, compare the packet and durable lease before
recording it. ACK, acceptance and a bare reconciliation label in imported
history leave a durable mutation or start intent unresolved until the reviewed
resolution links exact action and context evidence.
