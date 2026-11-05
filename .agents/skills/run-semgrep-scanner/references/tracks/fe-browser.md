# fe-browser — Frontend and browser trust boundaries

## Intent, applicability, and discovery

Discover in-scope routes/views, URL/API/storage/user data, render/template APIs, script loaders, navigation, messaging, and actual framework/wrappers. Public/protected UI is source context. This SAST track does not require runtime browsers/journeys or establish DOM execution; React rules do not cover every JS framework.

## FE-BR-01 — Are HTML/DOM/template sinks controlled for their actual context?

Discover rich text/messages/templates/direct DOM and URL/API/storage/user inputs. Derive rendering/sanitization/encoding requirements from renderer/content policy for HTML/attribute/URL contexts. Combine HTML/URL detectors with framework-directive searches and manual provenance/sanitizer implementation/configuration review. Constants, effective sanitizer versions/options, and framework text escaping may explain matches; safeHtml names or URL parsing do not establish safety. Record input/transform/sink/control paths. Sink matches alone do not establish attacker control, script execution, or runtime CSP; inspect unknown wrappers or add framework-specific fixtures.

## FE-BR-02 — Where does dynamic code/script content originate?

Discover eval/Function, script injection/loaders, expression/template engines, imports, and actual APIs. Derive trusted-code requirements from plugin/script/build contracts. Inspect loader URLs/constructors and input-to-execution paths. Fixed assets, signatures/integrity, and verified dead/test code may matter; CSP declarations do not establish runtime enforcement. Record provenance/validation/integrity/sinks and unknown configuration. Read missing loaders/callers or retain external-source gaps without claiming browser execution.

## FE-BR-03 — Are navigation destinations and opener behavior appropriately restricted?

Discover return URLs/deep links/location/router/window.open/user links. Derive scheme/origin/destination/opener policy from internal/external/SSO contracts. Use query/hash taint and opener candidates plus wrapper/router/canonicalization review. Inspect allowlists/fixed mappings/relative paths/scheme checks/noopener/noreferrer/subsequent opener clearing. Route names do not establish internal destinations. Record checks/options/policy and avoid unobserved final-URL/opener/browser-version claims; inspect missing wrappers/SSO mappings.

## FE-BR-04 — Are messaging senders, recipients, and payloads bound correctly?

Discover Window/iframe/worker senders/handlers/types/receivers. Derive origin/source-window/payload/targetOrigin requirements from integration contracts, distinguishing workers/public broadcasts. Inspect inline and named handlers/wrappers, exact-origin versus suffix/substring comparisons, source binding, early returns, schemas, and sinks. Wildcard public data is not automatically sensitive disclosure. Record send/check/sink/API locations, review both directions, and retain parent/shared-handler gaps; manual paths are not native traces.

## FE-BR-05 — Can credentials/session material appear in storage, bundles, configuration, or logs?

Discover auth persistence, client environment exports, telemetry/console, and provided bundles. Derive session/secret handling from policy/threat model; browser token storage alone is not a confirmed exploit. Inspect Web Storage/auth-name/Vite candidates, custom storage/loggers/build exports, actual material/lifecycle/redaction. Public IDs/keys/placeholders, injection/log stripping, and session purpose may explain candidates. Record sanitized types/provenance/writers/readers/consumers without secret values. Trace key → material → HTTP consumers → remember-me/login/register/logout where present; names do not establish credentials or runtime bundle exposure/validity/attacker scripts.

## FE-BR-06 — Are UI permissions being mistaken for server authorization?

Discover menus/client guards/roles and sensitive API calls. Derive server trust boundaries from API authorization contracts. Inspect UI principal/action/payload mappings; read relevant server controls only within authorized source scope. Server middleware/service checks may enforce permissions; hidden menus/buttons do not establish server allow/deny. Record UI/API and actually read server locations, with outside-scope/missing-source limits. Do not open a whole-server assessment or infer missing server authz from client code.

## Review ledger and completion

Record `{route_component, action_or_data, input_source, transform, sink_context, api_consumer, token_storage_material, token_storage_consumer, server_handler_control_read, outside_scope, question_id, manual_review_id}` in `questions[].result` or manual-review observations. Values describe actually inspected facts; unknowns remain null with specific next steps.

Link actual locations; unknown segments remain null with next steps. UI guards remain UI-layer observations, server claims require actual server-control review. HTML/navigation/message questions need their actual URL/origin/attribute/HTML context. fe-public-static.yml supports TS/React/browser/Vite, partially FE-BR-01…05; FE-BR-06 and other frameworks/wrappers require manual/custom work. A shared HTML renderer can explain a false-positive after sufficient control review; nonmatching text rendering does not certify the page.

Consult the [catalog](../rule-catalog.md) and [rules/triage](../rules-and-triage.md). Missing detectors require applicable local/custom/manual work, rather than N/A or clean results. Close assigned inventory/questions with source-appropriate claims and explicit runtime/policy limitations.
