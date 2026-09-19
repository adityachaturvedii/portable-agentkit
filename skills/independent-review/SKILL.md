---
name: independent-review
description: Review an immutable candidate against intent and public contracts, producing evidence-backed findings without editing it.
---

# Independent review

## Prerequisites

Base/candidate revisions, stated intent, diff/context and reviewer distinct from implementation authors.

Read the shared [authority and evidence rules](../../docs/skill-contract.md) before applying this procedure. They define the pack’s output and permission boundary. Load only a relevant [domain procedure](../../domains/README.md) if domain-specific verification is needed.

## Procedure

Verify scope and missing requirements before reviewing failure paths. Inspect relevant correctness boundaries: transactions and migrations, concurrent shared state, retries/idempotency, shell/SQL injection, LLM output trust, tenant authorization, enum/value coverage and numerical assumptions.

For each actionable finding, identify location, severity, reachable trigger, consequence and a reproduction or precise reasoning chain. Distinguish confirmed defects from uncertainties. Deduplicate findings by cause, not vote count; disagreement should yield a falsifiable question or targeted experiment.

Review without fixing the candidate. Bind findings and coverage to its exact revision. Record dispositions with rationale, and explicitly list unavailable checks. If the reviewer is the implementer, label the result a self-check; an independent reviewer is still required. Never manufacture independence through a different display name.

## Required output

Produce a version 1 `independent-review` handoff using [the schema](../../contracts/handoff.schema.json) and [format guide](../../contracts/README.md). Payload fields: `reviewer`, `implementation_authors`, `findings`, `coverage`, `verdict`. Record evidence, limitations and next actions in the envelope. Use empty lists only when nothing applies; use an explicit explanation for unavailable observations.

## Stop conditions

Stop on candidate mutation, missing scope/revision, lack of reviewer independence or exhausted review budget. Return findings or a blocked result. Review cannot authorize publication, accept its own implementation, or waive verification.

## Attribution and adaptations

- [pstack / skills/interrogate/SKILL.md](https://github.com/backnotprop/pstack/blob/157aae39a733135e93d8b5b19ff62c6a84b0ad56/skills/interrogate/SKILL.md): Concrete findings on fixed revision; replace voting/model defaults and model-fix PRs with falsifiable checks.
- [gstack / review/SKILL.md](https://github.com/garrytan/gstack/blob/a6b3a57512ca6d5c6aa5b68f74f736195021f96e/review/SKILL.md): Reuse selected review categories; remove setup, telemetry, global learning, fixer and external-review orchestration.

See [retained notices](../../THIRD_PARTY_NOTICES.md). No upstream executable or linked plugin is required.
