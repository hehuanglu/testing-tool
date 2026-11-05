# authorization-ownership — Functional, object, and tenant authorization

## Intent, applicability, and discovery

Discover actor/action/object/tenant/shared grants, handlers/jobs, persistence wrappers, relations, lists/bulk/exports, and lifecycle independently of naming regexes. Account/organization/workspace/member are examples, not an allowlist. Inspect principal provenance and authoritative fields; functional authorization is not automatically BOLA.

## AUTHZ-01 — May this actor perform the function/action?

Discover privileged/business entry points, including jobs/library callers with different trust. Derive actor/action requirements from supplied role/permission specs/ACLs or labeled source assumptions. Inspect global/local guard/middleware/policy/service registration and exception paths; ownership rules do not establish function coverage. Consider inherited/global/service controls, trusted callers, and delegation. Missing local decorators/client menus do not establish absent authorization. Record registration/check/action/principal locations and policy source; inspect missing callers/configuration while isolating actual policy dependencies. No unobserved runtime allow/deny claim.

## AUTHZ-02 — Are detail/read/update/delete operations bound to the correct object/owner/tenant/grant?

Discover IDs/keys through lookup/use/mutation, actual persistence APIs/wrappers, and principals. Derive ownership/shared/admin permissions from models/policy; owner fields need not be userId. Review TypeORM-shaped candidates plus raw/custom repositories and prior checks through before-use authorization. ID-only lookup is a candidate; extra status/type predicates do not establish ownership or correct principal binding. Record identity/object/check/criteria/use and actual control paths. Inspect unknown wrappers/names rather than dropping unmatched paths; a small lookup snippet cannot establish system-wide absence.

## AUTHZ-03 — Do collections, searches, pagination, bulk operations, and exports preserve scope?

Inventory collections/counts/aggregates/bulk IDs/exports separately when their control paths differ from details. Derive per-collection/per-element tenant/grant expectations from policy, including disclosure through counts/filters. Inspect query builders, predicates before execution, per-element actions, serializers/exports, and scoped repositories/provided RLS. Admin cross-tenant permissions and overwritten filters matter; detail checks do not cover lists. Record principal/policy/construction/use locations; inspect missing builders/wrappers/RLS configuration. Static review does not establish populated datasets or runtime isolation.

## AUTHZ-04 — Are parent-child references and relation changes authorized consistently?

Discover nested IDs, foreign keys, relation assignment/reparenting/batch linking, primary and referenced objects. Derive membership/tenant/grant requirements from relation/business policy; primary-object permission does not automatically authorize references. Inspect relation APIs/joins and checks before linking/writing. Constraints may establish existence/consistency without actor authority; review service controls/shared grants/intentional cross-tenant links. Record both object paths/checks/writes/principals. Review schema and linked-resource checks; missing runtime schema/deployment limits constraint claims.

## AUTHZ-05 — Do state transitions change permissions or action preconditions?

Discover approve/publish/archive/transfer/lock and state-dependent reads/writes. Derive actor/before-after requirements from business state machines or labeled assumptions. Inspect transition methods/predicates/events, check-to-write order, transactions, and alternate callers; bundled rules are not generic lifecycle coverage. Domain aggregates may enforce invariants; state checks do not replace role/tenant binding. Record state/control/write locations and assumptions. Inspect remaining aggregates/handlers or retain source/policy gaps without claiming runtime concurrency tests.

## AUTHZ-06 — Can client-controlled protected fields override authority?

Discover owner/tenant/role/state/grant writes through assignments/spreads/merge/create/update/save. Derive immutability/server authority/allowed changes from APIs/schemas/policy rather than names. Inspect provenance, runtime allowlists, overwrite order, and actual persistence with ownership/body candidates and field searches. Server-derived input, DTO filters, hooks, post-spread authoritative overrides, and unsaved create may explain matches; trace verified principal binding. Record validation/merge/write/control locations without sensitive values or TS-as-runtime-validation claims. Inspect missing hooks/callers/wrappers or useful custom naming fixtures.

## Review ledger and completion

Record `{actor_source, action, object_or_collection, related_references, state_protected_fields, check_predicate, use_write, callers, locations, question_id, status, next_step}` in `questions[].result` or manual-review observations. Values describe actually inspected facts; unknowns remain null with specific next steps.

Trace actor authority to verifiers/principals and predicates to real implementation. Split detail/update/delete controls and preserve list/count/aggregate/reference responsibilities; owner checks do not close client-writable state/protected fields. Receiver names are hints: Map/Set.delete is in-memory; service.update may write. Resolve imports/types/constructors/managers/aliases instead of repository-name allowlists or service exclusions. Map input/output/shared/aliased/inherited DTOs through Body/Query/Param callers and serializers; do not blanket-exclude ResponseDto. authorization-ownership-static.yml is mainly TS/Nest/TypeORM inventory candidates; AUTHZ-01/04/05 need manual/custom work. Unknown names such as loadForWorkspace/spaceKey still require review. Prior guards may still match; extra predicates or match counts do not establish completion.

Consult the [catalog](../rule-catalog.md) and [rules/triage](../rules-and-triage.md). Missing detectors require applicable local/custom/manual work, rather than N/A or clean results. Close assigned inventory/questions with source-appropriate claims and explicit runtime/policy limitations.
