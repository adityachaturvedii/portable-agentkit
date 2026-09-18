# CLI integration source and dependency review

Review date: 2026-09-18. Phase 0 skill-source pins, MIT notices and adaptations are unchanged. Phase 2 code is original standard-library Python; no upstream executable source, provider SDK, plugin or credential is vendored. External installed CLIs are invoked through their documented public command interface. Original toolkit outbound licensing is still deferred to distribution (D006).

| Runtime input | Observed compatibility / dependency | License and distribution treatment |
|---|---|---|
| Codex CLI | Installed `@openai/codex` 0.154.0; npm package requires Node ≥16 and version-matched optional native platform packages. The launcher spawns the native executable. Doctor records resolved launcher hash, not a full dependency attestation. | Installed package declares Apache-2.0. No source/binary copied or redistributed. |
| Claude Code | Installed native executable 2.1.220. Doctor records executable hash. Existing macOS Keychain-backed subscription visible under guarded host status. No SDK or additional dependency installed. | Separately supplied vendor application; no license or redistribution rights inferred from access to the CLI. Nothing redistributed. |
| Toolkit / sandbox | Python 3.9.6 standard library; macOS-provided `/usr/bin/sandbox-exec`; POSIX process APIs. | No new Python package, privileged service, container engine or OS dependency installed. Linux/Windows managed execution unsupported. |

Installed `--version`, `exec --help` / `--help`, and guarded auth status were inspected before implementation. Actual observations are in [doctor evidence](../evidence/phase2/doctor-host.json). The compatibility constants fail managed execution for unreviewed versions. Exact version matching is not cryptographic supply-chain verification; the installed host tools and platform remain trusted.

Primary references checked (documentation may move; installed behavior is authoritative for this experiment):

- [Codex noninteractive execution](https://learn.chatgpt.com/docs/non-interactive-mode): JSONL terminal/usage events, ephemeral execution and configuration/rules controls.
- [Codex authentication](https://learn.chatgpt.com/docs/auth): subscription versus API-key methods; status is not a purchased-credit guarantee.
- [Codex configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference): per-call settings, feature and permission controls. The generic provider retry fields cannot override the reserved built-in provider in this installed release, as actual startup evidence demonstrates.
- [Codex provider code at rust-v0.154.0](https://github.com/openai/codex/blob/rust-v0.154.0/codex-rs/model-provider-info/src/lib.rs): built-in provider and bounded retry definitions. Inspected as reference; no code copied. This is a version tag reference, not a newly audited full source tree.
- [Claude headless interface](https://code.claude.com/docs/en/headless), [environment variables](https://code.claude.com/docs/en/env-vars), and [sandboxing](https://code.claude.com/docs/en/sandboxing): print/stream output, safe mode, retry/turn controls and tool-specific boundary caveats. Installed public binary strings additionally confirmed the zero-retry environment-variable branch; no patching or extraction of user state.

Adaptation: provider event schemas are translated into neutral records; missing metrics stay unknown and raw redacted fields remain available. No output is treated as an approval or proof of its own success. Safe mode/ignore-config controls are per process, not edits to user configuration. `--bare` was deliberately excluded because it would change the authentication assumptions. API-key environment variables and provider overrides are not inherited.

This integration review is narrower than an audit of either entire CLI or every transitive dependency. No claim is made that a version, license, advertised flag or checksum proves runtime isolation. See [contracts](runtime-contracts.md), [effective matrix](sandbox-matrix.md), and [validation](phase2-validation-report.md).
