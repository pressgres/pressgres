# ADR-0011: DDL staging model (schema planner and migrator role only; web runtime never executes DDL)

- **Status:** Proposed
- **Date:** 2026-11-23
- **Deciders:** Project lead (solo maintainer)
- **Related issues:** pressgres/pressgres#8 (R-006), R-002, pressgres/pressgres#9 (R-009), S-001, D-003, P-003; ADR-003, ADR-004, ADR-008, ADR-009

## Context

WordPress and its plugins change the schema at runtime: `dbDelta()` during install and upgrade, `CREATE TABLE` in plugin activation hooks, and ad hoc `ALTER TABLE`. On MySQL the web process usually holds a database user that can do all of this. For Pressgres this is a security problem (a compromised plugin can alter or drop the schema). It is also a correctness problem: MySQL DDL has no safe automatic translation to a UUID-only PostgreSQL schema.

Evidence:

- **[R-002](../research/R-002-schema-and-sql-paths.md#ddl-and-schema-discovery):** `dbDelta()` parses `CREATE TABLE` text with regexes, inspects the catalog through `DESCRIBE` and `SHOW INDEX`, and generates `CHANGE COLUMN`, `ALTER COLUMN ... SET DEFAULT`, `ADD COLUMN` and `ADD` index statements. It does not check individual `query()` results. Core has **37 literal `ALTER TABLE` sites** plus **4 generated ALTER forms**, 9 literal `DROP TABLE` sites and helper functions (`maybe_create_table()`, `maybe_add_column()`, `maybe_convert_table_to_utf8mb4()`). R-002 recommends replacing the MySQL schema emitter with **versioned PostgreSQL migrations under the migrator role**, and **staging plugin `dbDelta()` output as reviewable migration plans** that fail closed on unknown DDL.
- **[R-006](../research/R-006-threat-model-and-sandbox.md#captured-output):** the sandbox ran the runtime as a separate non-owner login with only CONNECT, schema USAGE and table DML. The schema owner was a no-login role. The DDL fixture was refused **at both layers**: **2 adapter rejections** and **4 PostgreSQL `42501` (insufficient privilege) denials** for direct `CREATE`, `ALTER`, `DROP` and `CREATE TEMP` under the runtime role. The worker never had the migrator credential or a route to it.
- **[06 — Security](../06-security-operations.md#security-architecture):** `wps_migrator` owns and changes the schema only at deploy time. `wps_runtime` cannot `CREATE`, `ALTER` or `DROP`. The web runtime does not store migration credentials. The [threat model](../security/threat-model.md#top-10-risks) ranks "runtime or agent gets migrator privileges" as risk 4.
- **[R-009](../research/R-009-core-phpunit-baseline.md#pg-a--prototype-verbatim-fails-in-the-bootstrap-0-):** this rule has a real cost. With an adapter that rejects DDL, the stock PHPUnit bootstrap installs **nothing** (0%: `SET`, 18 `DROP TABLE`, 36 `DESCRIBE` and 12 `CREATE TABLE` rejected, then `wp_insert_user()` fails). The test harness needs a pre-created schema. Core tests also rewrite `CREATE TABLE` to `CREATE TEMPORARY TABLE` inside tests.

## Decision

**All DDL goes through a schema planner and is applied by a separate migrator role outside the web request path. The web runtime (PHP-FPM, WP-Cron, REST) never executes DDL. The adapter rejects it, and PostgreSQL denies it independently.**

1. **Two layers of enforcement.**
   - *Adapter:* the SQL adapter (ADR-003) classifies statements by AST. Any DDL (`CREATE`, `ALTER`, `DROP`, `TRUNCATE`, `RENAME`, `CREATE TEMP`), plus `DESCRIBE` and `SHOW` that are not mapped to the catalog adapter, is rejected on the runtime connection with a clear error and an audit event.
   - *Database:* `wps_runtime` is a non-owner login with `CONNECT`, schema `USAGE` and the table DML it needs. Schema objects are owned by a `NOLOGIN` owner role. `PUBLIC` loses database and schema grants. This is the R-006 setup, made the production default.
2. **Core schema.** Shipped as versioned native PostgreSQL migrations (D-003) and applied by `wps install` and `wps upgrade apply` using short-lived migrator credentials that only the installer process receives ([03 — Installer](../03-installer-cli.md)). Core's `dbDelta()`, `pre_schema_upgrade()` and the `maybe_*` helpers are patched (ADR-001) so they do not emit DDL on the managed runtime. The WordPress DB revision only advances after the migration is verified.
3. **Plugin schema.** When a plugin calls `dbDelta()` or emits DDL, Pressgres does not execute it. In the sandbox (ADR-004), the planner captures it and translates recognized statements into a PostgreSQL migration plan (UUID references, quoted identifiers, deterministic index names). Unknown shapes, identity semantics it cannot resolve, and destructive operations fail closed. The reviewed plan becomes part of the plugin's signed manifest. `wps plugin install` applies it with the migrator role **before** activation.
4. **Applying migrations.** Each run takes an advisory lock, requires a verified restore checkpoint, and runs plan, dry run, apply and verify with an operator checkpoint ([05](../05-plugin-compatibility.md#plugin-schema-migration-algorithm)). Constraint changes such as ADR-008 FKs use the same path (`NOT VALID`, then `VALIDATE`).
5. **Tests and dev.** Test harnesses and dev stacks create the schema with the migrator before the suite runs, as R-009 did. They do not loosen runtime privileges. Agents and CI bots never hold production migrator credentials (threat model B8).

## Consequences

- **Positive:** a compromised plugin or request cannot change or drop the schema. That holds even if the adapter has a bug, because PostgreSQL enforces it separately (R-006: 4/4 direct DDL attempts denied). Every schema change is reviewed, versioned and reproducible, which matches AGENTS rule 6.
- **Negative:** plugins that create tables lazily at runtime, or that call `dbDelta()` on update, will not work until a manifest migration exists. This is by design but reduces compatibility. Upstream test infrastructure needs a patched bootstrap or wrapper (R-009 found 0% without one). Plugin upgrades that change schema need an operator step.
- **Neutral:** `CREATE TEMPORARY TABLE` is denied on the runtime too. Any core or plugin path that needs temp tables in production has to be found and handled explicitly. Tests use them (R-009 harness item 6).
- **Compatibility matrix:** plugins that emit DDL are listed with the manifest migration version that covers them. Without one they are `BLOCKED`.
- **Migration impact:** all schema evolution is a forward migration with a recorded checkpoint. Rollback is restore or a forward fix, never an automatic undo (05 rollback nuance).

## Alternatives considered

- **Translate DDL live in the runtime (MySQL DDL to PostgreSQL on the fly):** gives the web process schema authority, and arbitrary `ALTER` cannot be translated safely to UUID semantics ([05](../05-plugin-compatibility.md#database-translation-pipeline)). Rejected.
- **Runtime role with DDL rights but adapter-only filtering:** one layer, inside the same process a malicious plugin controls. Direct PDO bypasses it (threat model B3). Rejected.
- **Let plugins run DDL during activation with a temporary elevated role:** activation runs arbitrary plugin PHP, which would then hold schema authority. Rejected.
- **Allow `CREATE TEMP` on the runtime:** lower risk than persistent DDL, but it extends what the runtime can do with no measured need. Deferred until evidence shows a supported path requires it.

## Open items / revisit triggers

- Find core and target-plugin paths that need temporary tables or runtime `SHOW` and `DESCRIBE`, and decide per path whether to use the catalog adapter, patch the caller or reject.
- Decide whether the patched `tests/phpunit/includes/` bootstrap is part of the managed patchset or a harness-only layer (R-009 open question).
- Narrow the runtime grants further (R-006 open question) and define the backup role's grants.
- Revisit if a target plugin from R-014 cannot work without runtime DDL. The answer is a manifest migration or excluding the plugin, not granting DDL.
