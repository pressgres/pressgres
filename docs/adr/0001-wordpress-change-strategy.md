# ADR-0001: WordPress change strategy (managed, version-pinned patchset)

- **Status:** Proposed
- **Date:** 2026-11-22
- **Deciders:** (pending: patchset codeowners, project lead, legal reviewer for licensing items)
- **Related issues:** pressgres/pressgres#7 (R-005); R-001, R-013, R-015, U-001, U-005; ADR-002, ADR-006, ADR-007

## Context

Pressgres needs native UUIDv7 primary keys (UUID-only, ADR-002). A `db.php` drop-in cannot change WordPress's integer casts, type declarations, REST schemas or editor ID assumptions ([02 — Architecture](../02-architecture.md#core-constraints)). Core PHP and the bundled block-editor JS therefore have to be modified for every supported WordPress release, including short-notice security releases.

Evidence from [R-005](../research/R-005-patch-mechanism-and-licensing.md):

- In wordpress-develop 7.1.5 the block-editor JS (`wp-includes/js/dist`) is not committed. It is copied from a prebuilt Gutenberg artifact pinned by SHA in `package.json`. Block PHP (`wp-includes/blocks/*.php`) is also copied from Gutenberg. Changes to either must be made in Gutenberg **source** and rebuilt.
- GPLv2 §2(a) requires prominent, dated notices on modified files. §3 requires complete corresponding source, including build scripts, for built forms. Hand-edited minified JS is not the "preferred form for making modifications".
- WordPress security fixes are not committed until release day, and follow-up releases can come within hours (6.9.2 → 6.9.3 in about 8 hours).
- A proof of concept (`tools/patchset/`) shows strict, hash-locked application. It rejects tampered upstream trees and patches and refuses offsets. A rebase dry run classifies each patch as CLEAN, REFRESH or CONFLICT.

## Decision

Adopt a **hybrid managed patchset**. Maintainers rebase in git forks. Pressgres ships a strict, hash-locked series of text patches applied to verified pristine upstream sources.

1. **Two series per supported release.** `patches/wordpress/<version>/` targets the wordpress-develop tag. `patches/gutenberg/<sha>/` targets the Gutenberg SHA that this wordpress-develop tag pins. Block PHP and editor JS changes go only in the Gutenberg series.
2. **Artifact format.** Each patch is made with `git diff --full-index` (pre- and post-image blob ids) and carries a DEP-3-style header: `Patch-Id`, `Upstream-Status`, `Date`, `License: GPL-2.0-or-later`, `Tests`. Each series has a `series` file listing the SHA-256 of every patch in apply order, and an `upstream.lock` with the upstream identity, the SHA-256 tree manifest digest and the expected patched-tree digest. `series` and `upstream.lock` are signed at release.
3. **Strict application in release CI.** Verify the upstream archive hash, then the SHA-256 tree manifest, then the patch hashes. Apply with no fuzz and no offset, check exact pre- and post-images, and reproduce the patched-tree digest. Any deviation is a hard failure.
4. **JS.** Patch Gutenberg source, build it once per pin with upstream's `IS_WORDPRESS_CORE` build, and publish the result as a Pressgres-owned, SHA-256-pinned and signed artifact. wordpress-develop consumes it through its existing `gutenberg.sha`/`ghcrRepo` mechanism. Built `js/dist` files are never edited by hand.
5. **Rebase workflow.** Maintainers keep `pressgres/<version>` branches in forks of wordpress-develop and Gutenberg, rebase with three-way merge, and export the series. Reviewers see the patches plus `git range-diff`. Every patch has a regression test.
6. **AST tooling** (nikic/php-parser, Rector, codemods) may be used to find sites and to generate candidate patches, and as CI lint. It never runs as a build-time transform. Its output is committed as reviewed patches.
7. **Security releases.** CI runs `rebase-check` automatically on every upstream tag. A documented hotfix path applies the upstream security diff on top of the shipped series when a full rebase cannot finish within the SLA. Proposed targets: 24 h when every patch is CLEAN or REFRESH, 72 h on CONFLICT. The final targets are set in ADR-006 and the support policy. *(ADR-0006 proposes relaxing these to best-effort targets of 72 h / 7 days for a solo maintainer.)*
8. **Compliance artifacts per release.** A generated `PRESSGRES-MODIFICATIONS.txt` and inline change markers (GPLv2 §2(a)); a published source bundle with the upstream references, both series and the build scripts (§3); and a license check and SBOM of both trees. The product is never named "WordPress" (trademark policy; ADR-007).

## Consequences

- **Positive:** what differs from upstream is small, reviewable and auditable. Builds are reproducible and verifiable before install, matching [07 — Compatibility](../07-compatibility.md)'s "hard fail if no matching signed patch manifest". The design satisfies AGENTS rule 8, and the source-availability story is clear.
- **Negative:** two series and a Gutenberg build per release add CI time and infrastructure: an artifact registry and a Node toolchain. Strict three-line context makes patches sensitive to nearby upstream edits, so more patches need REFRESH. Maintainers must handle releases in several time zones to meet a 24 h security SLA. WordPress core auto-updates must be blocked and replaced by Pressgres releases.
- **Neutral:** for each WordPress `x.y.z`, the compatibility matrix gains one row per release, keyed by the pair (wordpress-develop tag, Gutenberg SHA) plus the patchset hashes.
- **Migration impact:** none at the schema level. Upgrades require the new series to be locked and signed before the installer accepts the version.

## Alternatives considered

- **Quilt-style series only, no fork:** right shipping format, but quilt has no three-way merge, so rebasing under security time pressure is manual and error-prone. Kept as the *ship* format only.
- **Git fork as the product:** good rebase tooling, but the delta from upstream lives only in branch history. That is harder to audit and sign, and it drifts toward an unbounded fork ([11 — Trade-offs](../11-tradeoffs-risks.md)). Kept as the *maintainer workspace* only.
- **Build-time AST transforms:** least textual churn, but review moves from code to rules. A rule that silently stops matching ships untested code, and generated patches would still need review (AGENTS rule 7). Kept as authoring and lint tooling only.
- **Patching built `wp-includes/js/dist` output:** unreviewable minified diffs, overwritten on every Gutenberg sync, and not the GPL "preferred form". Rejected.
- **Dual IDs, no core patch:** out of scope; Pressgres is UUID-only (ADR-002).
