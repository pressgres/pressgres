# ADR-0009: Legacy migration scope (fresh sites first; restricted core-only import pilot with explicit crosswalk)

- **Status:** Proposed
- **Date:** 2026-11-23
- **Deciders:** Project lead (solo maintainer)
- **Related issues:** R-002, R-008 (user discovery), X-002, X-003, M-001 (roadmap M4); ADR-002, ADR-004, ADR-008, ADR-011

## Context

Existing WordPress sites run on MySQL with `bigint unsigned` IDs. Pressgres is UUID-only (ADR-002), so moving a site over means **re-identifying every entity** and rewriting every place an old ID appears. [14 — Open decisions](../14-open-decisions.md#questions-to-resolve-before-m1) asks whether a fresh site is enough for the first release or whether MySQL import must ship at 1.0. [01 — Scope](../01-product-and-scope.md#explicitly-out-of-scope-for-10) already excludes "seamless MySQL-to-PostgreSQL migration for arbitrary production sites".

Evidence:

- **[R-002](../research/R-002-schema-and-sql-paths.md):** all 25 identity-role columns are `bigint(20) unsigned`. Import must treat legacy IDs as lossless decimal strings, including values above the signed 64-bit range. `links.link_owner` defaults to `1`, so import must resolve the real legacy user 1 through the crosswalk. Legacy zero in the `term_relationships` composite PK needs reconciliation. `term_relationships.object_id` is polymorphic. Option payloads carry legacy IDs (for example, default category options sanitized with `absint()`). Exact release-to-revision mappings for older 6.x sources were **not available**, so supported source versions must be keyed by stored DB revision. R-002 recommends keeping "MySQL extraction and UUID crosswalk in the separate import path".
- **[04 — Data model](../04-data-model.md#source-to-target-migration-existing-mysql-site)** already specifies the procedure: read-only source snapshot, a per-entity crosswalk `(entity_type, source_table, legacy_id) → uuidv7`, parent-first copy, typed rewriting of references, meta, block JSON, serialized PHP and URLs, reconciliation, staged cutover, and rollback by restoring the source rather than reversing UUIDs.
- **[Threat model](../security/threat-model.md#top-10-risks)** risk 5: "Bad migration corrupts typed references or loses data", gated by crosswalk reconciliation and a tested restore (X-002, B-001). [11 — Trade-offs](../11-tradeoffs-risks.md) R5: corrupt serialized or opaque plugin data is **critical**.
- [R-013](../research/R-013-patchset-size-and-rebase-cost.md) explicitly **excludes** bulk content migration from its patchset and effort estimate, so import is unbudgeted work on top of about 74 engineer-days a year of release duty (ADR-006).
- No spike has measured import. There is no evidence today that the first users need it. That is R-008's question.

## Decision

**The first Pressgres release supports fresh sites only. Legacy import comes later as a restricted, core-only pilot with an explicit source-ID crosswalk. Unknown data blocks the import.**

1. **First release: fresh installs only.** `wps install` creates a new site. Content can come in through supported APIs, such as the REST API or a Pressgres-tested importer, which assign new UUIDs naturally. There is no `wps migrate` for MySQL sources.
2. **Pilot scope (roadmap X-002, M4).** Single-site only. Core tables only (the 12 in R-002). Source profiles pinned by WordPress DB revision and MySQL or MariaDB version. Plugin tables and plugin-owned serialized data are **out of scope** unless a reviewed typed mapper exists in an ADR-004 manifest (X-003). Otherwise the import is blocked and the tables are exported to quarantine.
3. **Crosswalk.** A dedicated migration schema stores `(entity_type, source_table, legacy_id_text) → uuid`. Legacy IDs are stored as text so unsigned 64-bit values are never truncated. Every typed reference, registered meta field, option payload and block attribute is rewritten through the crosswalk by field-specific adapters. Blind numeric search-and-replace is forbidden. The crosswalk is kept for redirects (`?p=<legacy>`) and external integrations, with a documented retention period.
4. **Safety.** The pilot reads from a read-only source snapshot, writes to a new database through the migrator role (ADR-011), and runs on a schedule of: plan, dry run, reconcile, apply. Reconciliation covers row counts, zero orphans for enforced FKs (ADR-008), link and media checks, and sampled redirects. A failed or partial import means discarding the target, never a partial cutover. Rollback means returning to the source site.
5. **Priority can change on evidence.** If R-008 user discovery shows the first persona cannot adopt without import, this ADR is revisited, and the pilot may move earlier. It keeps the same core-only, blocking scope.

## Consequences

- **Positive:** the first release avoids the highest-risk data path (threat model risk 5) and stays within one maintainer's budget. The crosswalk design keeps legacy URLs and integrations working when import arrives.
- **Negative:** existing WordPress sites cannot move to Pressgres at launch, which limits adoption to new projects. Even the pilot will reject most real sites, because most real sites have plugins with custom tables or serialized IDs.
- **Compatibility matrix:** a separate "import source profiles" table, empty at first release, listing (source DB revision, MySQL or MariaDB version, supported core tables) once the pilot exists.
- **Migration impact:** none for the first release. The pilot adds a migration schema and `wps migrate plan/apply/verify` (M-001).

## Alternatives considered

- **Import required at 1.0:** delays the first release by an unbudgeted amount and puts the most dangerous data path on the critical path without measured evidence of demand. Rejected unless R-008 shows otherwise.
- **General importer including plugin data:** opaque serialized payloads cannot be safely remapped in general ([05](../05-plugin-compatibility.md#existing-site-plugin-migration)). Rejected.
- **Keep legacy integer IDs alongside UUIDs (dual IDs):** out of scope. Pressgres is UUID-only (ADR-002). Legacy IDs live only in the crosswalk.
- **Deterministic UUIDs derived from legacy IDs:** would not be time-ordered UUIDv7 and would leak source IDs. A crosswalk is explicit and auditable. Rejected.
- **WordPress WXR export and import only:** a reasonable route for users to try (it re-creates content through WordPress APIs). Not verified on Pressgres, loses some data, and is not a substitute for a reconciled migration. It may be documented as a best-effort path once tested.

## Open items / revisit triggers

- R-008 result: does the first persona need import at 1.0?
- Which source DB revisions and MySQL or MariaDB versions the pilot accepts. R-002 could not map releases to revisions from the pinned checkout.
- Policies for orphaned references, missing default link categories and legacy zero rows in `term_relationships` (R-002 open questions).
- Crosswalk retention period and privacy treatment, since it maps public legacy URLs to UUIDs.
