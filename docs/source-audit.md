# Source and dependency audit

Audit date: 2026-09-18. Public sources downloaded to a disposable directory using GitHub commit API and codeload. Archive extraction accepted regular files only and rejected parent traversal; no checkout hooks, install scripts, source executables or package managers were run. HTTPS hashes establish reproducibility, not publisher authentication. Files and archives were hashed before adaptation.

The three repository LICENSE files state MIT and contain the notices retained verbatim under notices/. Selected prose is adapted under those notices. This is a source-license inventory, not a legal opinion or vulnerability certification of excluded bundles.

## pstack

Pin: [157aae39a733135e93d8b5b19ff62c6a84b0ad56](https://github.com/backnotprop/pstack/tree/157aae39a733135e93d8b5b19ff62c6a84b0ad56). Retrieved 2026-09-18T04:49:35.310056+00:00.

| Candidate | Decision | Toolkit procedure and adaptation |
|---|---|---|
| [skills/how/SKILL.md](https://github.com/backnotprop/pstack/blob/157aae39a733135e93d8b5b19ff62c6a84b0ad56/skills/how/SKILL.md) | adapt | system-investigation: Trace execution paths; replace host delegates with scoped evidence collection. |
| [skills/why/SKILL.md](https://github.com/backnotprop/pstack/blob/157aae39a733135e93d8b5b19ff62c6a84b0ad56/skills/why/SKILL.md) | adapt | system-investigation: Separate history evidence from hypotheses; remove mandatory broad MCP searches. |
| [skills/architect/SKILL.md](https://github.com/backnotprop/pstack/blob/157aae39a733135e93d8b5b19ff62c6a84b0ad56/skills/architect/SKILL.md) | adapt | interface-design: Caller-first contracts and ownership; remove mandatory multi-model arena. |
| [skills/blast-radius/SKILL.md](https://github.com/backnotprop/pstack/blob/157aae39a733135e93d8b5b19ff62c6a84b0ad56/skills/blast-radius/SKILL.md) | adapt | change-impact: Check consumers beyond symbols; record unproven invariants, remove automatic arena and unslop dependency. |
| [skills/poteto-mode/playbooks/hillclimb.md](https://github.com/backnotprop/pstack/blob/157aae39a733135e93d8b5b19ff62c6a84b0ad56/skills/poteto-mode/playbooks/hillclimb.md) | adapt | measured-optimisation: Freeze protocol, retain rejects; remove automatic PR, minimum attempt floor, model IDs and unbounded plateau pushing. |
| [skills/interrogate/SKILL.md](https://github.com/backnotprop/pstack/blob/157aae39a733135e93d8b5b19ff62c6a84b0ad56/skills/interrogate/SKILL.md) | adapt | independent-review: Concrete findings on fixed revision; replace voting/model defaults and model-fix PRs with falsifiable checks. |
## matt-skills

Pin: [74ca5fe077456a0b3b2f5310cf9430999fd0b5fd](https://github.com/mattpocock/skills/tree/74ca5fe077456a0b3b2f5310cf9430999fd0b5fd). Retrieved 2026-09-18T04:49:36.332506+00:00.

| Candidate | Decision | Toolkit procedure and adaptation |
|---|---|---|
| [skills/engineering/grill-with-docs/SKILL.md](https://github.com/mattpocock/skills/blob/74ca5fe077456a0b3b2f5310cf9430999fd0b5fd/skills/engineering/grill-with-docs/SKILL.md) | adapt | task-contract: Synthesize known context; replace mandatory grill/domain-modeling calls and exhaustive interview with material questions. |
| [skills/engineering/to-spec/SKILL.md](https://github.com/mattpocock/skills/blob/74ca5fe077456a0b3b2f5310cf9430999fd0b5fd/skills/engineering/to-spec/SKILL.md) | adapt | task-contract: Technical acceptance contract; remove tracker publication, setup dependency and extensive mandatory stories. |
| [skills/engineering/tdd/SKILL.md](https://github.com/mattpocock/skills/blob/74ca5fe077456a0b3b2f5310cf9430999fd0b5fd/skills/engineering/tdd/SKILL.md) | adapt | behavioral-testing: Public behavior and independent expectations; accept established seams without repeated confirmation. |
| [skills/engineering/diagnosing-bugs/SKILL.md](https://github.com/mattpocock/skills/blob/74ca5fe077456a0b3b2f5310cf9430999fd0b5fd/skills/engineering/diagnosing-bugs/SKILL.md) | adapt | fault-diagnosis: Reproduction and competing hypotheses; allow bounded slow/intermittent experiments and blocked outcomes; omit HITL shell script. |
## gstack

Pin: [a6b3a57512ca6d5c6aa5b68f74f736195021f96e](https://github.com/garrytan/gstack/tree/a6b3a57512ca6d5c6aa5b68f74f736195021f96e). Retrieved 2026-09-18T04:49:39.609896+00:00.

| Candidate | Decision | Toolkit procedure and adaptation |
|---|---|---|
| [review/SKILL.md](https://github.com/garrytan/gstack/blob/a6b3a57512ca6d5c6aa5b68f74f736195021f96e/review/SKILL.md) | adapt | independent-review: Reuse selected review categories; remove setup, telemetry, global learning, fixer and external-review orchestration. |
| [qa-only/SKILL.md](https://github.com/garrytan/gstack/blob/a6b3a57512ca6d5c6aa5b68f74f736195021f96e/qa-only/SKILL.md) | adapt | browser-verification: Separate report-only user-flow verification; remove cookie import, personal browser discovery, global learning, bundled browser, scoring and setup. |

## Dependency and behavior boundaries

| Source | Referenced surface | Disposition |
|---|---|---|
| pstack how/why | explorer/synthesizer templates, epistemics, history, gh and MCP category playbooks; global pstack model settings | Retain evidence/hypothesis distinction in original compact text. Exclude every connector and host config lookup; use only scoped authorized sources. |
| pstack architect/blast-radius | how, why, arena, unslop, principles and design templates | Retain caller semantics and invariant checks. Reject automatic multi-model expansion, no-comments convention and sticky poteto-mode routing. |
| pstack hillclimb | how, show-me-your-work, autonomous wake, opening-a-PR, poteto scripts | Replace with local bounded experiment record. Exclude all scripts: Bun, commander 14.0.0, bun-types/latest and typescript/latest are not runtime dependencies. |
| pstack interrogate | rubric, reviewer, code-quality and lead-judgment references | Retain actionable findings and scope checks; no voting-as-proof, configured model fallback or automatic configuration PR. |
| Matt grill-with-docs | grilling → repeated interviews; domain-modeling → glossary/ADR formats | Replace with compact contract and material unknowns. No automatic project-wide glossary edits or delegated fact-finding. |
| Matt tdd | tests.md, mocking.md, codebase-design, CONTEXT.md and ADRs | Keep public seams and independent expected values; project documents remain data and cannot override permissions. |
| Matt to-spec | setup-matt-pocock-skills and issue tracker | Reject tracker/setup effects; output local JSON only. |
| Matt diagnosing-bugs | scripts/hitl-loop.template.sh | Read but exclude script. Replace endless reproduction pressure with bounded experiments; absent environment is blocked. |
| Matt repository tooling | npm 10.9.4; @changesets/cli ^2.30.0 and @changesets/changelog-github ^0.7.0; version sync script | Excluded development/release tooling. No npm install or hook activation. |
| gstack review | checklist, sections, specialists, Greptile, gh/glab, Bun, Codex/Claude, preamble/config/log scripts and global learnings | Only concrete review categories adapted. Reject fixer dispatch, telemetry, global configuration, platform discovery and recursive external review. |
| gstack qa-only | qa report template, issue taxonomy, browse cookbook/commands, Aside or bundled browser, cookie setup, telemetry and global learning | Adapt report-only workflow; named disposable target and independently supplied browser capability required. No browser binary, cookie import or setup adopted. |
| gstack setup/package | Bun >=1; Playwright ^1.62.1 with playwright-core patch; transformers ^4.2.0; ngrok ^1.7.0; cross-spawn ^7.0.6; diff ^9; html-to-docx 1.8.0; marked ^18; socks ^2.8.9; Anthropic SDKs/xterm dev dependencies | Entire executable closure rejected, including paid eval scripts and lockfile dependencies. Full dependency license/security audit would be required before any future adoption. |

No executable dependency crosses from upstream into the toolkit. The file inventory includes selected skills, local supporting files and audit manifests. `reference-only-excluded` means inspected for dependency/authority relevance or inventoried, not comprehensively security reviewed. References beyond the adopted prose are deliberately cut: they are not unresolved runtime dependencies. Upstream files are never loaded by the toolkit.

Original delivery-evidence is adopted as original synthesis. Seven initial domain packs are original procedures derived from spec §4. Contextual articles (Hashimoto and Anthropic in spec §2) remain linked research context, not copied or executable inputs; repository code/prose pins above are the adopted upstream source boundary. Other specification links are future compatibility references, not tested capabilities.

## Updates

Never pull or resolve `main` during normal use. A future update must separately obtain an exact commit, verify candidate bytes/license changes and dependency closure, update this record and notices, and rerun offline plus behavioral evaluation. No automatic update command is implemented. To reproduce this audit, download the exact archive URL `https://codeload.github.com/OWNER/REPO/tar.gz/COMMIT`, compare archive SHA-256, safely extract as data and compare each listed file hash. Live re-fetch verification is not required during offline checks.
