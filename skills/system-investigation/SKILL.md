---
name: system-investigation
description: Explain how an existing subsystem works or why it has its present shape using scoped source evidence.
---

# System investigation

## Prerequisites

Named question, immutable input revision, authorized source paths and any relevant history.

Read the shared [authority and evidence rules](../../docs/skill-contract.md) before applying this procedure. They define the pack’s output and permission boundary. Load only a relevant [domain procedure](../../domains/README.md) if domain-specific verification is needed.

## Procedure

Anchor the question in concrete entry points and symbols. Trace one representative input across call boundaries, state owners and outputs; include errors and concurrency only where relevant. A list of filenames is not an execution path.

For rationale questions, consult available local history, tests and recorded decisions. Separate what code demonstrably does, documented intent and inferred explanations. Name a plausible alternative explanation when evidence cannot discriminate. Absence of history is a gap, not proof of intent.

Cite revision and file/line locations for claims. Test a load-bearing assertion with a small permitted probe when useful; otherwise mark it unverified. Search only sources relevant to the authorized question. Do not enumerate private connectors, chat or other repositories merely because they are available.

## Required output

Produce a version 1 `system-investigation` handoff using [the schema](../../contracts/handoff.schema.json) and [format guide](../../contracts/README.md). Payload fields: `question`, `paths`, `findings`, `hypotheses`, `gaps`. Record evidence, limitations and next actions in the envelope. Use empty lists only when nothing applies; use an explicit explanation for unavailable observations.

## Stop conditions

Stop when the question is answered with traceable evidence, the scope limit is reached, or required access is unavailable. Return gaps and the cheapest next observation; do not invent history.

## Attribution and adaptations

- [pstack / skills/how/SKILL.md](https://github.com/backnotprop/pstack/blob/157aae39a733135e93d8b5b19ff62c6a84b0ad56/skills/how/SKILL.md): Trace execution paths; replace host delegates with scoped evidence collection.
- [pstack / skills/why/SKILL.md](https://github.com/backnotprop/pstack/blob/157aae39a733135e93d8b5b19ff62c6a84b0ad56/skills/why/SKILL.md): Separate history evidence from hypotheses; remove mandatory broad MCP searches.

See [retained notices](../../THIRD_PARTY_NOTICES.md). No upstream executable or linked plugin is required.
