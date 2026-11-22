# R-005 — WordPress patching mechanism and redistribution obligations

- **Issue:** pressgres/pressgres#7 · **Roadmap:** [R-005](../08-roadmap.md) · **Feeds:** [ADR-001](../adr/0001-wordpress-change-strategy.md), ADR-007, R-013, R-015, U-005
- **Date:** 2026-11-22 · **Status:** research spike, findings for review
- **Pinned sources:** `wordpress-develop-7.1.5` (shallow clone, HEAD `984163c92ef66b6186538ecf01bacb97fc097541`) and `gutenberg-89408c2` (HEAD `89408c2b9bd944575dfa9039bc6870da1c8f56cb`), both read-only. Paths below are relative to the reference root.

> **Not legal advice.** Section 3 is an engineering reading of license texts and public policy pages, written to frame questions for counsel. Nothing here is a legal opinion or a trademark clearance.

## Summary of findings

1. **Recommended mechanism: hybrid (option e).** Maintainers work in a **git fork** of `wordpress-develop` and of Gutenberg, with one branch per pinned upstream release. The **shipped and reviewed artifact** is an exported, ordered **patch series**: `git diff --full-index` patches with DEP-3-style headers, a `series` file of SHA-256 hashes and an `upstream.lock` that pins the upstream tree digest and the expected patched-tree digest. Release CI applies the series strictly to a checksum-verified pristine upstream. Codemods (nikic/php-parser or Rector, jscodeshift) may help *author* patches, but their output is committed as reviewed text patches. They never run at build time.
2. **JS must be patched at Gutenberg source, never in `wp-includes/js/dist`.** In wordpress-develop 7.1.5, `src/wp-includes/js` is gitignored (`wordpress-develop-7.1.5/.gitignore:39`). The block-editor bundles come from a prebuilt Gutenberg artifact downloaded from GHCR at the SHA pinned in `package.json` (`wordpress-develop-7.1.5/package.json:9-12`, `wordpress-develop-7.1.5/tools/gutenberg/download.js:7-20`) and are copied in by `build:gutenberg` (`wordpress-develop-7.1.5/Gruntfile.js:2220-2231`). The built bundles are minified output. GPLv2 defines source as "the preferred form of the work for making modifications to it" (`wordpress-develop-7.1.5/src/license.txt:193-197`), so hand-patching the dist output would also weaken compliance with the source-availability terms.
3. **Some core PHP is also Gutenberg-owned.** `wp-includes/blocks/*.php` (92 top-level files in 7.1.5) and `wp-includes/build/*.php` are copied from the Gutenberg build (`wordpress-develop-7.1.5/tools/gutenberg/copy.js:79-92`, `:296-302`; `wordpress-develop-7.1.5/Gruntfile.js:697-718`; listed as Gutenberg-sourced in `Gruntfile.js:68-80`). Patches to these files belong in the Gutenberg series, or the next Gutenberg sync overwrites them. A rough heuristic found `absint`/`(int)` in 25 of the 92 files. That count is a lead for R-001/R-013, not an audit.
4. **The demo works** (`tools/patchset/`, captured output below). It rejected a tampered upstream tree, rejected a tampered patch, refused an offset-only drift in strict mode, and classified a simulated next release as `REFRESH` (offset) or `CONFLICT` (rejected hunk shown). A change *adjacent* to a hunk, three comment lines right above `function get_post_custom(`, already causes a `CONFLICT`. Three context lines make the series sensitive to nearby upstream edits. This sensitivity is useful for review but costs rebase effort.
5. **Security releases come with no public advance notice and can follow each other within hours.** Security fixes "are not committed until the day of a release" (<https://make.wordpress.org/core/handbook/best-practices/backporting-commits/>). 6.9.3 shipped "around eight hours after 6.9.2" (<https://make.wordpress.org/core/2026/03/25/wordpress-6-9-2-retrospective/>). Only the latest version is officially supported, and backports are "a courtesy" (<https://wordpress.org/about/security/>). Pressgres therefore needs an automated rebase-check on every upstream tag plus a documented hotfix path (proposed SLA below).
6. **GPL:** a Pressgres distribution of patched WordPress must be GPL-2.0-or-later as a whole (GPLv2 §2(b), `src/license.txt:136-139`). It must carry prominent notices on modified files stating the change and its date (§2(a), `src/license.txt:133-134`). Recipients must be able to get the complete corresponding source, including "the scripts used to control compilation and installation" (§3, `src/license.txt:172-197`). For Pressgres that means the patches, the Gutenberg source at the pinned SHA and the build scripts. Running patched WordPress only as a service, without distributing it, triggers no source obligation under GPLv2 (<https://www.gnu.org/licenses/gpl-faq.html#UnreleasedMods>).
7. **Trademark:** the WordPress Foundation policy says non-licensed businesses "cannot use [the marks] as part of a product, project, service, domain name, or company name". It also says "Under no circumstances is it permitted to use WordPress or WordCamp as part of a domain name", and "Please do not use 'WP' in any way that confuses people" (<https://wordpressfoundation.org/trademark-policy/>). Descriptive nominative use is allowed: "Hosting for WordPress" is the policy's own example. A modified distribution must not be called "WordPress". Candidate names such as "WPPostgres" ([17 — Names](../17-names.md)) carry the "WP" confusion risk. This goes to R-015/ADR-007 and counsel.

## 1. Mechanism options

### 1.1 How upstream is assembled (facts that constrain every option)

| Layer | Where it comes from in 7.1.5 | Evidence |
|---|---|---|
| Core PHP (`wp-admin`, most of `wp-includes`) | committed in wordpress-develop `src/` | tree listing; 3,798 files under `src/` (demo manifest) |
| Gutenberg JS packages, script modules and block CSS | **not committed**: `/src/wp-includes/js`, `/src/wp-includes/css/dist` and block `*.js`/`*.css` are gitignored | `wordpress-develop-7.1.5/.gitignore:39-45`; `Gruntfile.js:59-66` (`gutenbergUnversionedFiles`) |
| Gutenberg build artifact | `tools/gutenberg/download.js` downloads the OCI blob `ghcr.io/WordPress/gutenberg/gutenberg-wp-develop-build:<sha>`, checks its SHA-256 and size against the OCI manifest, then extracts it to `./gutenberg` | `tools/gutenberg/download.js:7-20`, `:113-183`; `package.json:9-12` |
| Artifact producer | Gutenberg CI builds `IS_WORDPRESS_CORE=true` with `.wpPlugin.name = "wp"` (`npm run build -- --skip-types`) and pushes it to GHCR with `oras push` tagged by commit SHA | `gutenberg-89408c2/.github/workflows/build-plugin-zip.yml:250-260`, `:300-363`; `gutenberg-89408c2/bin/build-plugin-zip.sh:81` |
| Gutenberg-sourced but committed in core | block PHP (`wp-includes/blocks/*`), `wp-includes/build`, `theme.json`, asset manifests | `Gruntfile.js:68-80` (`gutenbergVersionedFiles`); `tools/gutenberg/copy.js:296-302` |
| Configurable source | `readGutenbergConfig()` reads both `gutenberg.sha` and `gutenberg.ghcrRepo` from `package.json` | `tools/gutenberg/utils.js:110-125` |

Consequence: a Pressgres build needs **two** patch series: one on wordpress-develop and one on Gutenberg at the SHA that wordpress-develop pins. The patched Gutenberg is built once per pin, and the result is a Pressgres-owned artifact with its own SHA-256. Because `ghcrRepo` and `sha` are configurable (`utils.js:110-125`), a one-line patch to `package.json` in the WordPress series can point `grunt build` at that artifact, so upstream's copy logic is reused unchanged. This is an inference from the code and has not been executed: the full npm build needs network access.

### 1.2 Comparison

Rebase effort is relative. Absolute effort depends on patch count and spread, which R-013 has to measure.

| Criterion | (a) quilt-style series on verified tarball | (b) git fork, branch per release, rebase | (c) git fork + exported `format-patch` series as artifact | (d) build-time AST transforms (php-parser/Rector, codemods) | (e) **hybrid**: (b) to work in, (c)+(a) to ship, (d) only to author |
|---|---|---|---|---|---|
| Rebase per minor/security release | Manual `quilt refresh`; no three-way merge, so every context change is resolved by hand | `git rebase --onto` with three-way merge and `rerere`; best tooling | as (b) | Lowest *textual* churn, since rules match AST shapes, not lines. Every rule still needs re-validation against new code, and a silent no-match is the main risk | as (b) for the work; the export is mechanical |
| Reviewability | Excellent: each patch is a small diff with a header | Good, but the delta from upstream is spread over branch history; reviewers need `git range-diff` | Excellent, plus `git range-diff` between releases | Poor for the *result*: reviewers read transform rules, not the code that ships. The output diff must be generated and reviewed anyway | Excellent: reviewed patches plus a range-diff on rebase |
| Reproducibility | High if the tarball hash and patch hashes are pinned | Depends on fork hosting; the history is the artifact | High: patches plus upstream hash fully determine the output (demo: patched-tree digest locked) | Depends on transformer version, PHP version and rule order; pin all of them | High (demonstrated) |
| Signing / hash manifest | Natural: `series` + `upstream.lock` | Signed tags/commits; ties trust to the forge | Natural, same as (a) | Sign the rule set and the generated diff | Natural (demonstrated hash manifest; signing is a follow-up) |
| CI fit | Simple: verify, apply, test | Needs fork access and history; heavier | Simple apply in CI; fork only for maintainers | Needs the transformer toolchain in the build; AGENTS rule 7 forbids auto-generated PHP patches without review | Simple apply in release CI; fork CI for rebase-check |
| PHP | yes | yes | yes | yes (php-parser/Rector) | yes |
| Built JS (`js/dist`) | Patching minified dist is unreviewable, rebuilt every Gutenberg sync, and not the "preferred form" (§3) | Needs a Gutenberg fork + rebuild anyway | Gutenberg series + rebuild | JS codemods on Gutenberg source + rebuild; still a rebuild | **Gutenberg source series + rebuild → Pressgres artifact** |
| Short-notice security release | Hand-refresh every touched patch under time pressure | Fast if the rebase is clean | Fast if clean | Fast when rules still match; dangerous when they silently stop matching | Fast: automated rebase-check on tag, then range-diff review |
| Satisfies AGENTS rule 8 (`patches/wordpress/<version>`) | yes | no on its own (patches live in a fork) | yes | no (no patches dir) | yes |

### 1.3 Why not pure (a), (b) or (d)

- **(a) alone** ships the right artifact but gives maintainers poor rebase tools. Quilt has no three-way merge, and `patch` silently accepts fuzz unless told not to. The demo's strict wrapper fixes this for *applying*, not for *rebasing*.
- **(b) alone** makes the fork history the product. That conflicts with "managed version-specific patchset, not unbounded fork" ([14 — Open decisions](../14-open-decisions.md)) and with the `patches/wordpress/<version>/` layout ([02 — Architecture](../02-architecture.md)). It is also harder to audit what differs from upstream.
- **(d) alone** looks attractive for repetitive edits (`absint( $post_id )` → helper), but it moves review from code to rules. A rule that stops matching after an upstream refactor produces a build that differs from what was tested, with no error. Generated output must be reviewed anyway (AGENTS rule 7), so commit that output as patches. Use AST tooling to *find* sites (R-001), to *generate* candidate patches and as a CI lint ("no new `absint(` on ID parameters in touched functions").

### 1.4 Security releases and a proposed SLA-compatible workflow

Upstream facts: fixes land on release day only (handbook above). The 6.9.2 cycle back-ported to 22 branches and needed a fast-follow release about 8 hours later because of a regression (retrospective above). The release page publishes MD5 and SHA-1 checksums per archive and no SHA-256 (<https://wordpress.org/download/releases/>). The per-file checksum API returns 32-hex (MD5-length) values (<https://api.wordpress.org/core/checksums/1.0/?version=7.1.5&locale=en_US>). Pressgres should therefore compute and pin its own SHA-256 manifest after verifying the upstream hash.

Proposed workflow. The targets are proposals for ADR-006 and the support policy, not commitments:

1. **Detect (automated, within 1 h of an upstream tag).** CI watches `WordPress/wordpress-develop` tags and the wordpress.org release feed. On a new tag in a supported branch it fetches the tag, verifies the wordpress.org archive SHA-1, generates the SHA-256 manifest and runs `patchset rebase-check` for both series (WordPress, plus Gutenberg if the pinned SHA changed).
2. **Classify.** If every patch is `CLEAN` or `REFRESH`, a bot opens a PR with refreshed patches, a new `upstream.lock` and `git range-diff` output. Any `CONFLICT` pages the patchset owner.
3. **Rebase in the fork.** The maintainer runs `git rebase --onto <new-tag> <old-tag> pressgres/<old>` (with `rerere` enabled), then exports with `git format-patch`/`git diff --full-index` into `patches/wordpress/<new>/`. Every patch keeps its regression test (AGENTS rule 8).
4. **Gate.** Required checks: strict apply on pristine upstream, the patched-tree digest is reproduced by a second runner, UUID regression suite, upstream PHPUnit subset, and a codeowner review of the range-diff ([09 — Engineering standards](../09-engineering-standards.md)).
5. **Release.** Sign `series` and `upstream.lock`, publish source (patches + upstream reference + build scripts) alongside the artifact, and update the release manifest ([07 — Compatibility](../07-compatibility.md)).
6. **Hotfix path when step 3 cannot finish in time.** Apply the upstream security diff (from the tag's commits) as an extra patch on top of the currently shipped `<version>` series, release `<version>+pg.N`, then do the full rebase normally.

Proposed targets: **security release with only `CLEAN`/`REFRESH` → patched release within 24 h; with `CONFLICT` → 72 h, or the hotfix path within 24 h; regular minor → 7 days; major → experimental until revalidated** ([07 — Compatibility](../07-compatibility.md)). Two inputs decide whether these are realistic: patch count from R-013, and whether maintainers in several time zones are funded. Note that WordPress auto-updates of minor releases would *replace* patched core. Pressgres must block core auto-updates and deliver its own (`WP_AUTO_UPDATE_CORE` and the updater policy, [14 — Open decisions](../14-open-decisions.md) item 14; not verified in this spike).

## 2. Proof of concept (`tools/patchset/`)

**What was built.** `tools/patchset/bin/patchset` (bash 3.2 compatible, git and sha256 only) with the subcommands `manifest`, `lock`, `verify`, `apply` and `rebase-check`. `tools/patchset/demo.sh` copies the pristine reference trees into the gitignored `tools/patchset/.work/` and runs six scenarios. Example series:

- `examples/patches/wordpress/7.1.5/0001-add-object-id-helper.patch` adds `wp-includes/pressgres-object-id.php` (placeholder `pressgres_object_id()`) and loads it in `wp-settings.php` before `post.php` (upstream `src/wp-settings.php:220`).
- `examples/patches/wordpress/7.1.5/0002-post-ids-use-object-id-helper.patch` replaces `absint( $post_id )` in `get_post_custom()` and `is_sticky()` (upstream `src/wp-includes/post.php:2849` and `:2920`).
- `examples/patches/gutenberg/89408c2/0001-format-library-image-id-as-string.patch` replaces `parseInt( id, 10 )` in `packages/format-library/src/image/index.js:41` with a string-preserving return. This is Gutenberg **source**. The dist rebuild is not run (no network for `npm ci`).

All patches are illustrative. The helper falls back to `absint()` for non-UUID input only so that the demo stays syntactically meaningful. That fallback is not a design proposal (ADR-002 governs IDs).

**Fail-loud guarantees** (see `tools/patchset/README.md`): upstream tree digest and file count, per-patch SHA-256, per-file pre-image git blob id, no fuzz, offset or whitespace fix-up from `git apply -v`, per-file post-image blob id, and the patched-tree digest. `git apply` never fuzzes without `-C`, but it *silently* accepts offsets. The tool parses `git apply -v` output and rejects `offset`. This was verified in scenario 5b, where git reported `Hunk #1 succeeded at 2849 (offset 3 lines)`.

**Results** (command: `tools/patchset/demo.sh`, run on macOS with git 2.54.0 and PHP 8.4.27, about 31 s wall time including the relock run):

| # | Scenario | Expected | Result |
|---|---|---|---|
| 1 | apply WP series to pristine 7.1.5 | exit 0, patched digest matches lock | pass: `ab1d48c9…` |
| 1b/1c | `php -l` on patched files; helper smoke test | no syntax errors | pass |
| 2 | apply Gutenberg series to pristine 89408c2 | exit 0 | pass: `146fb1fb…` |
| 3 | one byte appended to untouched `wp-includes/formatting.php` | rejected before patching | pass (exit 1) |
| 4 | one character changed in patch 0002 | series hash mismatch | pass (exit 1) |
| 5a/5b | 3 lines added at top of `post.php` | strict apply refuses; rebase-check `REFRESH (offset)` | pass (exit 1, exit 3) |
| 6 | upstream changed `is_sticky()` cast line | rebase-check `CONFLICT`, rejected hunk printed | pass (exit 3) |

An earlier run, before scenario 5 was revised, inserted the 3 lines directly above `function get_post_custom(`. That produced `CONFLICT`, not `REFRESH`, because the docblock's closing `*/` line is hunk context. The scenario was then moved to the top of the file to show a true offset. Both behaviours are what the design intends.

<details>
<summary>Captured output: <code>tools/patchset/demo-output.txt</code> (full; tabs expanded to 4 spaces)</summary>

```text
R-005 patchset demo  (git: 2.54.0, host: Darwin)

### 1. apply WordPress series to pristine 7.1.5 src/
$ tools/patchset/bin/patchset apply .work/wp-7.1.5 tools/patchset/examples/patches/wordpress/7.1.5
== verify 7.1.5 against .work/wp-7.1.5
  upstream tree ok    sha256=9b52b38a786cea2d5463655f3b5c8385029dab2ad57da2d120e6867ee401ae7b files=3798
  series hash ok      0001-add-object-id-helper.patch
  series hash ok      0002-post-ids-use-object-id-helper.patch
== apply (strict: no fuzz, no offset, exact pre/post images)
  applied             0001-add-object-id-helper.patch
  applied             0002-post-ids-use-object-id-helper.patch
  patched tree ok     sha256=ab1d48c96c837290aae1d657df19a139dc1e7fa95f71553a21cd410eab159a81 (matches upstream.lock)
RESULT: OK
--> exit 0 (expected)

### 1b. php -l on patched files
$ sh -c cd '.work/wp-7.1.5' && for f in wp-settings.php wp-includes/post.php wp-includes/pressgres-object-id.php; do php -l $f; done
No syntax errors detected in wp-settings.php
No syntax errors detected in wp-includes/post.php
No syntax errors detected in wp-includes/pressgres-object-id.php
--> exit 0 (expected)

### 1c. helper smoke test (absint stubbed; illustrative)
$ php -r function absint($v){return abs((int)$v);} require '.work/wp-7.1.5/wp-includes/pressgres-object-id.php'; var_dump(pressgres_object_id('0190F3A2-7B1C-7DEF-8ABC-0123456789AB'), pressgres_object_id('42'));
string(36) "0190f3a2-7b1c-7def-8abc-0123456789ab"
int(42)
--> exit 0 (expected)

### 1d. generated modification notice
$ cat .work/wp-7.1.5/PRESSGRES-MODIFICATIONS.txt
This is a MODIFIED version of wordpress-develop 7.1.5.
It was changed by the Pressgres project. Each patch below lists the files it
changed and the date of the change. Complete patch sources: patches/ in the
Pressgres source distribution. License: GPL-2.0-or-later (see license.txt).

0001-add-object-id-helper.patch  [PG-WP-0001]  date=2026-11-22
    wp-includes/pressgres-object-id.php
    wp-settings.php
0002-post-ids-use-object-id-helper.patch  [PG-WP-0002]  date=2026-11-22
    wp-includes/post.php
--> exit 0 (expected)

### 2. apply Gutenberg series to pristine 89408c2 source
$ tools/patchset/bin/patchset apply .work/gutenberg-89408c2 tools/patchset/examples/patches/gutenberg/89408c2
== verify 89408c2 against .work/gutenberg-89408c2
  upstream tree ok    sha256=b2cc1ed038ae7a850a26669aa3f503ab468e60daaadddd757e0e488190eb3257 files=12296
  series hash ok      0001-format-library-image-id-as-string.patch
== apply (strict: no fuzz, no offset, exact pre/post images)
  applied             0001-format-library-image-id-as-string.patch
  patched tree ok     sha256=146fb1fbc28f2f2898bece886351287f5b93f0bc958f63a4338f81e3317d9e8e (matches upstream.lock)
RESULT: OK
--> exit 0 (expected)

### 3. tampered upstream tree is rejected before any patch is applied
$ tools/patchset/bin/patchset apply .work/wp-tampered tools/patchset/examples/patches/wordpress/7.1.5
== verify 7.1.5 against .work/wp-tampered
  upstream tree MISMATCH
    expected 9b52b38a786cea2d5463655f3b5c8385029dab2ad57da2d120e6867ee401ae7b (3798 files)
    actual   0750541252218ab58c94fd5fa34812fec902fdd3b512e2897af01c72a1e6ced9 (3798 files)
FATAL: upstream tree is not the pinned pristine wordpress-develop 7.1.5
--> exit 1 (expected)

### 4. tampered patch file is rejected by the series hash manifest
$ tools/patchset/bin/patchset apply .work/wp-7.1.5-b .work/series-tampered
== verify series-tampered against .work/wp-7.1.5-b
  upstream tree ok    sha256=9b52b38a786cea2d5463655f3b5c8385029dab2ad57da2d120e6867ee401ae7b files=3798
  series hash ok      0001-add-object-id-helper.patch
  series hash MISMATCH 0002-post-ids-use-object-id-helper.patch
    expected a9ecc3c79d6181339ef385134eb38b81e3f2ba810a68d759fbfa3452cefbbccb
    actual   cbb68b9b1139bb93f3c205e4a1385179cb6bb5f4eefe4fe09346e4a19a36128a
FATAL: patch series does not match its hash manifest
--> exit 1 (expected)

### 5a. strict apply refuses a drifted tree (offset-only drift)
$ tools/patchset/bin/patchset apply .work/wp-next-offset tools/patchset/examples/patches/wordpress/7.1.5
== verify 7.1.5 against .work/wp-next-offset
  upstream tree MISMATCH
    expected 9b52b38a786cea2d5463655f3b5c8385029dab2ad57da2d120e6867ee401ae7b (3798 files)
    actual   7d68257408abf93749f836dd0b093b9800858aa1c2ecd40366714ade949021dd (3798 files)
FATAL: upstream tree is not the pinned pristine wordpress-develop 7.1.5
--> exit 1 (expected)

### 5b. rebase-check dry run (offset-only drift)
$ tools/patchset/bin/patchset rebase-check .work/wp-next-offset tools/patchset/examples/patches/wordpress/7.1.5
== rebase-check 7.1.5 against .work/wp-next-offset (dry run; target is not modified)
  series hash ok      0001-add-object-id-helper.patch
  series hash ok      0002-post-ids-use-object-id-helper.patch
  target differs from pinned upstream: classifying each patch
  0001-add-object-id-helper.patch: CLEAN (exact pre-image)
  0002-post-ids-use-object-id-helper.patch: REFRESH (applies only with offset; regenerate patch)
      pre-image MISMATCH wp-includes/post.php (expected blob aa6e4f9999ae, found e8ca3471f63d)
      git: Hunk #1 succeeded at 2849 (offset 3 lines).
      git: Hunk #2 succeeded at 2920 (offset 3 lines).
RESULT: 1 patch(es) need maintainer action
--> exit 3 (expected)

### 6. rebase-check dry run (conflicting upstream change)
$ tools/patchset/bin/patchset rebase-check .work/wp-next-conflict tools/patchset/examples/patches/wordpress/7.1.5
== rebase-check 7.1.5 against .work/wp-next-conflict (dry run; target is not modified)
  series hash ok      0001-add-object-id-helper.patch
  series hash ok      0002-post-ids-use-object-id-helper.patch
  target differs from pinned upstream: classifying each patch
  0001-add-object-id-helper.patch: CLEAN (exact pre-image)
  0002-post-ids-use-object-id-helper.patch: CONFLICT (hunk context changed; manual rebase required)
      pre-image MISMATCH wp-includes/post.php (expected blob aa6e4f9999ae, found 7abe0725ec49)
      git: Checking patch wp-includes/post.php...
      git: error: while searching for:
      git:  * @return bool Whether post is sticky.
      git:  */
      git: function is_sticky( $post_id = 0 ) {
      git:  $post_id = absint( $post_id );
      git: 
      git:  if ( ! $post_id ) {
      git:      $post_id = get_the_ID();
      git: 
      git: error: patch failed: wp-includes/post.php:2917
      git: error: wp-includes/post.php: patch does not apply
    rejected hunks:
      diff a/wp-includes/post.php b/wp-includes/post.php    (rejected hunks)
      @@ -2917,7 +2917,7 @@ function get_post_custom_values( $key = '', $post_id = 0 ) {
        * @return bool Whether post is sticky.
        */
       function is_sticky( $post_id = 0 ) {
      - $post_id = absint( $post_id );
      + $post_id = pressgres_object_id( $post_id ); // Pressgres: modified 2026-11-22.
       
        if ( ! $post_id ) {
            $post_id = get_the_ID();
RESULT: 1 patch(es) need maintainer action
--> exit 3 (expected)

DEMO RESULT: all scenarios behaved as expected
```

</details>

## 3. GPL and redistribution obligations (research, not legal advice)

### 3.1 What triggers obligations

- WordPress is "GPLv2 (or later)" and "Derivatives of WordPress code inherit the GPL license" (<https://wordpress.org/about/license/>; `src/license.txt:1-17`).
- Obligations attach to **distribution**: "The GPL permits anyone to make a modified version and use it without ever distributing it to others" (<https://www.gnu.org/licenses/gpl-faq.html#UnreleasedMods>). The GPL "does not require you to release your modified version" (<https://www.gnu.org/licenses/gpl-faq.html#GPLRequireSourcePostedPublic>). Distribution to customers, including handing a container image or installer download to another legal entity, counts as distribution. Hosting it for them as a service does not, under GPLv2. The AGPL differs (<https://www.gnu.org/licenses/gpl-faq.html#UnreleasedModsAGPL>), and no AGPL component was found in core in this spike; see the open questions.

### 3.2 Obligations when Pressgres distributes patched WordPress

| Obligation | Source | Pressgres implementation |
|---|---|---|
| Keep copyright, license and no-warranty notices intact; ship the license | GPLv2 §1, `src/license.txt:117-123` | never patch `license.txt` or file headers away; strict apply plus post-image checks guarantee untouched files are byte-identical |
| **Prominent notices on modified files stating the change and its date** | GPLv2 §2(a), `src/license.txt:133-134` | (1) an inline marker comment at each change (`// Pressgres: modified 2026-11-22.` in the demo patches); (2) a generated `PRESSGRES-MODIFICATIONS.txt` listing every modified file and its patch date (demo scenario 1d); (3) patch headers carry `Date:`. **Whether (1)+(2) is sufficient is a question for counsel.** |
| License the whole as GPL at no charge to third parties | GPLv2 §2(b), `src/license.txt:136-139` | Repo is already GPL-2.0-or-later ([README](../../README.md#license)); patches are licensed `GPL-2.0-or-later` (header field). Pressgres-only components loaded into WordPress (db.php, mu-plugins) are treated as derivative works per <https://wordpress.org/about/license/> |
| Interactive-program announcement | GPLv2 §2(c), `src/license.txt:141-150` | WordPress does not normally print such an announcement; the exception in the same clause appears to apply. Confirm with counsel. |
| Complete corresponding source, including build/install scripts, for non-source forms (minified JS, built bundles, container images) | GPLv2 §3, `src/license.txt:172-197` | Accompany every artifact with, or point to (<https://www.gnu.org/licenses/gpl-faq.html#SourceAndBinaryOnDifferentSites>: "clear instructions"), the upstream reference (wordpress-develop tag + Gutenberg SHA), both patch series, `upstream.lock`, and the build scripts (`Gruntfile.js`, Gutenberg build config, Pressgres build). Prefer §3(a) (source alongside) over a 3-year written offer (§3(b), `src/license.txt:180-185`). |
| Patches themselves | Patches are modifications of GPL code; distributing them is distributing part of a work based on the Program | License patches GPL-2.0-or-later. Contributions are accepted under the same terms ([README](../../README.md#license)); consider a DCO sign-off so provenance is recorded. |

**Built JS.** The `wp-includes/js/dist` bundles are produced by a build. If Pressgres changed them, the "preferred form for making modifications" is the Gutenberg source plus Pressgres patches, not the minified output (`src/license.txt:193-197`; FAQ: corresponding source is "the source that the binaries were made from", <https://www.gnu.org/licenses/gpl-faq.html#MustSourceBuildToMatchExactHashOfBinary>). This is a second, legal reason to patch Gutenberg source and rebuild.

### 3.3 Bundled third-party components (verified in-file headers; not exhaustive)

| Component | License as stated | Evidence |
|---|---|---|
| WordPress core / b2 | GPLv2 or later; b2 "released under the GPL" | `src/license.txt:1-40` |
| Gutenberg | Project license GPL-2.0-or-later; contributions on or after 2021-04-15 dual GPL-2.0-or-later **and** MPL-2.0; earlier code being relicensed | `gutenberg-89408c2/LICENSE.md:5-21`, `:42-60`; `package.json:7` |
| PHPMailer | LGPL-2.1 | `src/wp-includes/PHPMailer/PHPMailer.php:16` |
| SimplePie | BSD-3-Clause | `src/wp-includes/SimplePie/src/SimplePie.php:3-4` |
| getID3 | multiple (GPL v1/v2/v3, LGPLv3, MPL-2.0) at licensee's choice | `src/wp-includes/ID3/license.txt:11-21` |
| sodium_compat | ISC | `src/wp-includes/sodium_compat/LICENSE:1-4` |
| Text_Diff (Horde) | LGPL | `src/wp-includes/Text/Diff.php:9-13` |
| PclZip | LGPL | `src/wp-admin/includes/class-pclzip.php:5` |
| Snoopy | LGPL 2.1 or later | `src/wp-includes/class-snoopy.php:18-19` |
| POP3 class | GPL | `src/wp-includes/class-pop3.php:5-13` |
| phpass | public domain | `src/wp-includes/class-phpass.php:16-32` |
| AVIF info | BSD-2-Clause + AOM Patent License 1.0 | `src/wp-includes/class-avif-info.php:3-6` |
| Services_JSON | BSD-style | `src/wp-includes/class-json.php:29-33` |
| TinyMCE (vendored) | LGPL (license file) | `src/js/_enqueues/vendor/tinymce/license.txt:1` |
| Plupload / mOxie | "Released under GPL License" | `src/js/_enqueues/vendor/plupload/plupload.js:6`, `moxie.js:7` |
| MediaElement.js | MIT | `src/js/_enqueues/vendor/mediaelement/mediaelement.js:9` |
| twemoji, zxcvbn | MIT | `src/js/_enqueues/vendor/twemoji.js:3`; `zxcvbn.min.js:4` |
| npm runtime deps (jQuery, Backbone, Underscore, React, lodash, moment, CodeMirror, …) | not verified per package in this spike | `wordpress-develop-7.1.5/package.json:85-115`; copied into `js/dist/vendor` by `Gruntfile.js:412-493` |
| Gutenberg npm dependency tree in built JS | Gutenberg CI enforces an allow-list via `wp-scripts check-licenses`; GPL-2-compatible list includes MIT, BSD, ISC, LGPL-2.1, MPL-2.0, Apache-2.0 WITH LLVM-exception…; Apache-2.0 and others are allowed only when not distributed | `gutenberg-89408c2/packages/scripts/utils/license.js:57-82`, `:90-97`; `gutenberg-89408c2/.github/workflows/static-checks.yml:120` |

Notes:

- **MPL-2.0** code can be combined into a GPL "Larger Work" under MPL §3.3 unless it carries the Exhibit B "Incompatible With Secondary Licenses" notice. Code shipped only with the MPL text is "not considered Incompatible with Secondary Licenses" (<https://www.mozilla.org/en-US/MPL/2.0/FAQ/>, Q14 and Q25). The Pressgres license check must fail on any Exhibit B notice.
- **LGPL-2.1** components can be combined with GPL-2.0-or-later code. LGPL-2.1 §3 lets a licensee "opt to apply the terms of the ordinary GNU General Public License" (`src/js/_enqueues/vendor/tinymce/license.txt:211`). Keep their notices; do not relicense them in place.
- **Action:** run `wp-scripts check-licenses --prod --gpl2` (`gutenberg-89408c2/packages/scripts/scripts/check-licenses.js:20-22`) on the patched Gutenberg build, and generate an SPDX/CycloneDX SBOM for both trees per release ([14 — Open decisions](../14-open-decisions.md) item 16).

### 3.4 Trademark constraints on naming a modified distribution

From the WordPress Foundation trademark policy (<https://wordpressfoundation.org/trademark-policy/>; no last-updated date on the page):

- Permission is required to use the WordPress name or logo "as part of any project". Non-licensed businesses "cannot use them as part of a product, project, service, domain name, or company name". Commercial licensing goes through Automattic ("they have the exclusive license").
- Domains: "Under no circumstances is it permitted to use WordPress or WordCamp as part of a domain name or top-level domain name."
- "WP": "Please do not use 'WP' in any way that confuses people." The page cites WP Engine as an example of confusion. The page does not say whether "WP" alone is a mark; "WP-CLI" is listed as a word mark.
- Allowed: referring to WordPress to explain services. The page's examples include "Hosting for WordPress" in place of "Managed WordPress Hosting".

Implications for Pressgres (to confirm with counsel; R-015/ADR-007):

- Never call the patched build "WordPress", "WordPress for PostgreSQL", or similar. Use factual, nominative wording such as "Pressgres, a PostgreSQL distribution based on WordPress® 7.1.5 (modified)", with a non-affiliation statement.
- Domains must not contain "wordpress". Avoid "WP" in the product or domain name where it could imply affiliation. The candidate "WPPostgres" ([17 — Names](../17-names.md)) is high risk. The CLI name `wps` should be checked too.
- Change user-visible branding in the patched admin only as far as the GPL allows and the trademark policy requires. Removing marks is not restricted by the GPL, but notices must stay intact. Whether patched admin screens that keep the WordPress logo imply endorsement is a question for counsel.

## 4. Recommendation for ADR-001

Adopt a **hybrid managed patchset**. Maintainers rebase in per-release branches of git forks of wordpress-develop and Gutenberg. Pressgres **ships** two version-pinned series of `git diff --full-index` patches with DEP-3-style headers: `patches/wordpress/<version>/` and `patches/gutenberg/<sha>/`. Each series has a SHA-256 `series` manifest and an `upstream.lock` pinning the upstream and patched-tree digests, and both files are signed. Release CI applies the series strictly to checksum-verified pristine upstream: no fuzz, no offset, exact pre- and post-images, reproducible output. Editor JS and block PHP are patched only in Gutenberg source and rebuilt into a Pressgres-owned, SHA-256-pinned artifact; built `js/dist` is never hand-edited. AST codemods may find and draft changes but never run at build time. Every upstream tag triggers an automated `rebase-check`, and a documented hotfix path backs a proposed 24 h/72 h security SLA. Each release publishes a source bundle (upstream refs, both series, build scripts), generated modification notices and an SBOM. The product is never named "WordPress". Draft: [ADR-0001](../adr/0001-wordpress-change-strategy.md) (Proposed).

## Implications for the UUID patchset (patch strategy per category)

| Category | Where it lives | Strategy |
|---|---|---|
| Core PHP ID casts and type declarations (`absint`, `(int)`, `intval`, `int` params) | wordpress-develop `src/` | WordPress series in `patches/wordpress/<version>/`; AST tooling finds sites and generates candidates; reviewed text patches ship |
| Block render PHP (`wp-includes/blocks/*.php`), `wp-includes/build/*.php` | **Gutenberg** source (`packages/block-library/src/*/index.php` etc.) | Gutenberg series; never patch the core copy |
| Block-editor / data / core-data JS (`parseInt`, numeric ID assumptions) | Gutenberg `packages/*/src` | Gutenberg series + rebuild → Pressgres-owned artifact (SHA-256, signed); `package.json` `gutenberg.sha`/`ghcrRepo` point to it |
| Legacy non-Gutenberg admin JS (`src/js/_enqueues/**`) | wordpress-develop `src/js` | WordPress series; rebuilt by `grunt build` |
| REST schemas (`'type' => 'integer'` for IDs) | wordpress-develop PHP | WordPress series |
| New Pressgres helpers | new files added by patch (as demo 0001) or a Pressgres mu-plugin | Prefer mu-plugin/drop-in when no core load-order requirement; otherwise a patch adding the file |
| SQL generation | `$wpdb` facade drop-in | not a patch (ADR-003) |

## Open questions

1. **Counsel:** are inline `// Pressgres: modified <date>` markers plus a top-level `PRESSGRES-MODIFICATIONS.txt` sufficient "prominent notices … and the date of any change" under GPLv2 §2(a)? Or must each modified file's header be changed?
2. **Counsel:** for container images and installer downloads, is a source tarball (pristine upstream reference + patches + build scripts) published next to each release sufficient under §3(a)? Does pointing to upstream wordpress.org/GitHub for unmodified parts suffice, or must Pressgres host all source itself?
3. **Counsel:** do Pressgres-only PHP components (db.php drop-in, SQL parser reuse) need any additional notices? Does the GPL obligation reach the separately distributed `wps` CLI, which is not loaded into WordPress? This is "mere aggregation" (`src/license.txt:167-170`) versus a derivative work.
4. **Counsel:** trademark: can the product say "based on WordPress" or "for WordPress" in its name or tagline, and may patched admin screens keep WordPress logos? Is a license from Automattic or the Foundation needed for any planned use? Is "WP" in the CLI name `wps` a risk?
5. **Counsel:** Gutenberg's pre-2021 code relicensing status (`LICENSE.md:42-60` says "in the process"). Is it irrelevant for a GPL-only distribution, as assumed here?
6. **Counsel:** do any bundled components carry patent clauses or attribution terms (AOM Patent License for AVIF info, `class-avif-info.php:5-6`) that need NOTICE handling?
7. Engineering: the full SPDX license inventory of the 7.1.5 release archive and of the patched Gutenberg build was not produced. Run the license checker and SBOM tooling in U-005.
8. Engineering: rebuilding Gutenberg reproducibly (bit-identical `js/dist`) has not been verified. If builds are not reproducible, pin and sign the Pressgres artifact by SHA-256 rather than expecting rebuild equality.
9. Engineering: how Pressgres prevents WordPress core auto-updates and the dashboard updater from overwriting patched core. This needs a separate spike (open decision 14).
10. Engineering: patch count and per-release rebase cost are unknown until R-001/R-013. The SLA targets above depend on them.

## Method / reproduction

- Read: `AGENTS.md`, `README.md`, `docs/02`, `docs/07`, `docs/09`, `docs/11`, `docs/14`, `docs/adr/0000-template.md`.
- Upstream build facts: `grep -n` over `wordpress-develop-7.1.5/{package.json,.gitignore,Gruntfile.js,tools/gutenberg/*.js}` and `gutenberg-89408c2/{.github/workflows/build-plugin-zip.yml,bin/build-plugin-zip.sh,LICENSE.md,packages/scripts/**}`. Line numbers are cited inline.
- Block PHP counts: `ls src/wp-includes/blocks/*.php | wc -l` → 92; `grep -ln "absint\|(int)" src/wp-includes/blocks/*.php | wc -l` → 25 (heuristic; any `(int)` matches, confidence **low** for ID relevance, not sampled).
- License headers: `grep -n -i -m3 "license\|copyright"` on each listed file.
- Demo: `tools/patchset/demo.sh` (first run with `RELOCK=1` to pin digests, then a plain run captured to `tools/patchset/demo-output.txt`). Example patches were authored in a scratch git repo with `git diff --full-index`.
- Web sources (fetched 2026-11-22): <https://wordpressfoundation.org/trademark-policy/>, <https://wordpress.org/about/license/>, <https://wordpress.org/about/security/>, <https://make.wordpress.org/core/handbook/best-practices/backporting-commits/>, <https://make.wordpress.org/core/2026/03/25/wordpress-6-9-2-retrospective/>, <https://wordpress.org/download/releases/>, <https://api.wordpress.org/core/checksums/1.0/?version=7.1.5&locale=en_US>, <https://www.gnu.org/licenses/gpl-faq.html>, <https://www.mozilla.org/en-US/MPL/2.0/FAQ/>. The GPLv2 text was read from the bundled `src/license.txt` rather than fetched.
- Not done: npm builds, network downloads of upstream archives, signing, SBOM generation.
