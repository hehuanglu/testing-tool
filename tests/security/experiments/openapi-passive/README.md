# B1 OpenAPI passive experiment

The fixture exposes `/health` and `/items`; the OpenAPI document declares exactly one route.
The good control must prove an actual `/items` request and a new JSON report. The negative
document declares `/missing` and must not receive coverage credit.

```sh
bash tests/security/experiments/openapi-passive/run.sh --mode good --out /tmp/openapi-good
bash tests/security/experiments/openapi-passive/run.sh --mode missing-route --out /tmp/openapi-missing
```

This qualifies OpenAPI import plus passive API transport only. It does not claim SOAP,
GraphQL, authorization, business assertions, or active scan support. The profile stays
experimental until a clean GitHub run is recorded.
