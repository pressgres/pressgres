# AGENTS.md — Instructions for AI coding agents

**Priority:** Security and data integrity > compatibility correctness > explicit release support > performance > convenience. This repository archive contains **specifications only**, not working application code.

1. Before work, read `README.md`, `docs/01-product-and-scope.md`, `docs/07-compatibility.md`, `docs/10-ai-agents.md` and touched subsystem docs.
2. Record task scope, current versions, architecture assumptions, files to touch, failure modes and acceptance tests.
3. Never claim an unverified SQL transformation or plugin is compatible. Preserve full UUIDv7 strings, never cast IDs to integers.
4. PostgreSQL 18+, managed WordPress 7.1 patchset and PHP 8.4 are the **proposed** first release target; exact patch releases are not yet pinned. Never claim production support based on this PRD alone.
5. Use parametrized SQL, AST-based transforms, fail closed on unsupported syntax, test via disposable PostgreSQL fixtures.
6. Do not run live data migrations or change database roles, secret stores, release tags or production configs without explicit human approval. Never bypass migration backup/verification.
7. Do not auto-generate/execute arbitrary PHP code as compatibility patches. Review/version/sign adapter manifests and test isolation.
8. Do not alter upstream WordPress files outside version-pinned `patches/wordpress/<version>`; add regression tests for every patch.
9. Run applicable tests; report commands and precise outcome honestly. No invented benchmarks or assertions of completed installs.
10. Submit small reviewed Conventional Commit PRs; add changelog and ADR when interface or migration contract changes. Document impacts to compatibility matrices.

**Review gate:** any auth, schema, UUID mapping, WordPress core patch, runtime permission, plugin activation or upgrade change requires designated human/codeowner approval. See detailed skill and role matrix in `docs/10-ai-agents.md`.
