# Track scope and starting questions

Use these questions to prepare the [criteria-driven plan](criteria-driven-workflow.md), then execute only its approved cases. They add no track-wide assignment or alternative workflow. User delivery follows the [Drive table contract](single-table-drive-output.md); JSON/native artifacts below are internal working data.

Apply the [ZAP result boundary](zap-result-boundary.md): native alerts and ZAP-derived observations are distinct; external-tool/source-only findings do not enter this skill’s ALERTS output.

Read with [tester context](tester-context.md). These are planning bases, rather than mandatory feature/case checklists or authorization for other tracks. User scope defines responsibility, discovery determines applicability, and capabilities determine techniques/rounds. ZAP DAST, UI automation, and direct BOLA remain distinct.

Supplied [security criteria](criteria-driven-workflow.md) may require techniques across or outside these tracks. Discover applicability and questions first; use track inventory only where it fits. A feature-specific object-access requirement does not automatically assign whole-product DAST, FE or all roles. Policy/config/source questions remain in the criteria layer.

## BE anonymous

Assess public server behavior without a logged-in identity. Discover public routes/auth middleware, normal public search/detail/list/login/register/reset, content types, required fields, state/mutations, and necessary anonymous cookies. Record auth transitions when public responses issue tokens; do not use those tokens for anonymous requests or arbitrarily strip identity while claiming original browser behavior.

Perform actual ZAP DAST for every in-scope public method/route, using suitable import/seed/crawl, passive and applicable active techniques. Protected-denial controls are additional rather than substitutes. Prepare valid bounded fixtures for public mutations instead of omitting difficult login/register cases. Close only after inventory reconciliation with actual techniques/results or explicit unexecuted items; imports/sample requests/passive-only/zero alerts are insufficient. Missing query input does not automatically imply active N/A.

## BE authenticated

Assess protected business APIs as the correct role with an effective session. Discover actual login/token/cookie transport, available or legitimately created accounts/roles, protected probes, and meaningful role-specific baselines/objects/states. Products need no common whoami/issuer/token pointer. Retain necessary tokens privately with notification rather than renewed permission.

DAST every in-scope protected method/route with applicable query/body/path/header/content-type techniques and role differences. Prepare/validate sessions, seed, run ZAP active, and monitor auth loss. Refresh/relogin supports execution; full expiry/revoke/SSO campaigns apply only when assigned. Public coverage belongs to anonymous scope without automatically opening it; deep BOLA is separate. Login/direct requests/BOLA do not replace native authenticated DAST. 401/auth loss is not authenticated coverage; missing actors/fixtures/vectors remain open.

## FE anonymous

Use a real browser as a new unauthenticated user. Start with a clean session and discover public pages/routes/forms/search/links/uploads/transitions. Observe DOM validation, storage/cookies, and actual network through ZAP, distinguishing client/server validation. Complete a normal journey before input variation; SPA HTTP 200 does not establish working UI.

Perform actual clicks/submits/navigation/readback on assigned public journeys and related network surfaces, using passive and applicable browser/active techniques. Crawlers support discovery but do not replace UI actions. For stored/DOM/reflected input inspect correct entry/display contexts; reflection differs from execution. Stop the anonymous portion at login transitions unless authenticated scope is assigned. Reconcile both UI and relevant API/input security questions; missing applicable active work keeps scope open. Do not expand to unrelated backend APIs.

## FE authenticated

Log in through real UI with the required actors/roles, discover landing/menu/session storage, and execute populated protected journeys. Observe UI/network/post-state before and after meaningful form/click/reload/navigation actions. Direct login/API/DB setup may support fixtures/native ZAP but does not replace UI login or business mutations.

Native active requires separately verified supported authentication; browser sessions do not establish the same active-scan actor. Reconcile role-dependent views/features and relevant API/input questions independently of journey/campaign lists. Hidden menus do not establish server denial; full BOLA needs its own assignment. Applicable active work requires allocation, execution, and readback; empty campaign lists or UI/passive-only are insufficient. Ground N/A in product facts. Session loss limits coverage to valid observations; missing roles/fixtures/capabilities block dependent journeys only.

## BOLA ownership

Determine which actor may act on whose object under relevant relation/state. Separate function-level permission differences from object authorization. Inventory every endpoint/role, path/query/body IDs, parent-child links, owner/tenant/shared grants, and lifecycle. Use confirmed policy or labeled source assumptions; prepare discovered roles with owner-positive and non-owner baselines. Privileged cross-owner permission does not remove ownership.

Check meaningful owner/non-owner/cross-owner and role/anonymous differences for read/create/update/delete/business actions, collections/filter/pagination, nested references, and states. Inspect returned data and side effects rather than status alone. Obtain IDs through actual ACK/readback and compare populated collections against object scope. Do not require infinite Cartesian products. Account for the endpoints, actors and states required by the approved criteria and plan, with results or explicit pending work. An approved universal criterion requires its full bounded population; missing accounts/fixtures/policy are not N/A. ZAP-derived observations retain tester interpretation provenance and do not replace either DAST track. Matching source assumptions does not certify policy correctness.

## Shared completion rules

Keep discovered → request sent → technique executed → result read distinct. Every endpoint requires handling without every possible rule/input combination. State discovery uncertainty rather than whole-product completion. Choose track order/work-unit size from risk and dependencies, prepare locally, and inherit valid results across [session checkpoints](retention-stop-and-recovery.md#working-session-checkpoints). Continue eligible work by default; only for a stated checkpoint reason retain concrete feasible next actions with partial completion; blocked means an actual dependency. Deliver the [Drive assessment table](product-assessment-handoff.md); keep JSON projections internal.
