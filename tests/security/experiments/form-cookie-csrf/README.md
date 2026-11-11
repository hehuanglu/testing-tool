# C1 form/cookie/CSRF experiment

This AF context uses form authentication, cookie session management, a synthetic CSRF field,
an explicit user and response verification. It records login/private witnesses without
persisting credentials or cookies.

```sh
bash tests/security/experiments/form-cookie-csrf/run.sh --mode healthy --out /tmp/form-healthy
bash tests/security/experiments/form-cookie-csrf/run.sh --mode revoke --out /tmp/form-revoke
bash tests/security/experiments/form-cookie-csrf/run.sh --mode bad-csrf --out /tmp/form-bad-csrf
```

This remains experimental even when the fixture controls pass; it does not qualify arbitrary
product login forms, CSRF extraction, SSO, MFA or refresh behavior.

On the pinned image, `revoke` must show a second successful login and a final private response
for the same actor; otherwise it is missing evidence rather than a pass.
