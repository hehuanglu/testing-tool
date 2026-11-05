# be-input — Backend inputs and data processing

## Intent, applicability, and discovery

Discover public/protected HTTP/GraphQL/RPC, jobs/events/files/library inputs, handlers, schemas, services, repository wrappers, sinks, responses, and logs independently of matches. Reading principals to understand a flow does not open a separate authentication/authorization assessment.

## BE-IN-01 — Can input affect SQL/query construction unsafely?

Discover raw SQL, ORM builders, sorting/filtering/dynamic identifiers, and wrappers. Expect bound values separated from SQL text and appropriate identifier mappings/allowlists under the query/schema/policy contract. Trace handler/job → service → wrapper → query using bundled local TS detectors plus searches/manual caller/binding review. Inspect constants, placeholders, actual allowlists, ORM escaping, and sort directions: a parameters array alone does not establish safe SQL text. Record input/construction/sink/binding/control locations and manual provenance. Close only after relevant query paths and controls are understood; find missing wrappers or retain specific source gaps. No static database/exploit claim.

## BE-IN-02 — How does input reach process, shell, code, or template execution?

Discover process launches, eval/Function, template engines, and interpreters. Derive code/command/template trust from feature/job contracts and policy. Inspect imports, APIs, command/argv/options, callers, and engines. Distinguish argv from shell strings, shell:true, interpreter arguments, quoting, fixed mappings, trusted templates, and sandbox semantics. Record actual execution options, input transformations, and controls. Explain what executes and how input affects it; inspect missing wrappers/options or add useful local fixtures. Process usage alone is not injection; do not execute product processes/payloads to prove it.

## BE-IN-03 — Do filesystem, upload, and archive operations preserve boundaries?

Discover upload/download/extract/archive and request/job-controlled read/write/rename/copy/link paths. Expect authorized base directories/resources, entry names, and symlink behavior under storage policy. Trace normalization → containment → actual operations and callers, using filesystem candidates plus library review. join/normalize does not establish containment; inspect canonicalization, separators/prefixes, symlinks/TOCTOU, generated names, and both source/destination for copies/renames. Record input/base/check/sink and read/write direction without inventing runtime permissions. Read missing extraction/storage wrappers; zero matches do not close file inventory.

## BE-IN-04 — How does input control outbound destinations?

Discover callbacks/webhooks/import/proxy/fetch, HTTP clients, URL/options/baseURL, and redirects. Derive destination/protocol/redirect requirements from integrations/allowlists/provided egress policy. Inspect client factories, URL construction/parsing, redirect settings, and callers with local taint/search/manual review. Fixed destinations, post-parse scheme/host allowlists, and redirect controls matter; parsing alone does not prevent SSRF. Record input/destination/check/config locations. Limit conclusions to inspected source, without unobserved DNS/reachability claims; missing runtime egress configuration does not block independent review.

## BE-IN-05 — Can binding/deserialization/mass assignment modify protected fields?

Discover DTO/entity binding, deserialization, spread/assign/merge/create/save, editable fields, and server-managed owner/tenant/role/state. Derive field allowlists/validation/authority from APIs/schemas/policy. Review actual validation invocation and merge order through persistence, using body/ValidationPipe candidates and binder searches. TS types are not runtime filters; declarations do not establish active pipes; create/merge may not write. Inspect hooks/wrappers/overwrites/caller trust. Record binding/validator/writer/control locations without sensitive payloads or blanket writability claims. Explain actual fields reaching writes; retain labeled assumptions/policy dependencies while completing feasible paths.

## BE-IN-06 — Can sensitive data reach unintended responses, logs, or errors?

Discover feature-specific personal/credential/asset data, serializers, error envelopes, and loggers. Derive disclosure/redaction requirements from API/classification/logging policy, labeling source assumptions. Combine naming/logger/error/HTTP candidates with actual model/serializer/caller/config review. Token names may be public IDs; inspect hashing, real redaction implementations, disabled levels, serializer exclusions, and internal returns. Record locations/data types/sinks/controls without values. Explain representation/exposure on selected paths, retain specific gaps, and avoid unobserved log-access/response/runtime-data claims.

## Review ledger and completion

Record `{entrypoint_input, trust_source, transform_validator, sink, control, response_or_write, callers, locations, limitations}` in `questions[].result` or manual-review observations. Values describe actually inspected facts; unknowns remain null with specific next steps.

Public/protected comes from source routing/guards, rather than runtime sessions. Supporting libraries are not automatically entry points. Split create/update when controls or overwrite order differ; map shared callers without multiplying root causes. Filesystem N/A requires discovery facts. The 21 rules in be-public-static.yml are TS/Nest/Node/TypeORM and bundled-partial; templates/archive/deserialization may require local/custom/manual techniques. Close inventory/questions, rather than a rule count.

Consult the [catalog](../rule-catalog.md) and [rules/triage](../rules-and-triage.md). Missing detectors require applicable local/custom/manual work, rather than N/A or clean results. Close assigned inventory/questions with source-appropriate claims and explicit runtime/policy limitations.
