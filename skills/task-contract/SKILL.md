---
name: task-contract
description: Turn an authorized engineering request into a scoped technical contract with observable acceptance checks.
---

# Task contract

## Prerequisites

User objective, available context and base revision; use unknown explicitly for missing facts.

Read the shared [authority and evidence rules](../../docs/skill-contract.md) before applying this procedure. They define the pack’s output and permission boundary. Load only a relevant [domain procedure](../../domains/README.md) if domain-specific verification is needed.

## Procedure

Read the request and available project facts before asking questions. Record objective, scope, non-goals, public interfaces, dependencies, acceptance criteria, risk and resource bounds. Map each acceptance check to an observable result and an independent source of expected values. Preserve the user’s requested behavior; do not redefine acceptance to fit an implementation.

Reuse established test seams and decisions. Ask only when a missing answer materially changes scope, correctness, access or cost. For a routine reversible choice, state an assumption and proceed. A new implementation task needs an assigned branch and dedicated worktree before edits; record this as a prerequisite if the host has not provided one. A worktree is not a sandbox.

Describe budget units separately: model calls, wall time, compute and money where known. Unknown usage is unknown. A proposed allocation grants no authority. Keep an acceptance check ID stable so later evidence can reference it.

## Required output

Produce a version 1 `task-contract` handoff using [the schema](../../contracts/handoff.schema.json) and [format guide](../../contracts/README.md). Payload fields: `objective`, `scope`, `non_goals`, `acceptance`, `interfaces`, `risk`, `budget`, `dependencies`, `unknowns`. Record evidence, limitations and next actions in the envelope. Use empty lists only when nothing applies; use an explicit explanation for unavailable observations.

## Stop conditions

No implementation until material ambiguities affecting that implementation are resolved. Independent scoped work may continue. Stop at the declared planning budget; never publish the contract to a tracker.

## Attribution and adaptations

- [matt-skills / skills/engineering/grill-with-docs/SKILL.md](https://github.com/mattpocock/skills/blob/74ca5fe077456a0b3b2f5310cf9430999fd0b5fd/skills/engineering/grill-with-docs/SKILL.md): Synthesize known context; replace mandatory grill/domain-modeling calls and exhaustive interview with material questions.
- [matt-skills / skills/engineering/to-spec/SKILL.md](https://github.com/mattpocock/skills/blob/74ca5fe077456a0b3b2f5310cf9430999fd0b5fd/skills/engineering/to-spec/SKILL.md): Technical acceptance contract; remove tracker publication, setup dependency and extensive mandatory stories.

See [retained notices](../../THIRD_PARTY_NOTICES.md). No upstream executable or linked plugin is required.
