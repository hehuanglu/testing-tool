# Recovery and delegation audit (offline)

Task: recovery_audit. Status: completed source review and bounded synthetic reproductions. No product traffic, secret/runtime artifacts, source edits, or full test suite. All paths below are relative to `.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment/src/zap_assessment/`.

Reviewed the maintenance/crash-recovery and subagent acceptance sections of `references/operational-validation.md`, and selective context, canonical writer, scheduling/recovery sections of `references/delegation-policy.md`. These require unknown effects to remain non-replayable while independent feasible work remains available. The findings below concern helper recovery behavior, not a demonstrated live product incident or future agent behavior.

## Proven offline defects

### R1 — P1: partial lease release makes cold recovery and retry impossible through the APIs

Location: `criteria_delegation.py:467-468` (release journal precedes multiple unlinks); `:230-253` (released task excluded from active map); `:264-270` (recovery requires every original lease).

With a valid packet holding resources `one` and `two`, release durably appends `released`, unlinks the first lease, then an injected OSError interrupts the second unlink. A real process death at that boundary yields the same disk state. Fresh `resume_next` fails `resource lease lacks retained task journal`. Retrying release fails `missing resource lease`; reacquire fails the orphan check before it can repair. A single-resource failure before its unlink is retryable by release, but normal resume still fails until that explicit retry. This is availability/recoverability failure, not unsafe replay. All workflow review (and therefore independent cases in the same assessment) is blocked. Expected: retain a resumable release transaction or tolerate a verified partial cleanup. Actual: no supported idempotent completion path for partially removed multi-resource leases.

### R2 — P1: acquisition crash before journal commit creates an unrecoverable orphan lease

Location: `criteria_delegation.py:326-328`, `:309`, `:250-253`, `:290-292`.

Reproduction writes the exact synthetic disk image after `atomic_bytes` durably publishes the resource lease and before `journal.append('leased', ...)`. No action has been sent. Cold resume and same-packet reacquire both reject `resource lease lacks retained task journal`; release rejects `recovery packet has no durable task binding`. Reacquire calls `validate_packet` → `make_packet` → `_approved` → `review_workflow` before its acquisition repair logic, so it cannot get past the orphan check. A process kill in this small window can thus stop the whole assessment and reserve the shared resource indefinitely, requiring manual state surgery outside the normal API. Synthetic crash-image reproduction, not an actual kill/power-loss run.

### R3 — P1/P2: ambiguous acquisition journal failure rolls back leases even if leased record persisted

Location: `criteria_delegation.py:328-330`; `journal.py:57-65`.

The acquire exception path unconditionally unlinks its newly acquired resources. Journal append can raise after bytes are written (e.g. fsync or directory fsync error), so the durable log can contain `leased` while all corresponding files are deleted. Reproduction wraps the actual append, lets it fully persist, then raises OSError to model lost persistence acknowledgement. Fresh resume and reacquire both fail `missing resource lease`. No product action has happened, but the stale active journal task blocks the whole assessment. Same transactional family as R2; combine into one finding if avoiding duplicates. Actual disk failure is not reproduced; resulting persisted state and retry behavior are proven.

### R4 — P2: one torn journal tail blocks every task, including independent readback

Location: `journal.py:28-30` (strict trailing-record rejection); `criteria_delegation.py:226-228` (always default strict Journal); `criteria_workflow.py:289-300` (unconditional coordinator snapshot for entire assessment).

Start a synthetic leased task, record intent and ACK, then append/fsync a partial JSON record to represent an interrupted subsequent append. Fresh resume, status and release all fail `Blocked: journal integrity failure`. `allow_partial_tail=True` exists in Journal but no Coordinator path uses it or offers an explicit verified repair. Fail-closed behavior correctly avoids replay; the operational defect is absence of a controlled recovery path, with assessment-wide rather than task-local impact. Retained valid prefix and executor receipt can still exist but cannot be reconciled through these APIs. Do not describe this as loss of durable ACK or successful unsafe replay.

## Proven integration limitation, not a two-file corruption claim

### R5 — P2/P3: merge CLI lacks idempotent retry and canonical promotion

Location: `product_scope_cli.py:117-128`; `safety_io.py:21-38`; `criteria_delegation.py:127-129`.

`criteria-merge` validates and writes a **new** output through no-clobber publication; it does not replace the input RUN or a canonical pointer. Repeating an identical merge with the same output after success-before-receipt returns FileExistsError. Using the input RUN as output also cannot overwrite it. This is distinct from `merge_result`'s in-memory row idempotence. The agent must read the existing output and separately select/promote the correct RUN. A crash between output creation and operator checkpoint/pointer update can leave the old RUN selected. The source does not implement the second promotion write, so do not claim an internal two-file atomic commit is corrupted. Proven: same-output retry fails. Inferred operational risk: stale canonical selection after interrupted promotion.

## Other source risks (not separately reproduced)

- `criteria_delegation.py:390-425`: assessment-wide lock is held while invoking arbitrary admitted callback. A hung callback blocks status/resume and other isolated tasks until the process is interrupted; there is no coordinator timeout. An executor may provide its own timeout, so this is a callback contract/availability risk, not proof an installed executor hangs.
- `journal.py:75-77, 88-93`: legacy Ownership acquire fsyncs file but not parent directory; quarantine replaces and release unlinks without parent fsync. Power-loss durability is not established. Coordinator release also unlinks without directory fsync (`criteria_delegation.py:468`), making old lease reappearance another potential orphan source after host crash. No filesystem/power-loss experiment performed.
- No evidence that these defects bypass consumed-action replay checks. Retained unknown-effect checks are conservative; problems are stalled recovery and shared-state consistency.

## Verification and evidence

Reproduction: `docs/reviews/zap-operations-audit-20261103/recovery-repro.py`. It operates only in fresh TemporaryDirectory fixtures and cleans them afterward. Run from repository root:

```sh
zap-product-assessment/.venv/bin/python docs/reviews/zap-operations-audit-20261103/recovery-repro.py
PYTHONPATH='.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment/src:.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment/tests' zap-product-assessment/.venv/bin/python -m unittest test_criteria_resume -q
```

Locked project interpreter run: R1–R4 produced the errors stated above; R5 first merge returned 0 and second identical merge returned FileExistsError. Existing `test_criteria_resume`: **4 passed**, 0.003 s. Those passing tests cover retained ACK hints, manually supplied unknown effects, limitation routing and approvals; they do not exercise acquisition/release crash transactions or torn coordinator logs. Initial system-python CLI probe could not import jsonschema; rerun with the existing project environment succeeded. No dependency installation was needed.

Suggested next action: implement explicit idempotent lease transaction recovery before changing fail-closed validation; test acquire-before-journal, journal-write-ack loss, partial release and torn-tail recovery with independent ready cases. Preserve non-replay guarantees and require retained evidence for effect reconciliation.
