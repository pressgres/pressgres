# tools/patchset — strict patch-series proof of concept (R-005)

**Status: research demo, not production tooling.** It shows the mechanism proposed in [ADR-0001](../../docs/adr/0001-wordpress-change-strategy.md) and [R-005](../../docs/research/R-005-patch-mechanism-and-licensing.md). The example patches are illustrative only and are **not** the Pressgres UUID patchset. Real patches belong in `patches/wordpress/<version>/` (see `AGENTS.md` rule 8).

## What it does

`bin/patchset` applies an ordered series of git-format patches to a pristine upstream tree and fails loudly on anything other than an exact, expected result:

| Check | Fails when |
|---|---|
| Upstream tree digest | SHA-256 of the sorted per-file SHA-256 manifest (and the file count) differs from `upstream.lock` |
| Series hash manifest | any patch file differs from its SHA-256 in `series` |
| Pre-image | any touched file's git blob id differs from the `index <pre>..<post>` line in the patch |
| Strict apply | `git apply` needs fuzz, reports an offset, or fixes whitespace |
| Post-image | any touched file's blob id differs from the patch's `<post>` id |
| Patched tree digest | the resulting tree differs from `patched_tree_manifest_sha256` in `upstream.lock` (reproducibility) |

It also writes `PRESSGRES-MODIFICATIONS.txt` into the patched tree (a deterministic list of modified files and change dates) as an aid for GPLv2 §2(a) notices.

`rebase-check` is a dry run against a different tree (for example the next upstream release). It never modifies the target and classifies each patch, applying them in order in a scratch copy:

- `CLEAN`: pre-image identical, nothing to do.
- `REFRESH`: the file changed but the hunks still apply (possibly with an offset); regenerate the patch so it applies exactly again.
- `CONFLICT`: hunk context changed; a maintainer must rebase. Rejected hunks are printed.

Exit codes: `0` ok, `1` verification or strict-apply failure, `3` rebase-check found patches that need maintainer action.

## Layout

```text
tools/patchset/
├── bin/patchset                      # manifest | lock | verify | apply | rebase-check
├── demo.sh                           # runs every scenario against the reference sources
├── demo-output.txt                   # captured output of the last demo run
└── examples/patches/
    ├── wordpress/7.1.5/              # PHP series against wordpress-develop 7.1.5 src/
    │   ├── series                    # "<sha256>  <patch>" in apply order
    │   ├── upstream.lock             # upstream id + tree and patched-tree digests
    │   └── 000N-*.patch              # git diff --full-index with a DEP-3-style header
    └── gutenberg/89408c2/            # JS SOURCE series against Gutenberg at the pinned SHA
```

Patch headers (`Patch-Id`, `Upstream-Status`, `Date`, `License`, `Tests`, …) follow the spirit of Debian DEP-3 (<https://dep-team.pages.debian.net/deps/dep3/>). `git apply` ignores text before the first `diff --git` line.

## Run it

```sh
# From the repository root. REFERENCE_ROOT holds wordpress-develop-7.1.5/ and gutenberg-89408c2/.
tools/patchset/demo.sh /path/to/pressgres/reference
# Maintainer only: re-pin digests after intentionally changing patches.
RELOCK=1 tools/patchset/demo.sh /path/to/pressgres/reference
```

Upstream copies go to `tools/patchset/.work/` (gitignored). The demo deletes them at the end unless `KEEP_WORK=1` is set. The demo takes about 30 s on a laptop, mostly copying and hashing about 16,000 files. Requirements: bash 3.2+, git, `rsync`, `perl`, `php` (only for the lint step), and `sha256sum` or `shasum`.

## Known limits

- Not implemented here: signing (`upstream.lock` and `series` should be signed, for example with Sigstore or `ssh-keygen -Y sign`), SBOM output, and the Gutenberg rebuild (`npm ci && npm run build` with `IS_WORDPRESS_CORE=true`). The JS demo stops after patching the Gutenberg source.
- The upstream tree in the demo is `wordpress-develop/src`. A release pipeline would pin the wordpress.org release archive (published with MD5 and SHA-1 only) and record our own SHA-256 manifest.
- `git apply` runs outside any repository, because `GIT_CEILING_DIRECTORIES` stops it from finding the Pressgres worktree. The three-way fallback (`--3way`) is therefore not used here. It belongs in the maintainer's git-fork rebase workflow, not in the release apply step.
