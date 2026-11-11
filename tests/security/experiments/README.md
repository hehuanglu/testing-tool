# Isolated capability experiments

These directories are not discovered by the stable suite. Each experiment owns its fixture,
controls and result, and stays `experimental` or `blocked` until the capability-specific gates
are met. A green experiment does not change an assessment verdict or claim generic product
support.

- `openapi-passive`: OpenAPI import plus actual passive `/items` transport.
- `bearer-passive`: static bearer environment injection, actor marker and canary leak check.
- `active-xss`: native active rule `40012` only, with vulnerable/fixed/auth-loss controls.
- `form-cookie-csrf`: form authentication, cookie session, CSRF and refresh witness.
- `bola-two-actor`: exact read-only actor/object oracle through ZAP.
- `browser-journey`: prerequisite check; currently blocked by missing `geckodriver`.

Run them with their local `run.sh` commands or the separate
`zap-regression-experiments.yml` workflow. Do not move an experiment case into
`tests/security/cases/` or add its profile to the stable exporter without a versioned contract,
two independent healthy runs, negative and missing-evidence controls, clean artifacts, cleanup
proof and a successful GitHub qualification run.
