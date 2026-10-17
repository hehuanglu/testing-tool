# UC12 local runtime

Use Docker Compose with project `uc12-run-002` and `finalsource/.env`.
The only published socket is `127.0.0.1:8123`, serving HTTPS. The database and
backend stay inside this project's network. Other Compose projects and volumes
are independent and must not be reset or removed.

The researcher-authorized local initialization generates independent random
database/JWT secrets in the ignored `.env`, and a local CA and localhost
certificate under ignored `.runtime.local/tls`. Trust this run's `ca.crt` for
local inspection. Do not disable certificate verification for general browsing.
No keys or credentials belong in source or evidence. The private Docker network
is the internal transport boundary between the TLS proxy and the API.

This host uses Avast HTTPS inspection. Export its already trusted public CA to
`.runtime.local/npm-ca.pem` (or set `NPM_CA_FILE`) for the optional BuildKit
`npm_ca` secret. npm retains TLS verification and lockfile integrity checking;
the CA is mounted during dependency installation and is not stored in an image.

Build with `docker compose -p uc12-run-002 --env-file finalsource/.env -f finalsource/compose.yaml up --build -d`.
MySQL runs the approved non-destructive create-bills migration on startup.
There is no native host application runtime and no scanner service.

Package manifests and lockfiles remain editable to support reviewed component
updates; rebuild the images after an approved lockfile/image version change.
Backend and frontend run without root, with read-only filesystems, dropped
capabilities and no-new-privileges. Temporary runtime files use bounded tmpfs.

The new guard uses the existing Nest JWT verifier because the clean baseline
has no pre-existing JWT guard. It checks signature, algorithm, issuer, audience,
expiry, numeric subject and current user existence. All bill reads additionally
bind owner identity in the database predicate.
