# authentication-session — Identity, credentials, and sessions

## Intent, applicability, and discovery

Discover in-scope login/passwordless/SSO, credential stores, issuance/verification, guards/middleware, reset/refresh/revoke/logout, serializers, and logs. Do not scan every protected business handler by default. Source review needs no real token; absent features may justify N/A, absent rules do not.

## AUTH-01 — Are credentials acquired, transformed, stored, and verified appropriately?

Discover registration/login/change or passwordless alternatives, handlers, hash/compare/imports, and persistence hooks. Derive representation/salt/cost/algorithm requirements from actual policy and implementation. Passwordless flows need nonce/key/assertion review rather than imposed password rules. Trace input → transformation → storage/verification and wrappers/callers with persistence/comparison/taint/threshold candidates. Confirmation differs from authentication; fields may already be hashed. Bcrypt <10 and MinLength 0..7 are heuristics, not universal policy. Record representation/control/policy locations without values, and limit claims about runtime costs/migrations/store contents. Missing policy leaves only dependent conclusions open while transformation review continues.

## AUTH-02 — Is identity verified before it is trusted?

Discover JWT/SSO/assertion/API-token decode/verify/strategy and principal use. Derive signature/issuer/audience/algorithm/purpose requirements from issuer/consumer contracts; decode only parses. Inspect actual imports/verifiers/configuration and token → verification → claims → principal paths. Upstream guards may verify the same token before decode; names such as verified/user/jwtService prove nothing. Read key resolution/defaults/bypass/errors. Record source/config/principal/control bindings without runtime token-validity or system-wide-absence claims; locate missing providers/guards/callers.

## AUTH-03 — Do issuance and cookies follow their contracts?

Discover sign/signAsync/session creation/Set-Cookie/defaults/environment overrides/subject assignment. Derive subject/lifetime/purpose/Secure/HttpOnly/SameSite expectations from session/cross-site/HTTPS policy. Trace principal → claims → issue and effective source precedence/consumers with secret/subject/cookie candidates. Literals may be demos/non-JWT/unreachable; body IDs may already be bound; preference cookies differ from sessions. Missing options differ from explicit false. Record filtered options/controls and unknown runtime/proxy overrides without testing secret validity.

## AUTH-04 — Do reset, refresh, revocation, logout, and expiry protect lifecycle state?

Review only actual assigned features: reset links/codes, refresh rotation, stores/logout/expiry. Derive one-use/binding/invalidation/rotation/expiry requirements from feature policy, without universal flow assumptions. Inspect handlers/stores/transactions/TTL/clocks/client consumers and state transitions; expiration detectors cover only a fraction. Stateless logout differs from revocation; providers/store layers may enforce controls. Read reuse/error/transaction order, record state/check/write and assumptions, and retain limits on concurrency/time/provider runtime. Inspect missing source/configuration without sending traffic.

## AUTH-05 — Can guards/middleware bypass checks or lose principal binding?

Discover protected surfaces/global-local guards/decorators/exemptions/order/principal propagation. Derive exemptions and principal provenance from actual routing/auth contracts. Inspect bootstrap/module registrations through handler/service/caller and verification of the same token. Global/inherited/service/provider controls may explain local absence; public/user names are insufficient. Record registration/order/exemptions/principal use. Missing source layers do not establish runtime bypass; inspect missing registration/callers and retain unresolved paths.

## AUTH-06 — Can credential/session material leak through responses, logs, or configuration?

Discover credential fields/transports/query/body/entity returns/logging/declarations. Derive disclosure/transport/redaction expectations from data/session/consumer policy; not every token is secret. Inspect actual values by type/provenance, serializers/callers/redaction/precedence with logging/HTTP/entity/query/config candidates. Internal returns/hashes/public values/effective serialization/placeholders/disabled sinks may explain matches; inspect implementations before false-positive. Record filtered material types/locations without secrets/raw headers; do not claim runtime exposure or credential validity.

## Review ledger and completion

Record `{feature, input_provenance, implementation_locations, config_consumer, control, output_consumer, question_id, limitations}` in `questions[].result` or manual-review observations. Values describe actually inspected facts; unknowns remain null with specific next steps.

Map actual acquisition/enrollment → transform/store → compare/verify → issue → principal → expiry/logout/revoke segments, recording absent-feature discovery facts. Separate enrollment/change/reset policy, login input, and bcrypt configuration. Login MinLength does not establish weak enrollment; map shared DTO callers/effective validators instead of exempting LoginDto by name. Client cleanup does not establish server revocation. Inspect guard implementation/registration/callers despite documentation, using tester-context discrepancy fields where needed. Classify credential-shaped returns through factory/config/helper/controller callers and serialization, rather than path exclusions. be-auth-static.yml mainly supports TS/Nest/Passport/JWT/bcrypt and some generic TS syntax; cookies are in config rules. AUTH-04/05 largely need manual/custom review. Verify same-token upstream controls before judging decode-to-principal candidates.

Consult the [catalog](../rule-catalog.md) and [rules/triage](../rules-and-triage.md). Missing detectors require applicable local/custom/manual work, rather than N/A or clean results. Close assigned inventory/questions with source-appropriate claims and explicit runtime/policy limitations.
