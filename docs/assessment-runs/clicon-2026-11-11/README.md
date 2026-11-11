# Clicon assessment runs — 2026-11-11

[metrics.json](metrics.json) contains counts from the final ZAP delivery projection and the fresh Semgrep acceptance run.

- **ZAP r5e — completed.** 34 criteria met, 6 unmet, 4 not applicable, 6 excluded. The scanner recorded 4 distinct alert identities across 14 occurrences. Two identities mapped to criteria. The review recorded 5 observed-only findings. The published sheet was verified.
- **Semgrep OSS 1.176.0 — partial.** 35 criteria passed, 2 failed and 7 remained not evaluable. Three rounds produced 63 native matches. Manual review supported 3 distinct issues and promoted zero Semgrep matches to findings. Counts of files scanned are per round and may overlap.

The two runs use separate evidence and verdicts. This snapshot contains aggregate counts and round metadata. The original operational records and workbooks are retained locally.
