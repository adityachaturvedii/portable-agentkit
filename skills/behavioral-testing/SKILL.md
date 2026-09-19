---
name: behavioral-testing
description: Build behavior tests at public seams with expected results independent of the implementation, using small vertical changes.
---

# Behavioral testing

## Prerequisites

Accepted behavior, established public seam, isolated fixture and independently derived expected outcomes.

Read the shared [authority and evidence rules](../../docs/skill-contract.md) before applying this procedure. They define the pack’s output and permission boundary. Load only a relevant [domain procedure](../../domains/README.md) if domain-specific verification is needed.

## Procedure

Use the highest practical public seam that reaches the behavior. Accept an already established seam without another interview. If the public contract is genuinely ambiguous, resolve that ambiguity before asserting an invented behavior.

Choose expected results from the specification, worked examples, independent references or external invariants. Do not copy the implementation’s formula into the assertion or snapshot current buggy output as truth. Exercise real collaborators where feasible; control time, randomness and external effects at system boundaries.

For a bug or new behavior, run one meaningful failing check, make the smallest vertical implementation change, then rerun it. Confirm the failure was the target symptom rather than infrastructure or import failure. Add boundary/failure cases in response to risk. Document commands and results on their actual revisions, including the before-fix revision. Prose-only edits need no invented test.

Use the relevant domain procedure for numerical, data, database or user-flow acceptance. A passing test is scoped evidence, not a universal correctness claim.

## Required output

Produce a version 1 `behavioral-testing` handoff using [the schema](../../contracts/handoff.schema.json) and [format guide](../../contracts/README.md). Payload fields: `seams`, `expected_results`, `cases`, `red_evidence`, `green_evidence`. Record evidence, limitations and next actions in the envelope. Use empty lists only when nothing applies; use an explicit explanation for unavailable observations.

## Stop conditions

Stop if the seam or dependency cannot exercise the target behavior, required verification is unavailable, or repair budget is exhausted. Never delete failing checks or relax thresholds to produce a pass.

## Attribution and adaptations

- [matt-skills / skills/engineering/tdd/SKILL.md](https://github.com/mattpocock/skills/blob/74ca5fe077456a0b3b2f5310cf9430999fd0b5fd/skills/engineering/tdd/SKILL.md): Public behavior and independent expectations; accept established seams without repeated confirmation.

See [retained notices](../../THIRD_PARTY_NOTICES.md). No upstream executable or linked plugin is required.
