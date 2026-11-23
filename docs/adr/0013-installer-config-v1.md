# ADR-0013 — Installer configuration v1

- **Status:** Proposed
- **Date:** 2026-11-23
- **Related issue:** I-002 (pressgres/pressgres#22)

## Context

The installer needs a versioned YAML contract that operators can validate before provisioning. Runtime and migrator credentials have different consumers under [ADR-0011](0011-ddl-staging-model.md).

## Decision

Require a string `schema_version` and reject unknown keys at every mapping in the [v1.0 schema](../../apps/installer-cli/schemas/pressgres-v1.json). Validate supplied settings before defaults or overrides are applied. Password fields accept `env:NAME` and `file:/absolute/path` references. Both CLI commands validate their syntax without accessing the referenced value. Database role names and password references must differ when both are supplied. Later preflight verifies connectivity and privileges with resolved credentials.

Report validation failures in the [CLI result envelope](0012-cli-result-envelope.md) with JSON pointers and redacted messages. Use exit 5 for invalid password references, including plaintext, and exit 2 for other configuration errors. Publish generated files with atomic per-file operations and require explicit permission via `--force` to replace them.

## Consequences

Configuration consumers can validate the YAML layer offline. Schema v1.0 is a preview contract and makes no change to the runtime compatibility matrix. Credential resolution and database migration remain separate installer operations.
