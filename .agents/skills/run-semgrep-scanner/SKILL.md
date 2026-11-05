---
name: run-semgrep-scanner
description: >-
  Assess product source security using local Semgrep scans and source review.
  Discover the product, define test questions, select or extend rules, triage
  candidates, and reconcile scope. Run assessment tracks sequentially with
  process and evidence self-review. Supports targeted scans and retesting;
  does not replace dynamic testing.
---

# Run Semgrep Scanner

Work as a tester using Semgrep and source review. Follow the user's language preference. The user supplies the goal; discover rule IDs, commands, and framework mappings yourself.

All skill resources reside beside this SKILL.md. Copy the complete directory into another project's `.agents/skills/` or install it for personal use. Read [setup and synchronization](references/setup.md); resolve paths from the loaded skill, rather than the product working directory. The repository's `.agents/skills/run-semgrep-scanner/` is the maintained source; personal installations include its references, rules, scripts, examples, and tests.

## Context and principles

Read [tester context](references/tester-context.md) for an assessment. The user defines scope, the product defines inventory, and test questions and actual capabilities determine techniques. Keep source structure, runtime behavior, and policy correctness as separate claims. Findings are not inventory; zero matches do not establish safety, and control names do not establish enforcement.

## Five assessment tracks

- [be-input](references/tracks/be-input.md): backend input and data processing, including public and protected source within scope.
- [fe-browser](references/tracks/fe-browser.md): HTML/DOM, code, navigation, messaging, and browser trust boundaries.
- [authentication-session](references/tracks/authentication-session.md): credentials, identity, sessions, and propagation; does not automatically include every protected business handler.
- [authorization-ownership](references/tracks/authorization-ownership.md): actor/action, object, tenant, collection, relation, and state boundaries.
- [configuration-build](references/tracks/configuration-build.md): configuration, builds, and dependency declarations; does not constitute an SCA/CVE scan.

Use the [track index](references/track-intents.md) to select starting questions. Adapt relevant questions to the product and assigned scope. Public/protected describes source surfaces; it does not establish that anonymous/authenticated execution occurred.

## Default workflow

Run multiple tracks **sequentially**, following the [track workflow](references/sequential-track-workflow.md): discovery → RUN checkpoint → technique selection → execution/readback → triage → inventory/question/native-result reconciliation → process and evidence self-review → save the track's ALERTS/RUN → next track. Complete these steps yourself without waiting for another reviewer. Describe this as self-review, not independent evaluation.

Select only assigned tracks. For a whole-product assessment, prefer the order above unless dependencies require otherwise. Targeted scans and retests do not automatically open all five tracks. A track may need several rounds; one YAML file does not define the entire assessment. A track may be ready for handoff while still partial/blocked after all feasible local work is exhausted and remaining dependencies are documented. Do not add approval checkpoints between tracks.

## Dispatcher

1. **Discover:** read applicable AGENTS instructions, source/specifications/configuration, and available local rules. Verify roots, stack, and Git revision/dirty state when available. Follow the [tester workflow](references/tester-workflow.md); inventory HTTP/GraphQL/RPC, jobs/events, libraries, UI, and configuration where relevant. Products need not expose endpoints.
2. **Announce track and scope:** inform the user without requesting authorization already granted. For example: “I will assess `<track>` across `<scope>`, starting with `<base IDs>`. Discovery will refine the questions around the actual features, framework, and controls. Results will distinguish Semgrep output from manual source review.” For several tracks, state scope and order; for narrow tasks, explain the selected bases.
3. **Checkpoint questions before execution:** save known scope, inventory, and questions in the working RUN, including expectations and their sources, planned techniques, and closure conditions. Leave unknown facts null. Follow [checkpointing and question instances](references/tester-workflow.md); base labels do not replace discovery. This is local bookkeeping, not an approval gate or another handoff file. Continue independent discovery and checks while inventory is incomplete.
4. **Map techniques:** consult the [catalog](references/rule-catalog.md) and [rules/triage](references/rules-and-triage.md): inspect repository/local rules and applicability, add a focused custom rule with fixtures when useful, and perform feasible manual review. Bundled rules support limited stacks; a missing rule does not make a question inapplicable.
5. **Execute:** use the [local CLI](references/semgrep-operations.md), selecting targets/rules for the current track's questions. Keep each round's output private outside the product. Read actual CLI help before choosing flags. Combine execution across tracks only at the user's request; retain separate question/output mappings and do not imply blanket coverage.
6. **Read back and triage:** inspect native results, errors, skips, timeouts, source, callers, and controls. Record newly discovered questions/techniques and why they arose without backdating the plan. Keep candidate dispositions in RUN; inventory candidates do not automatically become security alerts. Distinguish Semgrep from manual provenance and retain native severity/confidence.
7. **Reconcile and continue:** compare every inventory item/question against actual work using the [responsibility loop](references/responsibility-loop.md). Execute feasible next steps instead of stopping after documenting a limitation.
8. **Self-review and hand off the track:** follow the [track workflow](references/sequential-track-workflow.md) and [completion contract](references/reporting-and-completion.md). Assess process sufficiency for the scope/claims separately from evidence support for observations/triage. Save the two files and the review in RUN before moving on. Separate round status from assignment status. A supported issue does not prevent completion; exit 0 does not establish it.

## Outputs

For new assessments, deliver exactly **ALERTS.json and RUN.json per track**, using the v2 [reporting contract](references/reporting-and-completion.md), in a stable local directory outside the product. Embed [SAST evidence](references/evidence.md) in ALERTS; record operation/source provenance and self-review under `tracks[].review` in RUN. Keep raw output, logs, and temporary rules private. Do not require an extra EVALUATION file, canvas, evidence directory, archive, or hash manifest. Produce a separate evaluation only when requested. [Synthetic examples](examples/README.md) are not actual scan results. Preserve historical reports and never invent missing evidence.

## Task routing

- **New assessment:** context → sequential workflow → assigned question bases → catalog/CLI → responsibility loop → per-track self-review and reporting.
- **Targeted scan/candidates:** select relevant bases and the requested triage depth; detector search completion does not establish a system-wide audit.
- **Custom rule:** inspect implementation and keep product mappings outside the core skill; follow [rules/triage](references/rules-and-triage.md) and [fixtures](tests/README.md). A single question need not produce a multilingual library.
- **Retest:** inspect source changes and prior results. Check ignore/rule/path/engine changes before claiming a fix. Preserve history.
- **CLI/output failure:** [operations](references/semgrep-operations.md) → [responsibility loop](references/responsibility-loop.md); continue independent work.
- **Audit/setup-only/skill maintenance:** perform only the assigned work and use [validation](references/validation.md). Do not run a product assessment or fabricate ALERTS/RUN.

## Authorization, privacy, and stopping

An assessment of an identified product authorizes necessary local scans, source review, and triage within scope without per-round approval. A path alone or a setup question does not assign an assessment. Use OSS/CE, inspected local rules, isolated settings, and disabled metrics/version checks. Network isolation is a separate capability that must be verified. Do not independently log in/upload, use Registry/auto/Pro/SCA/Secrets, autofix, fetch dependencies, modify the product or machine-wide configuration, or send traffic to prove static findings. Resolve relative links from the skill directory.

Stop when the assigned scope and triage are addressed, the user requests a stop, or a diagnosed blocker leaves no valid step after authorized remediation. Do not retry unchanged conditions or open an assurance campaign. Ask only for missing information that materially affects scope, authorization, or conclusions and cannot be found locally; continue independent work.

Use **Operations** and **Limitations** in the final response: actual work/results/completion, links to both files for assessments, unfinished work, attempted remedies, and resumption conditions. For skill maintenance, report changes and validation accurately. Do not independently commit/push/publish, send messages, create chats, or spawn subagents without user instructions.
