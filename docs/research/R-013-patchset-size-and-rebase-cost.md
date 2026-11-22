# R-013 · Core UUID patchset size and release rebase cost

The expected single-site patchset changes **1,925 existing source lines across 284 upstream files**, plus **330 lines of PHP and JS helpers** and **190 lines of native schema**. The projected patch has **1,422 hunks**, including new files. For one supported release series, budget **5 / 11 / 20 engineer-days per feature release (the task's minor release)** and **1 / 2 / 4.5 per security release**. The estimate combines static source review and historical Git diffs. Implementation and rebase timings remain unmeasured. [Size data](data/R-013-size.csv) · [Effort data](data/R-013-effort.csv)

The baseline is WordPress develop 7.1.5 (`984163c92ef66b6186538ecf01bacb97fc097541`, schema revision 61833) and Gutenberg `89408c2b9bd944575dfa9039bc6870da1c8f56cb`. Assume proposed PHP 8.4 and PostgreSQL 18+, one native UUIDv7 per entity, canonical UUID strings at PHP and REST boundaries, a single-site managed build and two version-pinned patch series. The model covers runtime PHP, classic admin JS leads, Gutenberg sources and block metadata, REST, current install/seed/upgrade entry points, and schema integration. It excludes multisite, historical MySQL upgrade routines, bulk content migration, plugin adapters, generated build artifacts, tests from source-size counts, and the broader SQL translator and runtime implementation. Truncation, confusion between ID and absence, and damaged permission checks are the priority failure modes. `wordpress-develop-7.1.5/src/wp-includes/version.php:19` · `wordpress-develop-7.1.5/src/wp-includes/version.php:26` · `wordpress-develop-7.1.5/package.json:10` · [Data model](../04-data-model.md) · [Roadmap](../08-roadmap.md) · [R-005 proposed ADR](../adr/0001-wordpress-change-strategy.md)

## Ambiguous PHP triage

The R-001 CSV has 1,847 ambiguous **rows**, drawn from 5,741 total rows. A simple random sample of 80 without replacement used Python seed **13013** and the original CSV order. The sample records the original row, local source citation, classification, confidence and reason. For mixed functions, the classification refers to the matched operation. A permission expression that forwards an ID unchanged goes to boundary review, while a numeric gate or cast at the sampled line qualifies as a likely edit. [R-001 report](R-001-php-integer-id-audit.md) · [R-001 inventory](data/R-001-php-id-hits.csv) · [Reviewed sample](data/R-013-ambiguous-sample.csv)

| Source-reviewed classification | Rows | Example |
| --- | ---: | --- |
| Likely direct edit | 20 | The user sanitizer recasts the declared `ID` field. `wordpress-develop-7.1.5/src/wp-includes/user.php:1899` and `:1994`. |
| Identity-related boundary review | 26 | The emptiness guard accepts an array of UUIDs. The subsequent SQL builds a comma-separated list. `wordpress-develop-7.1.5/src/wp-includes/post.php:8506` and `:8507`. |
| Historical migration outside scope | 1 | The term-taxonomy insert result is cast in `upgrade_230()`. `wordpress-develop-7.1.5/src/wp-admin/includes/upgrade.php:1463`. |
| Unrelated operation | 33 | The regex-match key being tested is a position or capture name. `wordpress-develop-7.1.5/src/wp-includes/rest-api/class-wp-rest-server.php:1181`. |

- **Direct-edit yield is 25.0%** with an approximate **95% Wilson interval of 16.8–35.5%**, or **310–655 rows** across the ambiguous frame (point estimate 462). The observed false-positive rate for treating all ambiguous hits as direct edits is **75.0%**. The broader identity-review yield, including the historical hit, is **58.8%** (95% Wilson **47.8–68.9%**, about **883–1,273 rows**). The intervals describe row sampling only. They give no recall estimate and omit classifier judgment and within-line duplication. [Sample](data/R-013-ambiguous-sample.csv)
- **Confidence is high** for direct source evidence in the reviewed PHP rows and **medium** for the extrapolation to patch locations. The sample covers the ambiguous frame. R-001's separate 64 identity hits in its equal-by-kind review all matched their classified identity, but that exercise checked identity relevance. For patch sizing, the 3,103 classified identity rows include already string-capable operations and duplicate line locations. R-012's independent 40-hit review found 18 numeric assumptions, 7 boundary checks and 15 incidental matches. Its medium/low review pool had a **55%** false-positive rate when read as a list of numeric assumptions. [R-001 manual validation](R-001-php-integer-id-audit.md#manual-validation) · [R-012 method](R-012-editor-rest-id-audit.md#methodreproduction)

## Patch size model

Counts use distinct `(source repository, file, 1-based line)` coordinates. The upstream sizes count existing edit anchors, with one line per named or extrapolated site. Structural rewrites may replace larger spans. A hunk groups sites in the same file up to seven lines apart, the envelope for a unified diff with three context lines. Hunk totals assume neighboring edits can ship together. Several patches in a series can split that envelope. Files and hunks count new helper/schema files once each. Confidence is **medium** for the low and expected sizing model and **low** for the high scenario. [Named expected sites](data/R-013-sites-expected.csv) · [Size calculations](data/R-013-size.csv)

| Existing named sites before the residual ambiguous allowance | Low | Expected | High | Source example |
| --- | ---: | ---: | ---: | --- |
| Core PHP | 878 | 1,078 | 1,931 | `wordpress-develop-7.1.5/src/wp-includes/class-wp-query.php:2256` |
| REST PHP and callers | 224 | 272 | 391 | `wordpress-develop-7.1.5/src/wp-includes/rest-api/endpoints/class-wp-rest-posts-controller.php:114` |
| Classic admin JS | 2 | 3 | 3 | `wordpress-develop-7.1.5/src/js/_enqueues/vendor/plupload/handlers.js:479` |
| Gutenberg JS/TS | 16 | 102 | 447 | `gutenberg-89408c2/packages/core-data/src/resolvers.js:859` |
| Gutenberg render PHP | 7 | 11 | 68 | `gutenberg-89408c2/packages/block-library/src/video/index.php:28` |
| Block metadata | 20 | 20 | 20 | `gutenberg-89408c2/packages/block-library/src/navigation/block.json:25` |
| Install, seed and managed upgrade | 38 | 38 | 41 | `wordpress-develop-7.1.5/src/wp-admin/includes/upgrade.php:186` and `:676` |
| Schema integration and build pin | 3 | 3 | 3 | `wordpress-develop-7.1.5/src/wp-admin/includes/schema.php:36` · `wordpress-develop-7.1.5/package.json:10` |
| **Total** | **1,188** | **1,527** | **2,904** | [Low sites](data/R-013-sites-low.csv) · [Expected sites](data/R-013-sites-expected.csv) · [High sites](data/R-013-sites-high.csv) |

- **Low** admits high-confidence PHP numeric behavior, explicit integer/absence semantics, direct REST breakage, reviewed Gutenberg edits and two classic upload parsers. It assumes XML-RPC and deprecated-file entry points can be kept outside the profile. **Expected** includes medium-confidence PHP coercions and validators, stronger REST-link and Gutenberg lexical candidates, and XML-RPC/deprecated paths while their reachability is unresolved. **High** prices more query-var and sentinel changes, explicit handling of implicit binds, and the broad R-012 JS review queue. It is a scoping stress case that includes likely false positives. Block metadata counts include ID-bearing composite contracts as well as direct numeric fields. [R-001 inventory](data/R-001-php-id-hits.csv) · [R-012 REST CSV](data/R-012-rest-hits.csv) · [R-012 Gutenberg CSV](data/R-012-js-hits.csv)
- The managed schema owns DDL, the drop-in owns generated IDs and table-aware implicit binds, and the upstream patch owns typed callers, binding sites that destroy identity before translation, and install/upgrade handoffs. The model counts R-002 seed and upgrade anchors and excludes the stock DDL body from edited lines. Existing WordPress render-PHP lines owned by Gutenberg are matched to identical lines in the corresponding Gutenberg block source before deduplication. All selected render lines mapped in this run. `wordpress-develop-7.1.5/src/wp-admin/includes/upgrade.php:63` · `wordpress-develop-7.1.5/src/wp-admin/includes/schema.php:56` · `wordpress-develop-7.1.5/src/wp-includes/load.php:746` · `wordpress-develop-7.1.5/tools/gutenberg/copy.js:296` · [R-002 report](R-002-schema-and-sql-paths.md) · [R-002 schema CSV](data/R-002-columns.csv) · [R-002 DDL/DML CSV](data/R-002-ddl-paths.csv)
- Deduplication against the respective baseline leaves **17 / 18 / 18** novel, directly reviewed sample sites. For each scenario use the corresponding Wilson bound or midpoint evaluated on its novel count, multiply by 1,847 and subtract the sampled sites already counted. That yields **236 / 398 / 588** residual lines. The sample increases named files by **4 / 4 / 2** and hunks by **14 / 15 / 11**. Apply those observed deltas per novel site to the residual lines, then multiply by **0.25 / 0.50 / 0.75** for files (repeated edits in the same file) and **0.60 / 0.80 / 1.00** for hunks (shared helpers and nearby edits). Cap the file increment at as-yet-unrepresented eligible ambiguous PHP paths. These factors are planning assumptions. [Size calculations](data/R-013-size.csv)
- For example, expected files are `240 + round(398 × 4/18 × 0.50) = 284` and expected hunks are `1,153 + round(398 × 15/18 × 0.80) = 1,418`. Budget separate helper modules for typed parsing and lists, query/cache or REST boundary adapters, and editor key handling. The **180 / 330 / 560** helper lines are explicit budgets, split **120 / 220 / 380** PHP and **60 / 110 / 180** JS. For native schema, use **94 columns + 41 keys + 15 / 55 / 125** lines for framing, defaults, constraints and related migration declarations, or **150 / 190 / 260** lines. Budget **3 / 4 / 6** new files across helpers and schema, one hunk each. `wordpress-develop-7.1.5/src/wp-includes/functions.php:5065` · `wordpress-develop-7.1.5/src/wp-includes/rest-api.php:2349` · `gutenberg-89408c2/packages/core-data/src/resolvers.js:127` · `wordpress-develop-7.1.5/src/wp-admin/includes/schema.php:56` · [R-002 column inventory](data/R-002-columns.csv)

| Modeled total | Low | Expected | High |
| --- | ---: | ---: | ---: |
| Distinct existing source lines touched | 1,424 | 1,925 | 3,492 |
| Existing files touched | 181 | 284 | 533 |
| Existing-file hunks | 985 | 1,418 | 2,328 |
| New helper and native schema lines | 330 | 520 | 820 |
| Files including additions | 184 | 288 | 539 |
| Hunks including additions | 988 | 1,422 | 2,334 |

## Upstream churn

The fixed churn footprint uses **240 named files** and **1,153 named hunks** from the expected scenario, including source-reviewed ambiguous edits. It has **147 WordPress** paths and **93 Gutenberg** paths. Extrapolated edits have no coordinates and are excluded. Across three consecutive feature updates from the last shipped point release, **213 distinct paths** in that footprint changed at least once. Across all **16** latest-series point releases in the full interval, **66** changed at least once. The history covers **43 tags** from 6.8.0 through the UTC day of 7.1.5, including **39 point transitions**, of which **23** are backports on previously superseded series. [Named footprint](data/R-013-sites-expected.csv) · [Release pins](data/R-013-release-pins.csv) · [Per-file churn](data/R-013-churn-files.csv)

**Read each cell as files changed / lines added plus deleted / mapped hunks overlapping within three lines + uncertain-only hunks.** Projection uses old-side release coordinates. An uncertain-only hunk has a possible encounter in code edited or removed between the pinned reference and the older release. Treat both columns as review load. Git merge conflicts depend on the as-built patch and three-way merge. A changed file may still require strict patch refresh when its edited lines are distant. The CSV includes distances **0 / 3 / 10**, file-level evidence, missing older paths, and explicit security evidence. [Comparison data](data/R-013-churn.csv) · [R-005 rebase procedure](R-005-patch-mechanism-and-licensing.md#14-security-releases-and-a-proposed-sla-compatible-workflow) · [R-005 patchset demo](../../tools/patchset/README.md)

| Feature release pair | WordPress | Gutenberg | Gutenberg basis |
| --- | --- | --- | --- |
| 6.8.0 → 6.9.0 | 93 / 5,700 / 18+51 | 44 / 4,400 / 1+12 | Both package-version snapshots |
| 6.9.0 → 7.0.0 | 108 / 4,566 / 20+27 | 60 / 8,257 / 11+11 | Package-version snapshot → direct SHA |
| 7.0.0 → 7.1.0 | 79 / 5,851 / 30+39 | 65 / 7,581 / 7+10 | Both direct SHAs |
| 6.8.3 → 6.9.0 | 91 / 5,364 / 16+49 | 44 / 4,379 / 1+12 | Both package-version snapshots |
| 6.9.4 → 7.0.0 | 108 / 4,487 / 20+26 | 59 / 8,266 / 10+11 | Package-version snapshot → direct SHA |
| 7.0.4 → 7.1.0 | 79 / 5,708 / 30+36 | 63 / 7,550 / 6+10 | Both direct SHAs |

| Latest-series point release | WordPress | Gutenberg |
| --- | --- | --- |
| 6.8.0 → 6.8.1 | 5 / 105 / 0+0 | 1 / 37 / 0+0 |
| 6.8.1 → 6.8.2 | 7 / 264 / 0+0 | 1 / 2 / 0+0 |
| 6.8.2 → 6.8.3 | 6 / 125 / 2+2 | 0 / 0 / 0+0 |
| 6.9.0 → 6.9.1 | 6 / 279 / 0+0 | 2 / 15 / 1+0 |
| 6.9.1 → 6.9.2 (security) | 4 / 14 / 0+0 | 0 / 0 / 0+0 |
| 6.9.2 → 6.9.3 (security follow-up) | 1 / 2 / 0+0 | 0 / 0 / 0+0 |
| 6.9.3 → 6.9.4 | 2 / 10 / 0+1 | 0 / 0 / 0+0 |
| 7.0.0 → 7.0.1 | 8 / 96 / 1+0 | 5 / 31 / 1+0 |
| 7.0.1 → 7.0.2 | 4 / 32 / 1+1 | 0 / 0 / 0+0 |
| 7.0.2 → 7.0.3 | 5 / 47 / 1+2 | 0 / 0 / 0+0 |
| 7.0.3 → 7.0.4 | 1 / 2 / 0+0 | 0 / 0 / 0+0 |
| 7.1.0 → 7.1.1 | 13 / 559 / 4+5 | 2 / 224 / 0+0 |
| 7.1.1 → 7.1.2 | 1 / 2 / 0+0 | 0 / 0 / 0+0 |
| 7.1.2 → 7.1.3 | 5 / 214 / 0+1 | 0 / 0 / 0+0 |
| 7.1.3 → 7.1.4 | 8 / 50 / 2+0 | 1 / 6 / 0+0 |
| 7.1.4 → 7.1.5 (security) | 12 / 323 / 6+10 | 3 / 98 / 0+0 |
| **7.1.0 → 7.1.5 cumulative** | **28 / 1,132 / 10+14** | **6 / 328 / 0+0** |

- **Gutenberg history confidence.** WordPress 6.8 and 6.9 use individual `@wordpress/*` package declarations. Matching those version vectors against publish commits on Gutenberg's `wp/6.8` and `wp/6.9` branches recovers a likely source snapshot for each release. The launch snapshots match **74/74** and **77/77** declared versions, respectively. Every latest-series comparison matches the audited package versions declared directly by WordPress wherever a reconstructed snapshot is used. Three audited packages are absent from both launch manifests, so those packages have only snapshot provenance. Confidence is **medium** for these source diffs because a published dependency vector gives weaker provenance than a SHA. The **16** WordPress 7.x tags have direct pins, with **high** confidence in Git counts. Fourteen older-series Gutenberg pairs lack a match for at least one audited package version. They omit **43–67** affected paths per pair and use the CSV's measured denominator. `wordpress-develop-7.1.5/package.json:9` · [6.8.0 package declarations](https://github.com/WordPress/wordpress-develop/blob/6.8.0/package.json#L85) · [6.9.0 package declarations](https://github.com/WordPress/wordpress-develop/blob/6.9.0/package.json#L86) · [Release pins](data/R-013-release-pins.csv)
- **Feature releases.** The three shipped-base comparisons changed **135–167 of 240 paths** and **9,743–13,258 lines** in the audited footprint. They yield **17–36 mapped plus 37–61 uncertain-only** nearby hunks at N=3. At N=10 the mapped counts rise to **49–78**. The three Gutenberg diffs also introduce paths with **6 / 9 / 19** current-footprint hunks that have no old source path. At N=0 every feature pair has zero exact hits on lines still identical to the reference. Direct replacements of those lines can fall in the uncertain column after back-projection. Confidence is **medium** for context risk and **low** for actual merge conflicts. [Comparison data](data/R-013-churn.csv)
- **Point releases.** The latest-series steps changed **1–15** touched files and **2–783** lines. The largest N=3 proximity was 7.1.5 with **6 mapped plus 10 uncertain-only** hunks across both layers. Five mapped hunks are in `WP_Query`, where several ID list and SQL binding paths already need UUID work. A source diff can understate effort on a short notice release when CI, signing or behavior changes dominate. The security labels require explicit Git evidence or the R-005 retrospective. Other point tags include security-relevant commits with unconfirmed release classification. `wordpress-develop-7.1.5/src/wp-includes/class-wp-query.php:2256` · [7.1.5 security backport](https://github.com/WordPress/wordpress-develop/commit/be8f460792f434c7a3713950b857c6298c5e5565) · [R-005 retrospective citation](R-005-patch-mechanism-and-licensing.md#14-security-releases-and-a-proposed-sla-compatible-workflow) · [Per-file churn](data/R-013-churn-files.csv)

## Engineer time and R9

Assume one engineer-day is eight working hours and automated tests, builds, artifact signing and strict apply already exist. Fixed time covers upstream diff and series refresh, new ID-boundary review, fixture regression work and triage, the build, signing and release review. Use **3 / 5 / 8** fixed days for feature releases, **0.5 / 1.25 / 2** for routine points, and **1 / 1.5 / 2.5** for security. Each N=3 mapped overlap adds **0.5 / 1 / 1.5 hours** and each uncertain-only overlap adds **0.15 / 0.35 / 0.6 hours**, using the minimum, median and maximum counts from the relevant observations. For example, the expected feature rebase is `ceil(5 + (30 × 1 + 46 × 0.35) / 8) = 11` engineer-days. Runtime suite duration and parallel availability govern elapsed time. Confidence in the hours is **low** until rehearsed. [Effort worksheet](data/R-013-effort.csv) · [R-005 proposed release workflow](../adr/0001-wordpress-change-strategy.md)

| Estimated effort | Low | Expected | High |
| --- | ---: | ---: | ---: |
| Feature release rebase | 5 days | 11 days | 20 days |
| Routine point rebase | 0.5 days | 1.5 days | 4 days |
| Security release rebase | 1 day | 2 days | 4.5 days |
| Annual rebase work, one supported series | 28 days | 59 days | 118.5 days |
| Annual work including 25% reserve | 35 days | 74 days | 148 days |

The latest-series history has **three feature transitions and 13 point tags** in the year ending 2026-11-18. Three of those points have explicit security-chain evidence. The annual budget uses three feature rebases plus **all 13** points priced at the security rate to cover classification uncertainty and short notice. At **220 working days per FTE**, that is **0.13 / 0.27 / 0.54 FTE** before reserve. The expected allocation after reserve is about **0.34 FTE**, shared across maintainers. This covers the recurring release duty from R9. Initial implementation, wider compatibility work and support for additional WordPress series need separate budgets. [Effort worksheet](data/R-013-effort.csv) · [Release pins](data/R-013-release-pins.csv) · [R9](../11-tradeoffs-risks.md#risk-register)

## Summary of findings

- The likely direct-edit rate among ambiguous PHP hits is **20/80**, or **25%** (95% Wilson **16.8–35.5%**). After deduplication, the full scenarios span **1,424–3,492 existing lines**, **184–539 files including additions**, and **988–2,334 hunks including additions**. [Reviewed sample](data/R-013-ambiguous-sample.csv) · [Size worksheet](data/R-013-size.csv)
- Feature releases from the previous shipped point release change **135–167** of **240** named files. The 7.1.5 security release changes **15** and puts **16** named PHP hunks in the three-line mapped or uncertain review queue. The historical proxies put one active release series at an expected **59 engineer-days/year**, or **74** with reserve. [Comparison data](data/R-013-churn.csv) · [Effort worksheet](data/R-013-effort.csv)
- **R-007 go/no-go input.** Proceed with a managed single-series pilot if **three named, cross-trained maintainers** cover PHP/SQL, Gutenberg and release/QA, with a primary and backup on call and an independent reviewer available. Reserve roughly **0.34 FTE** across that group for recurrent rebase work, and rehearse both a feature transition (7.0.4 → 7.1.0) and a security transition (7.1.4 → 7.1.5) before committing to an SLA. If the team can provide only one maintainer or cannot demonstrate the gated security path, defer production support. Gate optional legacy surfaces first. The expected inventory has 95 named sites in three XML-RPC/deprecated files, spanning 83 clustered hunks. Consolidate typed helpers next so the behavior changes in fewer places. Upstream identifier-neutral seams with stock behavior preserved to reduce recurring patch ownership. These are planning conditions for R-007. `wordpress-develop-7.1.5/src/wp-includes/functions.php:5065` · `wordpress-develop-7.1.5/src/wp-includes/rest-api.php:2349` · [Expected sites](data/R-013-sites-expected.csv) · [Roadmap](../08-roadmap.md) · [R-005 release strategy](../adr/0001-wordpress-change-strategy.md)

## Implications for the UUID patchset

| Category | Proposed patch strategy and cost lever |
| --- | --- |
| PHP casts, lists, queries, IDs in options | Centralize canonical UUIDv7 validation and list handling and pass typed parameters. Keep policy local for root/absence, ordering, lookups by alternate key, write errors and authorization. R-001 records 20 non-network identity-classified `wp_parse_id_list` sites and 80 implicit binding sites before profile filtering. Audit helper distribution and opt-in upstream hooks for identity parsing and query typing. A shared parser cannot repair raw `IN` interpolation by itself. `wordpress-develop-7.1.5/src/wp-includes/functions.php:5065` · `wordpress-develop-7.1.5/src/wp-includes/class-wp-query.php:2256` · `wordpress-develop-7.1.5/src/wp-includes/class-wp-query.php:2419` · [R-001 hit inventory](data/R-001-php-id-hits.csv) |
| REST and permission boundaries | Patch shared matchers, argument schemas, validators and ID URL formatters. Keep resource lookup and permission decisions explicit. Propose upstream extension points that preserve stock default contracts. Route, coercion and authorization tests must cover the same UUID on both sides of the editor contract. `wordpress-develop-7.1.5/src/wp-includes/rest-api/endpoints/class-wp-rest-posts-controller.php:114` · `wordpress-develop-7.1.5/src/wp-includes/rest-api.php:2349` · `wordpress-develop-7.1.5/src/wp-includes/capabilities.php:179` |
| Gutenberg, classic JS and block.json | Amend and rebuild Gutenberg source with PHP renderers and matching metadata. Keep classic upload consumers in the WordPress series and retain full UUIDs in their headers and parsers. Gate optional features explicitly before excising their paths. `wordpress-develop-7.1.5/tools/gutenberg/copy.js:296` · `gutenberg-89408c2/packages/block-library/src/video/index.php:28` · `gutenberg-89408c2/packages/block-library/src/navigation/block.json:25` · `wordpress-develop-7.1.5/src/js/_enqueues/vendor/plupload/handlers.js:479` |
| Install, seed, native schema | Route managed DDL through versioned PostgreSQL migrations. Capture generated UUIDs at the actual inserts and use them for dependent seed rows. Gate historic upgrade entry points and keep the remaining SQL and schema behavior in the approved drop-in and migration interfaces. `wordpress-develop-7.1.5/src/wp-admin/includes/upgrade.php:186` · `wordpress-develop-7.1.5/src/wp-admin/includes/upgrade.php:268` · `wordpress-develop-7.1.5/src/wp-admin/includes/upgrade.php:676` · [R-002 schema paths](R-002-schema-and-sql-paths.md) |
| Release engineering | Maintain reviewed WordPress and Gutenberg branches, ship signed, strictly applied patches and rehearse the hotfix and full rebase. Gate on clean application and repeatable artifacts, an upstream PHPUnit baseline and UUID-specific disposable PostgreSQL/browser flows, including seed dependencies, capability checks, full UUIDs with shared prefixes, REST/editor round trips and upgrade/restore. [R-005 proposed ADR](../adr/0001-wordpress-change-strategy.md) · [R-012 acceptance proposal](R-012-editor-rest-id-audit.md#implications-for-the-uuid-patchset) · [Review gates](../10-ai-agents.md) |

## Open questions

- How many predicted sites disappear once boundaries have concrete helper contracts, and how many additional spans appear after scanning dynamic query arguments, PHPDoc, classic admin JS, or serialized references? The sample estimates positive yield within existing inventories. `wordpress-develop-7.1.5/src/wp-includes/class-wp-query.php:2422` · [R-001 limitations](R-001-php-integer-id-audit.md#methodreproduction)
- Which XML-RPC, classic admin, deprecated and feature-flagged editor flows can the first release safely gate? The expected scenario retains PHP legacy-file candidates while scope is open. `wordpress-develop-7.1.5/src/wp-includes/class-wp-xmlrpc-server.php:4524` · `gutenberg-89408c2/packages/core-data/src/resolvers.js:127` · [Expected sites](data/R-013-sites-expected.csv)
- How many real conflicts, behavior changes and elapsed hours do the two recommended rebases generate, and can the proposed 24-hour clean / 72-hour conflict targets survive overlapping releases? Release-frequency and per-backport security labels should be revisited before offering additional supported series. [R-005 SLA proposal](R-005-patch-mechanism-and-licensing.md#14-security-releases-and-a-proposed-sla-compatible-workflow) · [Release history](data/R-013-release-pins.csv)
- Can historic Gutenberg provenance be verified for the unmatched packages on superseded 6.8/6.9 branches? The exact source behind those dependency versions remains undetermined. [Release pins](data/R-013-release-pins.csv) · [Churn coverage](data/R-013-churn.csv)

## Method/reproduction

Sibling inputs live at the following repo-relative paths. Their links resolve in the corresponding sibling worktree or once its artifacts land in the same branch. R-005's proposed mechanism and demo informed the effort workflow. No application code, fixture DB, runtime install or live release was exercised by this spike. The SQLite reference was outside the footprint.

| Worktree | Repo-relative input |
| --- | --- |
| R-001 | `docs/research/R-001-php-integer-id-audit.md` and `docs/research/data/R-001-php-id-hits.csv` |
| R-002 | `docs/research/R-002-schema-and-sql-paths.md`, `docs/research/data/R-002-columns.csv` and `docs/research/data/R-002-ddl-paths.csv` |
| R-005 | `docs/research/R-005-patch-mechanism-and-licensing.md`, `docs/adr/0001-wordpress-change-strategy.md` and `tools/patchset/` |
| R-012 | `docs/research/R-012-editor-rest-id-audit.md`, `docs/research/data/R-012-js-hits.csv` and `docs/research/data/R-012-rest-hits.csv` |

From the R-013 worktree, use Python 3.10+ and Git. The only network operations are the two scratch clones and lazy blob fetches from their Git remotes. The other steps read the pinned references and sibling CSVs. Run the sample command without `--review` and with `--context` to regenerate the reviewed frame for inspection. Sample labels are human annotations.

```sh
refs=../../reference
data=docs/research/data
scripts=tools/research/R-013
hits=../R-001/docs/research/data/R-001-php-id-hits.csv

python3 -B "$scripts/sample.py" "$refs/wordpress-develop-7.1.5" "$hits" \
  --review "$data/R-013-ambiguous-sample.csv"
python3 -B "$scripts/estimate.py" "$refs" .. "$data"

scratch=$(mktemp -d /tmp/pressgres-r013.XXXXXX)
git clone --bare --filter=blob:none https://github.com/WordPress/wordpress-develop.git "$scratch/wp.git"
git clone --bare --filter=blob:none https://github.com/WordPress/gutenberg.git "$scratch/gb.git"
python3 -B "$scripts/history.py" "$refs" "$scratch" "$data"
python3 -B "$scripts/effort.py" "$data"
markdownlint-cli2 docs/research/R-013-patchset-size-and-rebase-cost.md
git diff --check
```

- `estimate.py` performs the scenario filters, source-line mapping, deduplication and Wilson extrapolation. The helper-leverage counts select R-001 `identity=identity` rows with `entity!=sites/blogs`, filter `pattern` on `wp_parse_id_list` or `implicit`, and count distinct `(file,line)` pairs. [R-001 inventory](data/R-001-php-id-hits.csv) · [Estimator](../../tools/research/R-013/estimate.py)
- `history.py` reads numeric tags in the four series through 2026-11-18 UTC, records each commit SHA and timestamp, takes consecutive point tags within each series, and pairs minor launches both with the previous launch and the previously shipped latest point. A point is in the latest series if its tag predates the next feature release. It matches old Gutenberg package versions against first-parent publish commits available at or before the relevant WordPress tag and prioritizes agreement on audited packages, then all packages, then recency. [History script](../../tools/research/R-013/history.py) · [Release pins](data/R-013-release-pins.csv)
- Churn uses `git diff --no-renames --numstat --patch --unified=0 OLD NEW -- <pathspec>`. Lines are insertions plus deletions. Moves count as a deletion and an addition where their paths are in the named set. A second zero-context diff projects each pinned coordinate onto the older tree. Unchanged spans project exactly under line offsets, while replaced spans or deletion seams project to an uncertain range. Overlaps are counted once per clustered hunk at N=0/3/10. Insertions use their old-side line boundary. Hunk counts on added files with no base path are recorded separately. [History script](../../tools/research/R-013/history.py) · [Per-file data](data/R-013-churn-files.csv)

- Verification passed with Python 3.14.2 and Git 2.54.0. The source-backed sample validator passed, the eight generated CSVs reproduced byte for byte, and all 92 layer comparisons reconciled with the detailed file counts. Both layers of 7.1.4 → 7.1.5 also matched a standalone Git numstat check. Markdownlint CLI2 0.24.0 reported zero issues. Static fixture checks covered line projection over inserts and deletes and hunk grouping.
