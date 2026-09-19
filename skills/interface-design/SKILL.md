---
name: interface-design
description: Design caller contracts and state ownership before an interface, schema or tensor change locks in the wrong behavior.
---

# Interface design

## Prerequisites

Task contract, affected callers, known compatibility constraints and investigation evidence if relevant.

Read the shared [authority and evidence rules](../../docs/skill-contract.md) before applying this procedure. They define the pack’s output and permission boundary. Load only a relevant [domain procedure](../../domains/README.md) if domain-specific verification is needed.

## Procedure

Write realistic caller examples first: input, output, failures and observable state changes. Derive the smallest useful interface from those examples. Assign one owner for mutable state and name the invariants at each boundary.

Specify representation where it changes correctness: tensor shape/stride/dtype/device and tolerance; API units and optionality; database transaction and schema version. Define cancellation, partial failure, retry and idempotency semantics when callers rely on them. A type signature alone is insufficient.

Compare a concrete alternative when there is a real architectural choice, recording what each exposes to callers. Do not force a panel or two full designs for a routine change. Keep numerical assumptions and invariant comments. Record any implementation discovery that invalidates the contract and revise before accumulating workarounds.

## Required output

Produce a version 1 `interface-design` handoff using [the schema](../../contracts/handoff.schema.json) and [format guide](../../contracts/README.md). Payload fields: `callers`, `contracts`, `ownership`, `invariants`, `alternatives`, `open_questions`. Record evidence, limitations and next actions in the envelope. Use empty lists only when nothing applies; use an explicit explanation for unavailable observations.

## Stop conditions

Stop for unresolved ownership, incompatible caller promises or a consequential architecture decision outside authorization. Return a local design artifact, not placeholder production code presented as implemented.

## Attribution and adaptations

- [pstack / skills/architect/SKILL.md](https://github.com/backnotprop/pstack/blob/157aae39a733135e93d8b5b19ff62c6a84b0ad56/skills/architect/SKILL.md): Caller-first contracts and ownership; remove mandatory multi-model arena.

See [retained notices](../../THIRD_PARTY_NOTICES.md). No upstream executable or linked plugin is required.
