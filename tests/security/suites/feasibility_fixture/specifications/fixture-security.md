# Synthetic CSP and authorization specification

## Objectives

`DEMO-CSP` maps to CWE-693. The public and protected fixture subjects emit the CSP header. The corresponding detector controls deliberately omit it. `DEMO-AUTHZ` maps to CWE-862. Guest and reader are denied the update, and the editor can advance the fixture revision.

## Design

Run against the disposable feasibility fixture with fresh sessions and state. The anonymous and form-authenticated Requestors fetch exact GET routes. The application supplies status and effective identity for protected responses. The passive queue drains before the scoped JSON report is read. Separately, direct application calls use independent cookie jars and read revision state after each update attempt.

## Cases and evidence

The [case registry](../cases/cases.json) defines each expected predicate and evidence key. The case IDs resolve to [objectives and CWE identifiers](../objectives/objectives.json). Missing traffic, an absent detector control, invalid identity evidence, or an invalid report precludes passing the affected scanner case. The authorization and state oracles use application responses and do not require ZAP.

The public and private CSP controls remove the subject header. The authorization control denies the editor without advancing state. Authentication, preflight, warning, incomplete request and report controls exercise fail-closed verdicts. The active and JWT entries are status controls with no dispatch.
