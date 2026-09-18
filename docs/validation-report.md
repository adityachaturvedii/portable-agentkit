# Phase 0–1 validation

This report separates offline consistency, synthetic behavior and future execution capabilities. The final local revision/check summary is recorded with the delivery proposal and its external head-bound receipt.

## Observed environment

macOS, Apple-provided Python 3.9.6, Git 2.54.0. Runtime uses only the Python standard library. No packages installed, CLI providers invoked, GPU contacted, paid APIs enabled or global CLI settings modified. Only public upstream archives and the new toolkit/disposable repositories were accessed.

## Automated checks

`python3 -m unittest discover -s tests -v`: 27 tests passed after adding archived-evidence integrity and a common independent acceptance oracle for both agent fixes. The final run is recorded in the local receipt. Tests exercise 18 explicit intent/domain cases, six buggy/corrected disposable CPU project families, malformed JSON, unsupported kinds/versions, duplicate evidence, stale revisions, self-reports, self-review, missing browser and incorrect optimization outcomes. A relocation test copies the entire toolkit to a path containing spaces and runs checks with an empty HOME; HOME remains empty.

The six CPU families cover invoice arithmetic, split leakage, a scalar gradient, inference cache identity, stable softmax and SQLite idempotency. Each planted defect fails its independent expectations and its corrected counterpart passes. Scalar/CPU examples do not validate a training framework, CUDA, mixed precision or a real serving system. The 18 selection cases exercise explicit intent mapping, not learned or natural-language routing.

`python3 -m agentkit check`: verifies skill inventory, relative references, exact notice bytes and all ten blocked format examples. Separately, all 88 upstream file hashes were compared with the downloaded pinned snapshots and matched. Offline package checking does not contact upstream or establish publisher signatures. The system skill-creator `quick_validate.py` could not run because PyYAML is absent (`ModuleNotFoundError: yaml`); that check is unavailable, not passed. No dependency was installed to bypass the limitation.

## Independent forward task and matched native baseline

Two independent agent contexts received the same synthetic invoice request, original source, 8-experiment allowance and 300-second target. One used the curated pack; the other used no toolkit or skills. These are development evaluations, not held-out trials. Model identity/usage and total wall time were not uniformly instrumented, so resource parity and efficiency are not established.

| Observation | Native baseline | Skills condition |
|---|---|---|
| Merchandise discount excludes shipping; invalid ranges rejected | Achieved | Achieved |
| Meaningful failing control and passing fixed tests | 7 test methods; 10,201 invariant combinations; original yields 11 assertion failures | 6 test methods, invalid-range subcases, red run plus discriminating shipping probe |
| Missing checkout browser/build | Explicitly unverified | Blocked browser handoff; incomplete delivery handoff |
| Local evidence/proposal | Narrative, logs and patch | Eight schema-valid handoffs, logs and diff |
| Reported experiments | 4 | 3 |
| Time | Agent reports 112.4 seconds; timing excluded initial reads | 1.333 seconds subprocess work; total agent wall time unknown |

Both conditions solved the planted API defect and avoided a false browser claim. The skills condition produced structured handoffs; the baseline included broader test enumeration. Neither result establishes that skills improve correctness, time, cost or review quality. No statistical superiority is claimed. A future matched repeated evaluation must instrument both conditions consistently and protect held-out cases.

Original artifacts and file hashes are retained under [audit/evaluations](../audit/evaluations/manifest.json). Temporary absolute paths are historical provenance; archived copies remain available after those directories disappear. Forward artifacts were produced before the clarity corrections below. The formal JSON contracts were assembled after implementation, so this evaluation does not establish enforced workflow order. The forward evaluator did not fabricate an independent reviewer.

## Corrections from the forward test

- Clarified the schema field is `command`, containing an argv array.
- Added a linked, filled synthetic red/green example with real logs.
- Limited database/transaction requirements to relevant backend behavior.
- Documented file-only validation, environment digest construction and current budget representation.
- Documented that cross-document acceptance coverage is manually reconciled; no controller claim is made.

## Not verified / planned

Browser interactions, GPU performance/races, native CLI authentication/isolation, canary-secret protection, egress restrictions, sibling/common-Git protection, independent role authentication, exact resource accounting, restart/recovery, atomic reservations, remote cancellation and stale approval enforcement are not implemented or tested. Validation of a claimed hash/reviewer identity cannot prove authenticity. Prompt guidance and offline checks are not security boundaries. Held-out cross-provider and baseline calibration remain later work.
