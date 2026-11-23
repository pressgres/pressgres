# ADR-0012 — Versioned CLI result envelope

- **Status** Proposed
- **Date** 2026-11-23
- **Related issue** I-009 (pressgres/pressgres#21)

## Context

Operators read CLI output at the terminal. Automation needs a stable way to read results and diagnostics, including failures during argument parsing. The installer and runtime already share exit codes and diagnostic fields.

## Decision

Commands produce a result rendered by the application. With `--format=json`, the application writes a single [`pressgres.cli/v1` object](../../apps/installer-cli/schemas/cli-v1.json) to stdout and returns the same exit code to the process. Command-specific data lives in `data`. A usage failure has exit code 2 and carries the canonical command name when known. Unexpected failures have exit code 1 and carry a correlation ID. Diagnostics use the shared contracts and omit raw arguments and unexpected exception details.

Human output uses stdout for success and stderr for errors. `--no-interaction` is a global option. `version` reads the packaged release manifest and reports missing artifact hashes explicitly.

## Consequences

Automation can use the process exit status and parse the same envelope on success and failure. Breaking envelope changes require a new schema version. The first command is read-only and introduces no database migrations.
