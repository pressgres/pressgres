# ADR-0014 — Signed release lockfile

- **Status** Proposed
- **Date** 2026-11-23
- **Related issue** I-004 (pressgres/pressgres#24)

## Context

[ADR-0001](0001-wordpress-change-strategy.md) requires signed, hash-locked WordPress and Gutenberg series. [ADR-0006](0006-version-policy.md) requires exact release pins. The installer currently reports preview pins and permits missing artifact digests.

## Decision

Use the [v1 release lockfile](../../packages/release/README.md) to bind exact source and runtime versions, the two patch-series manifests and artifact digests to a detached Ed25519 signature over the original JSON bytes. Resolve signing keys only from an independently provisioned trust root. Keep the current preview manifest as the CLI display source until the installer consumes signed lockfiles. The release library reuses the shared exit codes for authenticity, unsafe paths and integrity failures.

Use a versioned, sorted tree manifest that includes file modes and symbolic link targets. Release tooling that adopts the tree format must generate both tree digests with the v1 algorithm. The ordered series, per-patch verification and strict application in ADR-0001 still apply.

## Consequences

Release consumers can verify staged bytes against signed metadata before use. Installer adoption requires provisioning and rotating public keys, generating lockfiles from actual release builds, and enforcing release selection. The library introduces no database migration or supported version tuple. The project lead reviews the contract before release adoption.
