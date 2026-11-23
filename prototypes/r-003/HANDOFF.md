# R-003 prototype handoff (for R-009 and later spikes)

How to reuse the R-003 `db.php`, schema and core patch without touching this directory. Everything here is throwaway research code; read the limits in [`docs/research/R-003-uuid-prototype.md`](../../docs/research/R-003-uuid-prototype.md) before relying on it.

## Reusable pieces

| Piece | Path (relative to the repo root) | Notes |
|---|---|---|
| `$wpdb` drop-in | `prototypes/r-003/wordpress/db.php` | Copy to `wp-content/db.php`. Defines `Pressgres_R003_wpdb` and assigns `$wpdb`. |
| Config template | `prototypes/r-003/wordpress/wp-config.php` | Reads env vars below; hard-codes `/r003/build/logs/wp-debug.log`, change for your layout. |
| Schema | `prototypes/r-003/sql/01-schema.sql` | Only 9 tables (no comments, commentmeta, links, multisite). |
| Seed options | `prototypes/r-003/sql/02-seed-options.sql` | Boots WordPress without `wp_install()`. Roles/users/terms are created by `scripts/setup.php`. |
| Core patch | `prototypes/r-003/patches/wordpress-7.1.5-r003-uuid.patch` | Apply with `patch -p1 -d <wordpress-src-copy>` against wordpress-develop 7.1.5 `src/` only. |
| PHP image | `prototypes/r-003/docker/php/Dockerfile` | `php:8.4.27-cli-alpine` + `pdo_pgsql`. |

## Environment variables read by `db.php` / `wp-config.php`

| Variable | Default | Meaning |
|---|---|---|
| `PG_HOST`, `PG_PORT` | `db`, `5432` | Joined into `DB_HOST` as `host:port` |
| `PG_DATABASE`, `PG_USER`, `PG_PASSWORD` | `pressgres`, `pressgres`, empty | Connection |
| `WP_HOME` | `http://localhost:58080` | Also used as `WP_SITEURL` |
| `PRESSGRES_QUERY_LOG` | `wp-content/pressgres-query-log.jsonl` | JSON-lines log of every statement (original SQL, SQL sent, rules, status, error, caller, REST request) |
| `PRESSGRES_PHASE` | `unknown` | Free-form label written to each log line (e.g. `phpunit`) |

## Compose names and ports (do not reuse)

R-003 uses compose project `pressgres-r003`, services `db` / `web` / `php`, host ports `55433` (PG) and `58080` (web). Use a different project name and ports for your own stack (e.g. `pressgres-r009`, `55434`, `58081`) so both can run at once.

## Things that will bite a PHPUnit baseline (R-009)

- The schema is not created by WordPress: `wp_install()`, `dbDelta()` and the PHPUnit installer (`tests/phpunit/includes/install.php`) issue MySQL DDL that the adapter rejects (statement allow-list is `SELECT`/`INSERT`/`UPDATE`/`DELETE`/transaction control). You need your own schema bootstrap or an expected-failure classification for every DDL statement.
- The PHPUnit base class issues `SET autocommit = 0;` and `START TRANSACTION;` (`tests/phpunit/includes/abstract-testcase.php:496-497`), `ROLLBACK` (`:173`), rewrites `CREATE TABLE`/`DROP TABLE` to `TEMPORARY` variants (`:517-537`), and `utils.php:545` runs `SHOW TABLES;`. This adapter allows `START`/`COMMIT`/`ROLLBACK` but rejects `SET`, `SHOW` and all DDL, so extend the allow-list in your copy (and log what you add).
- `REPLACE`, `INSERT IGNORE`, `ON DUPLICATE KEY` (except the `wp_options` upsert), MySQL functions (`IF`, `FIELD`, `GROUP_CONCAT`, `DATE_FORMAT`, ...), SQL comments and double-quoted string literals fail closed with status `unsupported`; grep the query log for `"status":"unsupported"`.
- Any integer reaching a `uuid` column through `insert()`/`update()`/`delete()` is rejected (`non-UUID value for uuid column ...`). Tests that hard-code or cast numeric IDs (`get_post( 1 )`, `(int)` on factory results, `assertSame( 1, ... )`, etc.) will fail by design, and core paths outside this one flow are unpatched.
- `rows_affected` for `UPDATE` is PostgreSQL's matched-row count, not MySQL's changed-row count.
- Datetime columns are `varchar(19)`; the zero date `0000-00-00 00:00:00` is stored literally.
- `db_version()` reports `8.0` so core feature gates pass; `is_mysql` is `false`, which disables WordPress's charset/invalid-text stripping.
