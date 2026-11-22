# 05 — Plugin installation, compatibility and migrations

## Fundamental truth

A SQL translator cannot repair a PHP plugin that casts post IDs to integers, uses `%d` for UUIDs, embeds numeric IDs in external contracts or assumes `AUTO_INCREMENT` in business logic. Therefore **plugin support is opt-in and evidence-based**, not universally automatic.

## Plugin installation state machine

`DISCOVERED -> DOWNLOADED -> VERIFIED -> SCANNED -> {BLOCKED|SANDBOX_PENDING} -> SANDBOX_TESTED -> {BLOCKED|APPROVED} -> STAGED -> MIGRATION_APPLIED -> ACTIVATED -> MONITORED`.

See [plugin diagram](../diagrams/plugin-install.mmd).

## Scan gates

- Verify artifact checksum/signature where publisher supports it; record origin and dependency licenses.
- Parse `readme.txt`, main plugin headers, Composer constraints, dependency tree, activation hooks, `dbDelta` calls, direct `mysqli`, `$wpdb` queries, `CREATE/ALTER`, `wpdb->insert_id`, `get_*_id`, `%d`, `(int)` casts and regex-enforced numeric REST routes.
- Create manifest with `UUID_SAFE`, `SQL_ADAPTABLE`, `NEEDS_ADAPTER`, `UNSUPPORTED`, `UNKNOWN`; record evidence path/line and confidence.
- Static analysis is not proof; sandbox executes install, activate, create/read/update/delete, upgrades and uninstall against throwaway DB with no production credentials.
- On `UNKNOWN` fail closed and request reviewed adapter or explicit test-scope exception; no production activation bypass by default.

## Adapter manifest (versioned, reviewed, not arbitrary PHP generation)

```yaml
schema_version: 1
plugin_slug: example-gallery
plugin_version_range: '>=2.0 <2.2'
wordpress_runtime: '7.1-managed-uuid'
postgres_min: '18'
identity_contract: uuidv7-only
sql_ruleset: gallery-v1
schema_migrations:
  - 001_create_gallery_uuid_table
php_adapter: null
checks:
  - activate
  - media_create_and_delete
  - uninstall_in_sandbox
verdict: pending_tests
```

Place manifest in `adapters/<slug>/<version-range>/manifest.yaml` with reviewed rules, schema change scripts, tests, owners, provenance and hash. Never assume generated adapter code can be trusted; tests + code review required. Hook into `upgrader_pre_install`, `upgrader_process_complete`, plugin activation and WP-CLI paths, **but** treat hooks as defense in depth; controlled `wps plugin install` is the supported path because an unsupported plugin may execute code at activation or bypass normal channels. Production deploy should disable general plugin installs via WordPress admin.

## Database translation pipeline

`sql statement -> lex/parse -> typed AST -> identify object/column types -> apply approved semantic transforms -> render PostgreSQL + bind params -> execute -> normalize wpdb result`.

Examples:

| MySQL idiom | Strategy / caveat |
|---|---|
| Backticks | AST identifier quoting; preserve `"ID"` casing |
| `IFNULL(a,b)` | transform to `COALESCE(a,b)` after type tests |
| `SHOW TABLES` | catalog adapter |
| `ON DUPLICATE KEY UPDATE` | only with resolved unique conflict target |
| `SQL_CALC_FOUND_ROWS` | controlled count query semantics; benchmark |
| `AUTO_INCREMENT` | for primary entity identity: UUID default; ordinary counters remain numeric |
| `LAST_INSERT_ID()` | use statement-scoped `RETURNING`; cannot globally substitute |
| `dbDelta()` schema | dedicated schema planner, **do not** translate arbitrary ALTER in live runtime |
| MySQL collation/coercion | explicit compatibility tests; may remain unsupported |

## Plugin schema migration algorithm

1. **Preflight**: plugin/version lock; verify app/DB permissions, backups and staging DB.
2. **Introspect** plugin's declared tables and observed SQL; classify every PK/FK and non-identity numeric fields.
3. **Plan** AST translation into PostgreSQL-native migrations. Generate explicit diff and irreversible-operation warnings.
4. **Dry run** in clone/ephemeral DB with representative fixture data and all activation/update hooks.
5. **Verify** schema, data invariants, native UUID references, app behavior and performance; redact logs.
6. **Approve** immutable manifest digest (signed in trusted CI).
7. **Apply** under migration advisory lock with operator checkpoint, limited installer credentials, batched DML and monitored transaction boundaries.
8. **Activate** the plugin only after committed migrations and health checks.
9. **Upgrade** by re-running analysis for every new plugin version; never reuse approval blindly.
10. **Recover** by tested restore/checkpoint or forward fix; record failures and block plugin.

**Rollback nuance:** PostgreSQL DDL is often transactional but plugins may perform external side effects or mixed operations. Backups and roll-forward scripts are required; never promise universal atomic rollback.

## Existing site plugin migration

Existing MySQL plugin tables need explicit entity ID crosswalk declarations and relationship graph. Opaque serialized payloads cannot be safely remapped generically. Quarantine unknown tables as exports until a typed mapper is reviewed; activation blocked for plugin owning unsupported data.

## Acceptance scenarios

- Clean plugin with no custom tables and no integer-ID casts passes; activation succeeds.
- Plugin creates UUID-safe table via approved SQL migration; unique constraints and relations validated.
- Plugin contains `(int) $post_id`; scan records violation, activation blocked unless verified PHP adapter.
- Plugin upgrade adds unsafe `ALTER TABLE` or `bigint` FK; migration plan rejects before writes.
- Plugin uninstall attempts to drop shared tables; dry-run catches destructive effect and requires approval.
- Plugin direct PDO/mysqli bypasses `$wpdb`; flagged unsupported unless a specific reviewed adapter exists.
