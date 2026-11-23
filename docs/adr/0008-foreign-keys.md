# ADR-0008: Foreign key enforcement (gradual, after compatibility tests)

- **Status:** Proposed
- **Date:** 2026-11-23
- **Deciders:** Project lead (solo maintainer)
- **Related issues:** pressgres/pressgres#5 (R-003), R-002, R-009 (pressgres/pressgres#9), D-003; ADR-002, ADR-009, ADR-011

## Context

With UUID-only identity (ADR-002), every reference column is a PostgreSQL `uuid`, which already rejects malformed and integer values. The open question is whether, and when, to add physical `FOREIGN KEY` constraints that WordPress on MySQL never had.

Evidence:

- **[R-002](../research/R-002-schema-and-sql-paths.md#schema-inventory):** the single-site schema has 12 tables, 94 columns and 41 keys, with **zero physical foreign keys** upstream. It has 11 generated PKs, **12 FK-role columns** and **2 polymorphic-role columns**: `comments.comment_post_ID` (accepts zero for absence) and `term_relationships.object_id` (spans posts, links and registered object types). R-002 says both need review before any physical FK. Five mixed-case columns must be quoted (`"ID"`, `"comment_ID"`, `"comment_post_ID"`, `"comment_author_IP"`), and constraint DDL must use the same quoting.
- **Install order and seeds (R-002):** `wp_install_defaults()` hardcodes `term_id=1`, `object_id=1`, `comment_post_ID=1`, post IDs 2 and 3 for postmeta and the privacy-page option, and `?p=1` / `?page_id=2` GUIDs. `links.link_owner` defaults to `1`. The patched installer must capture each generated UUID before writing dependent rows. A physical FK will make any missed spot fail loudly, which is good, but only once the seed patch is complete.
- **Sentinels:** WordPress uses `0` for "no parent" or "no owner". [R-003](../research/R-003-uuid-prototype.md#failures-hit-and-workarounds-chronological) maps `0`/`''` to `NULL` only on typed bindings. Hand-written SQL comparing against `0` had to be patched in core to `IS NULL`. `post_parent` stored as `NULL` reads back as `0` after sanitization. R-003 deliberately ran with **no FK constraints**, as [04 — Data model](../04-data-model.md) recommends: "First prototype identity without broad FK enforcement; add per-table constraint after real tests."
- **Write and delete order:** WordPress deletes children (meta, relationships, comments) in PHP, statement by statement, mostly without wrapping transactions. Deferred constraints only help inside a transaction. No spike has measured the order WordPress uses for deletes or whether intermediate states violate a parent-child constraint.
- **Test baseline:** [R-009](../research/R-009-core-phpunit-baseline.md) gives a measurable gate (77.47% comparable pass rate on the prototype, with a ratchet recommended). An FK that breaks core tests shows up as a ratchet regression.

## Decision

**Ship the first schema with typed, nullable `uuid` references and no physical foreign keys. Add FKs one relationship at a time, only after that relationship's write, delete and seed paths pass compatibility tests.**

1. **Phase 0 (first release).** All references are `uuid` (nullable except the `term_relationships` composite PK). The `0` sentinel becomes `NULL` at typed boundaries only. A CI and `wps verify` **orphan check** reports dangling references for every logical relationship in R-002's inventory. It reports but does not block.
2. **Phase 1 candidates** (simple parent-child, deleted by core before or with the parent): `postmeta.post_id → posts."ID"`, `commentmeta.comment_id → comments."comment_ID"`, `termmeta.term_id → terms.term_id`, `usermeta.user_id → users."ID"`, `term_taxonomy.term_id → terms.term_id`, `term_relationships.term_taxonomy_id → term_taxonomy.term_taxonomy_id`.
3. **Phase 2 candidates** (more complex semantics): self-references (`posts.post_parent`, `comments.comment_parent`, `term_taxonomy.parent`), user ownership (`posts.post_author`, `links.link_owner`, `comments.user_id`), where core reassigns or nulls on user deletion. `comments.comment_post_ID` belongs here, after R-002's zero-for-absence review.
4. **Never a plain FK:** `term_relationships.object_id`, which is polymorphic across tables. It stays a typed reference checked by the orphan job, or gets a reviewed trigger if evidence later justifies one.
5. **Gate for each FK.** A constraint ships only when the following pass with it enabled: the fresh-install seed path, core CRUD and delete flows for both endpoint tables, the R-009 PHPUnit ratchet with no regressions, and an upgrade or replay on a fixture with existing data. It is added through a reviewed migration (ADR-011) as `NOT VALID`, then `VALIDATE CONSTRAINT`, so existing rows are checked without a long lock. The `ON DELETE` action is `NO ACTION` unless tests justify otherwise. Pressgres does not add cascades that change what WordPress deletes.
6. **Plugins.** Plugin tables get FKs only through their reviewed manifest migrations (ADR-004). No plugin FK may point into core tables without a test for the core delete path.

## Consequences

- **Positive:** the first release does not depend on WordPress's unmeasured write and delete ordering. The `uuid` type already blocks the worst failure class (silent integer truncation). Each FK added later makes corruption fail loudly instead of silently, which helps the security priority on data integrity.
- **Negative:** until Phase 1, referential integrity relies on application code plus the orphan check, the same as WordPress on MySQL. Each FK is a separate migration with its own tests and review. Some plugins that write orphan rows may break when FKs arrive. Those plugins have to be found through manifests.
- **Compatibility matrix:** a column listing which FKs each Pressgres release enforces, so operators and plugin manifests know what to expect.
- **Migration impact:** adding an FK to an existing site needs the orphan report to be clean first, or a reviewed cleanup. For imported sites (ADR-009), crosswalk reconciliation must leave zero orphans for enforced relationships.

## Alternatives considered

- **Full FK enforcement from day one:** strongest integrity, but the seed and delete paths are not yet patched or measured, and failures would block install. Rejected for the first release.
- **Never add physical FKs (MySQL parity):** gives up a PostgreSQL strength and leaves orphan detection to batch jobs forever. Rejected as an end state.
- **`DEFERRABLE INITIALLY DEFERRED` everywhere:** only helps inside transactions, and most WordPress writes are autocommit statements. May be used per relationship if tests show it helps. Not a blanket policy.
- **Trigger-based checks for all references:** harder to review and slower than native FKs. Reserved for the polymorphic case only.

## Open items / revisit triggers

- Measure core delete ordering for posts, comments, terms and users under PostgreSQL. This is a prerequisite for each Phase 1 and Phase 2 FK.
- Decide the PHP-side sentinel policy (`0` vs `null` on read-back, R-003 open question 2). It affects how `NULL` references behave in plugins.
- Revisit if the orphan check finds core itself producing orphans in normal flows. Fix core first, then constrain.
