# Handoff format v1

`handoff.schema.json` is a JSON Schema 2020-12 document using a deliberately small subset. The zero-dependency validator implements exactly the keywords present here and rejects unsupported schema keywords. It loads this bundled schema only; it never resolves a remote schema or executes content.

Envelope: `schema_version`, `task_id`, `kind`, `revision`, `status`, `summary`, `payload`, `evidence`, `limitations`, `next_actions`. All properties are explicit and unknown properties fail. Examples under examples/ are blocked templates, not completed evidence. Revisions are full lowercase Git object IDs (40 or 64 hex) or synthetic fixture SHA-256 content identities. Never use a branch name as immutable evidence identity.

`complete` means the named procedure has produced its required artifact. For investigation/design/contract it does not imply any executed check. `blocked` means a required capability/input is absent; `incomplete` means work or evidence remains. Both require a limitation and a next action. Browser, test and delivery completion additionally require nonempty passing cases linked to current evidence. A schema pass is not a delivery approval.

Evidence includes ID, revision, method, status, `command` (an argv array, empty for non-command observations), environment digest, artifact path/hash pairs and observation. Paths are opaque references: validation never reads them. A self-report may be unverified, not a measured pass. Command observations need argv, and measured pass/fail records need at least one hashed artifact. These checks detect omissions, not forgery; the producing identity and hashes must be independently verified by the future controller.

Historical red evidence may reference a previous revision; green/current acceptance evidence must match the candidate. Cases cite evidence IDs. Complete test handoffs require an observed failing command for the target symptom and passing command evidence at the candidate; tests for unchanged behavior can instead remain an investigation artifact. Blocked browser handoffs require no invented browser evidence. A complete independent review must name a reviewer different from all listed implementation authors, but the validator cannot authenticate that claim.

Delivery stores only a proposed PR. There is no approval field or approval format in Phase 1. Usage null means unknown and cannot be treated as zero. An immutable source package and trusted environment are prerequisites for using the validator. Schema version changes will require explicit migrations; no migration is implemented.


For a filled, observed synthetic example, see [the invoice test handoff](../audit/evaluations/skills/handoffs/behavioral-testing.json), [its raw evidence](../audit/evaluations/skills/evidence/green.txt) and [the evaluation report](../audit/evaluations/skills/forward-report.md). Temporary absolute paths are retained for provenance; archive/manifest mapping is described in audit/evaluations/manifest.json. Validate one JSON file at a time; directories are not input documents.

Environment digest convention: write an environment.json containing interpreter/tool versions, OS/architecture, dependency identities, relevant configuration and dataset/hardware identities (where applicable). Exclude credentials and unnecessary personal paths. SHA-256 the exact UTF-8 file bytes and retain that file beside logs. This identifies recorded metadata; it does not establish hermetic execution. The forward run predates this convention and includes its interpreter path.

The Phase 1 budget payload represents finite attempts and wall time plus paid usage disabled. Other resource limits belong in scope/unknowns until the controller ledger exists. Validation is per-document: acceptance IDs across contract/testing/delivery handoffs must be reconciled by the reviewer; coverage across documents and authenticated producer identity are not enforced here.

Complete optimisation requires a terminal accepted/rejected decision, at least one recorded experiment, and current command evidence matching the correctness outcome. An accepted candidate requires passed correctness. A rejected candidate may have failed correctness; its benchmark should then remain unrun. A review verdict of findings requires at least one finding.
