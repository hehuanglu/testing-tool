# Generated-source baseline

This directory contains the pre-existing platform baseline shared by every experimental run. It is not first-pass feature output and must not be counted as code generated for a use case.

## Frontend baseline

- React/Vite/TypeScript/Tailwind bootstrap and strict compiler/lint configuration.
- Root router, application shell, placeholder home and not-found pages.
- Typed Axios client and common API response types.
- Empty extension directories for feature components, context, hooks, assets and utilities.

## Backend baseline

- NestJS bootstrap, `/api` prefix, DTO validation and constrained CORS.
- Secure headers, normalized success/error responses and development-only Swagger.
- Validated environment/configuration and TypeORM/MySQL wiring with `synchronize: false`.
- A minimal health endpoint and empty `modules/` extension directory.

## Extension contract

For each approved UC, AI must extend this baseline rather than recreate it:

- FE: add feature pages/components/API services and register routes with the existing router/shell.
- BE: add feature modules/controllers/services/entities/DTOs and import modules into `AppModule`.
- Reuse the existing HTTP client, configuration, validation, filters and interceptors.
- Do not replace package/config/bootstrap files unless an approved requirement makes a minimal change necessary.
- Do not add dependencies when existing platform capabilities suffice.
- Preserve unrelated feature code and all prior user changes.

Every model comparison must start from the same clean baseline revision. Record that revision/input-bundle hash in the audit. Only the UC-specific diff after the generation start timestamp is first-pass generated code.

## Docker runtime baseline

`compose.yaml` runs MySQL 8.4, the compiled NestJS application with `NODE_ENV=development`, and the compiled React application served by unprivileged Nginx. The research runtime intentionally rejects `NODE_ENV=production` so Swagger/OpenAPI remains available to the independent final-source evaluator. Frontend and backend publish configurable loopback ports for researcher inspection; MySQL remains internal. This runtime is not a production deployment target. Nginx proxies `/api` to the backend so the browser uses one public origin. AI may extend Docker configuration only when an approved feature requires infrastructure changes; it must not expose MySQL, embed secrets, enable TypeORM synchronization or replace the containers for ordinary UC implementation.
