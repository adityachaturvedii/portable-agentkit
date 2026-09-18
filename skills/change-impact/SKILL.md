---
name: change-impact
description: Identify downstream consumers and invariants at risk from a proposed change and choose concrete verification targets.
---

# Change impact

## Prerequisites

Base and candidate revisions or a precisely scoped proposed diff; affected public contracts.

Read the shared [authority and evidence rules](../../docs/skill-contract.md) before applying this procedure. They define the pack’s output and permission boundary. Load only a relevant [domain procedure](../../domains/README.md) if domain-specific verification is needed.

## Procedure

Trace changed behavior beyond direct symbol references: serialized values, database readers, background jobs, caches, cleanup timing, feature flags and consumers in other languages. Do not invent callers when search is empty.

Name the load-bearing safety claim for each material risk. Explain the failure path, consequence, and evidence that supports or challenges it. Prefer a small experiment through the real public boundary to confident prose. Classify risks as confirmed, cleared with evidence, or unresolved.

Produce specific verification targets with expected behavior and affected consumers. A missing capability leaves the relevant risk unresolved; it does not clear it. Keep the report proportional to the consequences of the change.

## Required output

Produce a version 1 `change-impact` handoff using [the schema](../../contracts/handoff.schema.json) and [format guide](../../contracts/README.md). Payload fields: `change`, `consumers`, `invariants`, `risks`, `verification_targets`. Record evidence, limitations and next actions in the envelope. Use empty lists only when nothing applies; use an explicit explanation for unavailable observations.

## Stop conditions

Stop at the declared investigation budget or unavailable consumer/environment. Hand unresolved risk to the owner; never waive a gate or silently broaden scope.

## Attribution and adaptations

- [pstack / skills/blast-radius/SKILL.md](https://github.com/backnotprop/pstack/blob/157aae39a733135e93d8b5b19ff62c6a84b0ad56/skills/blast-radius/SKILL.md): Check consumers beyond symbols; record unproven invariants, remove automatic arena and unslop dependency.

See [retained notices](../../THIRD_PARTY_NOTICES.md). No upstream executable or linked plugin is required.
