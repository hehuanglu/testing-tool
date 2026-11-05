# Independent store/CLI verification

Scope: assessment_store.py, assessment_state_cli.py, their tests and relevant history collector, against docs/plans/zap-operations-core-implementation-plan-20261104.md. Offline only; synthetic TemporaryDirectory state; no product files, network or source fixes.

## S1 — P1: managed commit permits ACK-only history to erase a pending mutation

Exact locations in `.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment/src/zap_assessment/`:

- `assessment_store.py:225-228`: pending binding preservation checks only `pending_effects_from_run`, which excludes actionHistory-derived pending effects.
- `assessment_store.py:237-238`: actionHistory is protected only by prefix equality, so appending an ACK is accepted.
- `assessment_store.py:249`: reviewer accepts the resulting state.
- `question_evidence.py:157-160`: collector retains history when any state is unknown or latest state is intent. A latest acknowledged state therefore removes an earlier intent from pending, even without terminal evidence.
- `assessment_state_cli.py:163-165`: ordinary state-commit exposes this transition through the managed store contract.

Repro starts with a valid fixture having sufficient case evidence plus one retained mutation intent, with no coordinatorState (a supported store shape). Before commit, reviewer reports one pending effect and eligibleForCompletion=false. Append one history row for the same mutation with state=acknowledged. Keep operations, case evidence and original intent unchanged, add no terminal readback and no resolution. commit_snapshot succeeds. Reloaded reviewer reports zero pending effects and eligibleForCompletion=true.

This is a violation of the plan's explicit invariant “ACK không đồng nghĩa terminal, effect đã dừng hoặc evidence đủ” and its commitment to preserve pending history across managed transitions. It does not require editing immutable generation files or abusing the private request digest parameter.

Attribution: the collector behavior predates this store implementation; the new store's promised pending-history protection does not close that existing gap. Do not describe it as a newly introduced collector regression. If a matching coordinator journal is present, its independent pending intent can still block completion; the demonstrated case has retained RUN history and no coordinator. Such snapshots are accepted by state-init and supported by the implementation/tests.

Repair direction: acknowledgement must remain pending until a valid terminal reconciliation resolves it; validate semantic pending-action transitions as well as append-only bytes. Add both plain history and journal-envelope variants, a coordinator-free fixture, and a valid terminal-resolution control. Do not fix by treating ACK as terminal or by deleting the retained intent.

## S2 — secondary P2/P3 diagnostic gap: state-inspect reports clean despite corrupt committed ancestry

Locations: `assessment_store.py:177-189` verifies current generation only; `:424-427` returns integrity=clean; ancestry is checked later in `find_receipt` at `:308-325`.

Repro commits a second generation, corrupts the genesis RUN in the synthetic store, then calls inspect_store: integrity=clean. An ordinary next commit against the same current generation fails generation-integrity while traversing ancestry. Thus clean is only a current-snapshot result, not a whole-store/history result. Current generation remains byte-correct and no unsafe dispatch/rewind is demonstrated. Treat as a secondary diagnostic limitation rather than the acceptance blocker. Repair can validate ancestry during inspect or explicitly scope the returned integrity field and expose a separate ancestry result.

## Evidence and checks

Standalone reproduction: `docs/reviews/zap-core-verification-20261104/store-repro.py`.

Run using `zap-product-assessment/.venv/bin/python docs/reviews/zap-core-verification-20261104/store-repro.py`.

Observed:

```text
S1 CONFIRMED: ACK-only appended history cleared pending mutation; eligibleForCompletion False -> True
S1 CONTROL: no added operation, terminal readback or resolution; retained original intent unchanged
S2 state-inspect after parent corruption: clean
S2 next commit rejects same store: generation-integrity
```

Focused existing regression suite: `test_assessment_store` + `test_assessment_state_cli`: **12 passed**, 4.032 s, using the existing project interpreter and source/tests PYTHONPATH. Source review found no additional proven CAS/idempotency bypass: expected generation is checked after existing committed receipt lookup, typed merge computes its request digest from packet/result before rebasing onto current, generations use no-clobber publication, and current pointer is atomically replaced with readback. This is bounded evidence, not exhaustive filesystem or multi-process crash qualification.
