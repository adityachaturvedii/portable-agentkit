# Bounded static-web product workflow

This Phase 4 increment adds one reusable product profile for a fresh, controller-created static web repository. It is not general repository onboarding. The profile exposes four tracked product files (`README.md`, `game.js`, `index.html`, and `styles.css`), keeps `package.json`, controller state, Git metadata, acceptance source, evidence, and approval data outside worker authority, and permits no package download or dependency installation.

Product submission makes one accounted tech-lead provider call. The planner receives the original brief, observable controller-owned criteria, a bounded inventory, resource ceilings, and a hash-verified planning context. It returns JSON only. Controller validation rejects changed requirements or acceptance, stale inventory, unknown or unsafe paths, unsupported project operations, cycles, excessive fan-out, inconsistent interface/dependency summaries, overlapping independent write scopes, and plans that cannot reserve mandatory implementation, verification, and independent review.

The Claude planning request records an explicit 8,192 generated-output-token allocation. This is a provider execution control, not a token-spend cap: reported input, output, cached and cache-creation usage remain observations, and billing remains unknown. Codex has no tested equivalent output-token option and rejects this setting.

The planner supplies decomposition, not source code. There are no product-specific task graphs or finished implementations in the harness. One cohesive assignment is preferred. At most two assignments are accepted, and the existing scheduler, dependency snapshots, atomic claims, isolated worktrees, brokered integration, bounded repair, authentication recovery, routing, and usage ledger remain authoritative.

The controller build check is the documented `node --check game.js` command. The Node executable is pinned by path and SHA-256 during planning, copied into the verifier's disposable runtime, and executed with the protected mechanics test in a separate constrained candidate copy. The static profile downloads no dependencies. `package.json` provides `npm run build` as an optional local convenience, but the controller does not run npm or grant package-manager network access.

After exact-revision verification and cross-provider review pass, the task stops at `review_complete`. A supervised loopback preview must then be started and stopped. Browser evidence must cover every predeclared acceptance ID, identify the browser, bind the clean candidate revision, hash any screenshots retained under the evidence directory, require final human visual judgment, and prove the recorded preview process was cleaned up. Failed browser checks enter the same bounded repair ledger; absent browser capability remains a visible gap. A screenshot alone never passes a behavioral criterion.

Submit a product from files so shell quoting cannot alter the brief or protected test:

```sh
python3 -m agentkit product submit \
  --root /tmp/agentkit-product \
  --task-id product-demo \
  --brief-file /tmp/product-brief.txt \
  --acceptance-file /tmp/product-acceptance.json \
  --mechanics-test /tmp/product-acceptance.mjs \
  --max-calls 8 \
  --max-provider-calls 8 \
  --max-concurrency 2 \
  --max-repairs 2 \
  --max-escalations 2 \
  --max-elapsed-seconds 1200 \
  --planning-timeout 180 \
  --implementation-timeout 180 \
  --review-timeout 180 \
  --verification-timeout 10 \
  --live \
  --authorize-subscription-smoke
```

Inspect and execute the validated plan:

```sh
python3 -m agentkit product plan --root /tmp/agentkit-product --task-id product-demo
python3 -m agentkit product start --root /tmp/agentkit-product --task-id product-demo \
  --live --authorize-subscription-smoke
python3 -m agentkit product status --root /tmp/agentkit-product --task-id product-demo
python3 -m agentkit product preview-serve --root /tmp/agentkit-product --task-id product-demo
# Interact in the browser, then press Ctrl+C in this terminal to record confirmed cleanup.
python3 -m agentkit product browser-record --root /tmp/agentkit-product \
  --task-id product-demo --evidence /tmp/browser-evidence.json
python3 -m agentkit product package --root /tmp/agentkit-product --task-id product-demo
```

`browser-record` is a controller evidence import, not a browser automation engine. The acceptance operator or a separately controlled browser driver creates observations after real interaction and only after the foreground preview records cleanup. One `preview-serve` owner retains process control through Ctrl+C. The package records `approval.recorded=false` and performs no push, PR, merge, deployment, or publication.

Current support is macOS, trusted generated code, installed subscription CLIs, one provider planning call, at most two provider workers, a dependency-free static project, controller-owned Node mechanics checks, an owned loopback preview, and externally driven browser interaction. Comprehensive browser credential isolation, browser egress containment, hostile generated code, package installation, service workers, backends, arbitrary build tools, detached process containment, Linux/Windows/GPU execution, personal repositories, and crash-safe preview recovery are unsupported.
