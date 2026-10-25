> Research contract update (2026-10-21): native JSON bearer may be used in an explicitly selected `be-authenticated-research/1.0` deployment accepting local secret persistence. Default remains disabled. Historical failures below remain valid for the strict secret-safe contract. Research additionally requires protected subject JSON assertions, direct topology, continuity monitoring and bounded scoped scans. See `BE_AUTHENTICATED_RESEARCH.md`.

# JSON bearer target authentication feasibility spike

Status: experimental, default disabled, not a production capability.

This spike evaluates JSON login responses that contain a bearer token and a
protected verification endpoint. It does not change the target application's
authentication semantics and does not convert the token to a cookie.

## Approaches evaluated

### Native ZAP JSON authentication

The `json-bearer` prototype configures ZAP `jsonBasedAuthentication` and
`headerBasedSessionManagement`. The password is resolved from a credential
reference, and the Java-side prepared-session record contains only opaque ZAP
context/user identifiers. The raw token remains in ZAP's runtime state.

The fixture proves that this approach can:

- log in with JSON and extract a nested token;
- replay `Authorization: Bearer ...` for a protected request;
- validate a protected response through the configured ZAP user/context;
- route a validated session to guided HTTP crawl and accept it for direct
  active-scan startup;
- invalidate MCP session handles after process restart;
- reject durable queued execution because the queue cannot prove that the
  in-memory authorization lease survived a restart.

### MCP-managed literal header

A second experiment attempted to bind a literal token to ZAP header-based
session management after an MCP-managed login. ZAP did not associate that
literal header with the configured user session, so protected polling remained
logged out. This route is not used by the prototype.

## Retry and history-controller experiment

A fixture-only HTTP Sender script demonstrates most of the missing lifecycle:

- after a protected `401`, reset ZAP's stale local authentication clock and
  perform one native re-login;
- retry the original request once using a sender that is not user-bound, which
  prevents the native listener from starting a second login cycle;
- if the retry is still `401` or `403`, mark the session blocked and redirect
  subsequent same-origin traffic to ZAP loopback so it cannot reach the target;
- never attach the header outside the exact allowed origin;
- redact a controller-owned/manual protected request before that request is
  persisted.

The Docker integration fixture covers both a successful refresh and a rejected
refresh. The initial sender-script experiment records a security blocker:
native ZAP verification history contains the raw bearer token when the script
controller is used by itself.

## Necessary-condition gates

Additional fixture-only probes separate script limitations from ZAP extension
limitations:

1. **Java listener interception: partial pass.** A Java `HttpSenderListener`
   receives initiator 15 (`AUTHENTICATION_POLL`), can redact its `HttpMessage`,
   and the subsequent native `AuthenticationVerification` record is redacted.
   This proves that the verification leak is not intrinsically unavoidable.
2. **Native login secrecy: fail.** ZAP's native JSON authentication explicitly
   adds the login message to authentication history. The persisted request body
   contains the password and the persisted response body contains the JWT. A
   poll redactor cannot repair this because login uses a different initiator
   and the session extractor still needs the unmodified response.
3. **Extension-owned login and exact-origin injection: pass as a transport
   proof.** A controller-owned login can avoid history entirely, keep the token
   in private runtime memory, inject only for the exact allowed origin, and
   reach a protected endpoint. A cross-origin fixture request remains clean.
4. **HTTP Spider history secrecy: fail.** With extension-owned login, an
   ordinary HTTP Spider successfully reaches and discovers a protected child,
   but the Spider's persisted records still contain the raw bearer token even
   though the response callback redacts the live message. Therefore a normal
   `HttpSenderListener` is not a sufficient injection boundary for a
   secret-safe scan.
5. **One retry and fail closed: partial pass.** The fixture controller performs
   exactly one re-login, blocks later target traffic after a rejected refresh,
   and leaves a non-secret blocked marker. The repository already exposes
   stop-by-scan-ID operations, but it does not yet have a production-safe
   add-on signal and session-to-owning-scan mapping that synchronously stops the
   correct scan.
6. **Restart and durable queue: pass only by rejection.** Opaque MCP handles are
   invalid after restart and queued `json-bearer` execution is rejected. Safe
   durable execution would require the worker to prepare a fresh ephemeral
   lease; persisting a token is not acceptable.
7. **Wire-only transport boundary: manual pass, crawler path fail.**
   A fixture-only probe inserts the bearer value into the Apache request after
   ZAP has converted the history-visible `HttpMessage`, then removes it from
   the Apache request before ZAP copies transport headers back. A manual
   protected exchange succeeds while its ZAP model/history remains free of the
   password and bearer token, and exact-origin exclusion is proven. The same
   reflection/GraalJS proxy is not stable when invoked by Spider worker
   threads: repeated runs produce ZAP I/O errors before the proxy callback can
   record an error. Consequently there is no repeatable Spider or active-scan
   pass for this probe. The installed network add-on does not expose the
   outbound hook as a public API, and the transport callback also lacks an
   opaque context/user/session lease identifier for concurrent credentials on
   the same origin.

These gates show that neither native JSON authentication plus a redactor nor an
extension implemented only as an HTTP Sender listener satisfies the mandatory
history invariant. They also prove that a boundary below the history-visible
`HttpMessage` can satisfy the transport and history requirements. What remains
unproven is a supported, session-aware API for that boundary. A standalone
add-on against the current public APIs is therefore insufficient; the credible
next step is a narrow ZAP core/network-add-on change that supports ephemeral
secret request headers without copying them back to the model.

## Safety boundary

The Spring provider is loaded only when this explicit flag is set:

```yaml
zap:
  auth:
    experimental-json-bearer-enabled: true
```

The flag defaults to false. Enabling it is for an isolated fixture or continued
development only. Do not enable it for a production target, do not treat its
reports as secret-safe evidence, and do not persist or queue its session state.

No finalsource profile is installed by this spike, and no active scan is run
against finalsource.

## Decision and smallest next step

Native ZAP JSON authentication remains useful evidence that header replay,
protected crawl, and one-shot refresh are technically feasible, but it must be
discarded as the production secret lifecycle because it persists both login
credentials and token responses. Also discard an HTTP Sender script/listener as
the final injection design because Spider history still receives the raw
header.

The network-layer experiment has passed only for a manual fixture exchange and
only through reflection into version-specific private fields. It has not
produced a repeatable crawler result. Reflection is not an acceptable
production mechanism. The smallest credible next experiment is therefore a
time-boxed upstream/core or network-add-on API patch—not another MCP-side
script—that owns login, adds the authorization value below the history-visible
message boundary, and exposes a non-secret blocked-session signal. Acceptance
requires tests proving:

1. no reflection or dependency on private network implementation classes;
2. success, error, redirect, retry, and HTTP/2 paths never copy the secret into
   `HttpMessage` or any history record;
3. each outbound request carries an opaque lease identity so concurrent
   sessions, including sessions on the same origin, remain isolated;
4. exactly one login occurs after expiry, including the rejected-refresh path;
5. the owning spider or active scan is stopped immediately after failure;
6. direct execution works, while durable queue/restart behavior fails closed
   until a worker can prepare a fresh ephemeral lease.

Until those tests pass, `json-bearer` is not a trustworthy JWT-authenticated
scan primitive and should not be used as the basis for an orchestration skill.
If the supported upstream hook cannot pass the same Spider and active-scan
history tests plus concurrent-session isolation, this approach should be
removed rather than expanded further in the MCP server.
