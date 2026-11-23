# ADR-0003: SQL parser (reuse standalone `wordpress/mysql-parser`)

- **Status:** Accepted (2026-11-23)
- **Date:** 2026-11-23
- **Deciders:** Project lead (solo maintainer)
- **Related issues:** R-004, R-002 (roadmap tasks in [08 — Roadmap](../08-roadmap.md)); R-015 / pressgres/pressgres#16 (licensing); ADR-001, ADR-002, ADR-011

## Context

Pressgres runs WordPress and plugin SQL, written for MySQL, on PostgreSQL 18. [AGENTS](../../AGENTS.md) rule 5 requires AST-based transforms that fail closed on unsupported syntax. Regex rewriting is out. The open question from [14 — Open decisions](../14-open-decisions.md#pending-adrs-and-default-recommendation) was whether to reuse the parser from WordPress's SQLite Database Integration, fork it or write one.

Evidence from [R-004](../research/R-004-sqlite-parser-evaluation.md), against SQLite Database Integration 3.1.3 and wordpress-develop `7.1.5-src`:

- The reference tree ships two parsers: the Workbench-derived parser wired into the SQLite driver, and a **standalone `wordpress/mysql-parser` package** (LALR(1), generated with Bison 3.8.2 from MySQL Server 8.4.10's `sql_yacc.yy`, PHP >=7.2 runtime only, documented API).
- Corpus: 1,282 `$wpdb` call sites in `src` and `tests/phpunit`, 19 schema definitions and 14 supplemental inputs. Each parser accepted **421/423 extracted inputs (99.53%) and 435/437 overall**. Source review attributed both rejects to extraction or test context (an incomplete prepared prefix and a deliberately malformed PHPUnit input), not to grammar gaps. A manual 40-input sample had a 2.5% extractor false-positive rate.
- Performance (one local run, PHP 8.4.27, OPcache off): standalone median **26.708 µs** and p95 **92.959 µs** per statement, against 140.125 µs and 434.208 µs for the SQLite driver's front end. The standalone path had a higher heap peak (8,284,952 vs 7,411,176 bytes).
- The SQLite driver's emitter is private, tied to PDO SQLite and in places executes queries during translation. It cannot be reused as a PostgreSQL emitter. The standalone parser produces grammar-shaped nodes only, so Pressgres must supply identifier, type and semantic context itself.
- Both packages declare GPL-2.0-or-later. The Workbench grammar keeps two Oracle **GPL-2.0-only** notices with an additional linking permission. The standalone package's generated inputs (`sql_yacc.yy`, `lex.h`, Workbench lexer lineage) are pinned by SHA-256, but their original notices were not in the snapshot and are **unverified**.
- Coverage is syntax-only and static. R-004 rates any extrapolation to runtime coverage as low confidence: filter-assembled SQL, plugin queries and upgrade paths are underrepresented.

[R-002](../research/R-002-schema-and-sql-paths.md) fixes what the emitter must handle: five mixed-case columns that need quoting (`"ID"`, `"comment_ID"`, `"comment_post_ID"`, `"comment_author_IP"`), `INSERT ... ON DUPLICATE KEY UPDATE` in the option API, `REPLACE` as a public `wpdb` method, `REGEXP` in install, and 37 literal plus four generated `ALTER` forms in upgrade code.

## Decision

**Use the pinned standalone `wordpress/mysql-parser` as the MySQL front end, behind a Pressgres-owned adapter, and build the PostgreSQL 18 emitter in Pressgres.**

1. **Pin and wrap.** Pin an exact package version and hash. Only a Pressgres adapter touches parser rule names and token constants. The adapter requires complete lexing, exactly one statement, resource bounds and an allowlist of semantic AST shapes. Anything else is rejected (fail closed).
2. **Emitter rules come from R-004's "Fit for PostgreSQL" table.** Examples: `LIMIT x,y` → `LIMIT y OFFSET x`; `ON DUPLICATE KEY UPDATE` → `ON CONFLICT (known_key) DO UPDATE` only for reviewed unique keys; generated identity through `RETURNING "ID"`. Generic `REPLACE`, raw `LAST_INSERT_ID()`, unknown `REGEXP` semantics and any DDL on the web path are rejected by default. Pressgres patches managed callers instead. DDL routing is covered by ADR-011.
3. **Upgrade gate.** Every parser pin update must pass the R-004 corpus, AST shape snapshots for representative statements and the PostgreSQL fixture suite before it merges.
4. **SQL mode profile.** Pin the lexer version and SQL mode set used for WordPress input and test it on every dependency update.
5. **Packaging.** The standalone package and the SQLite driver declare overlapping global class names, so Pressgres loads only the standalone parser. If upstream cannot ship a required fix or packaging change, a narrow fork is the fallback. The fork inherits the same provenance and notice obligations.
6. **Redistribution gate.** Pressgres does not distribute a release containing the parser until the licensing review in the open items below is complete. Development and prototypes may use it now.

## Consequences

- **Positive:** no grammar to write or maintain. The measured front end is fast enough not to dominate request latency on this corpus. Upstream is an obvious place to report grammar regressions. The SQLite driver stays useful as a source of semantic and regression test ideas.
- **Negative:** Pressgres depends on an upstream package whose scope is SQLite-focused, and R-004 could not tell whether upstream wants a stable AST contract or a PostgreSQL consumer. Rule names can change between releases, which is why the snapshot gate exists. The emitter, which is the bigger part of the work, is all Pressgres code.
- **Neutral:** syntax acceptance is not compatibility. The compatibility matrix lists a SQL category as supported only after PostgreSQL fixture tests, never on parser acceptance alone (AGENTS rule 3).
- **Licensing:** the distributed artifact may carry GPL-2.0-only components. In practice the combined distribution is then under GPLv2 terms even though Pressgres code is GPL-2.0-or-later. This is consistent with ADR-007 but must be stated in the release notices.

## Alternatives considered

- **Reuse the SQLite driver's Workbench-derived parser:** same 435/437 acceptance, but its API is marked private. It was about 5x slower on median in this run (140.125 vs 26.708 µs), and its emitter is not reusable. Kept as a prototype fallback only.
- **Fork the parser now:** takes on grammar provenance and update obligations with no demonstrated gain. Kept as a fallback for blocking fixes.
- **Write a new parser:** adds grammar maintenance a solo maintainer cannot carry, with no measured advantage.
- **Regex or string rewriting:** violates AGENTS rule 5 and cannot fail closed reliably.

## Open items / revisit triggers

- **Licensing gate (blocks redistribution, not prototyping):** confirm the original notices and corresponding-source obligations for the pinned MySQL Server `sql_yacc.yy` and `lex.h` and the Workbench lexer lineage. Decide how release artifacts preserve Oracle's GPL-2.0-only notices and the linking exception. Tracked with R-015 (pressgres/pressgres#16). Not verified in this ADR.
- **Runtime coverage:** R-004 measured static extraction only. Before ADR acceptance moves the emitter past prototype, capture redacted runtime SQL from disposable WordPress fixtures (filters, upgrade paths, the initial plugin targets once R-014 picks them) and re-run acceptance.
- **Revisit** if the upstream package changes license, stops publishing, or an AST snapshot update breaks more than a small number of adapter rules in one release.
