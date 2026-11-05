# Select assessment question bases

Select by assignment and discovery, rather than YAML filenames. Each base offers six questions to specialize, rather than six mandatory checks for every product.

- [be-input](tracks/be-input.md): BE-IN-01…06; public/protected backend inputs and shared processing.
- [fe-browser](tracks/fe-browser.md): FE-BR-01…06; browser data/code/message/navigation boundaries.
- [authentication-session](tracks/authentication-session.md): AUTH-01…06; credentials, verification, issuance/lifecycle, principal propagation, and leakage.
- [authorization-ownership](tracks/authorization-ownership.md): AUTHZ-01…06; functions, objects/tenants, collections, relations, lifecycle, and protected fields.
- [configuration-build](tracks/configuration-build.md): CFG-01…06; effective configuration, privileges, network/TLS, dependency declarations, build/CI, and credentials.

A single assigned track does not open the other four. Reading shared code to answer a question does not open another service's assessment. For narrow scope, record `selected_base_ids` and reasons for omitted bases; distinguish out-of-scope from inapplicable. Cross-track execution may be shared only under the workflow's user-requested exception, with question mappings and no duplicate root-cause counts.

Keep rule names stable. `public`/`auth` in names do not define surfaces. Consult the [catalog](rule-catalog.md) for files, stacks, and limitations. Missing rules do not establish absence of risk; Python/Java/Go and other wrappers require suitable local/custom/manual techniques under [rules and triage](rules-and-triage.md).
