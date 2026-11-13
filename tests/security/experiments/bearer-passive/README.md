# B2 static bearer experiment

This isolated experiment injects a token from the runtime environment into one AF requestor
GET. The artifact stores only boolean actor/marker witnesses and scans itself for both secret
canaries. It does not qualify login, refresh, SSO or cookie authentication.

```sh
bash tests/security/experiments/bearer-passive/run.sh --mode good --out /tmp/bearer-good
bash tests/security/experiments/bearer-passive/run.sh --mode bad --out /tmp/bearer-bad
```

Good must produce `PASS/STATIC_BEARER_ACTOR_AND_MARKER_WITNESSED`; bad must produce
`MISSING_EVIDENCE/AUTH_LOST`. The profile remains experimental until a clean GitHub run is
recorded.
