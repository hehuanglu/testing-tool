# C3 two-actor BOLA experiment

This disposable fixture has object `alpha` owned by actor A. Both requests traverse ZAP.
The oracle is a ZAP-derived custom response witness, not a native alert.

```sh
bash tests/security/experiments/bola-two-actor/run.sh --mode fixed --out /tmp/bola-fixed
bash tests/security/experiments/bola-two-actor/run.sh --mode vulnerable --out /tmp/bola-vulnerable
bash tests/security/experiments/bola-two-actor/run.sh --mode auth-lost --out /tmp/bola-auth-lost
```

The three expected outcomes are respectively `PASS`, `REGRESSION`, and
`MISSING_EVIDENCE/AUTH_LOST`. This qualifies only a read-only two-actor fixture protocol;
the result records the unchanged post-state and that no reset is required. Mutation, async
ownership and product-specific actor setup remain unsupported.
