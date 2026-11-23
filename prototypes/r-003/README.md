# R-003 prototype: UUIDv7 primary keys through a minimal `$wpdb` adapter

**Throwaway research code** for issue pressgres/pressgres#5 (R-003). It proves that one WordPress 7.1.5 flow (create and read a post through PHP APIs and through `POST/GET /wp/v2/posts`) can run on PostgreSQL 18 with `uuid DEFAULT uuidv7()` primary keys, and records exactly what had to change. It is **not** the D-001/D-002 adapter, **not** a SQL translator (Q-001) and **not** a supported install path. Findings: [`docs/research/R-003-uuid-prototype.md`](../../docs/research/R-003-uuid-prototype.md).

## Requirements

- Docker with Compose v2 (tested: Docker 29.8.2, linux/arm64 on Apple Silicon).
- The pinned, read-only WordPress source at `../../../../reference/wordpress-develop-7.1.5` (override with `WP_SRC=/path/to/wordpress-develop-7.1.5/src`). The script refuses any other version.
- Images: `postgres:18.6-alpine`, `php:8.4.27-cli-alpine` (the PHP image is extended with `pdo_pgsql`, see [`docker/php/Dockerfile`](docker/php/Dockerfile); building it needs network access for `apk`).
- Free host ports `55433` (PostgreSQL) and `58080` (WordPress); override with `R003_PG_PORT` / `R003_WEB_PORT`.

## Run

```sh
cd prototypes/r-003
./run.sh all     # down -v, copy+patch WordPress, start db+web, setup, demos, query-log summary
./run.sh down    # stop and remove containers + volume (always do this afterwards)
```

`./run.sh all` exits non-zero if any check fails. Individual steps: `prepare`, `up`, `setup`, `demo`, `summary`, `down`. A baseline run **without** the core patch (shows the failures) is `R003_NO_PATCH=1 ./run.sh all`.

Developer loop used to discover the patch set: edit files under `build/wordpress/` directly, then `./run.sh iterate` (fresh database, no re-copy) and `./run.sh mkpatch` (regenerates `patches/wordpress-7.1.5-r003-uuid.patch` from `build/wordpress-pristine` vs `build/wordpress`).

## What it does

1. `prepare` copies `src/` of the pinned WordPress into `build/wordpress` (gitignored), copies `_index.php` to `index.php` (what the wordpress-develop build does), applies `patches/*.patch` with `patch -p1`, and installs [`wordpress/db.php`](wordpress/db.php) and [`wordpress/wp-config.php`](wordpress/wp-config.php).
2. `up` starts `db` (PostgreSQL 18.6; [`sql/01-schema.sql`](sql/01-schema.sql) and [`sql/02-seed-options.sql`](sql/02-seed-options.sql) run as init scripts) and `web` (`php -S` serving `build/wordpress`).
3. `setup` ([`scripts/setup.php`](scripts/setup.php)) uses WordPress APIs to run `populate_roles()`, `wp_insert_user()`, `wp_insert_term()` (default category) and `WP_Application_Passwords::create_new_application_password()`.
4. `demo` runs [`scripts/demo-php.php`](scripts/demo-php.php) (`wp_insert_post()` / `get_post()`) and [`scripts/demo-rest.php`](scripts/demo-rest.php) (`GET /wp/v2/users/me`, `POST /wp/v2/posts`, `GET /wp/v2/posts/<uuid>` against `web`, HTTP Basic with the application password). Both verify the stored row with an independent PDO connection (`uuid_extract_version("ID") = 7`).
5. `summary` ([`scripts/query-log-summary.php`](scripts/query-log-summary.php)) aggregates `build/logs/query-log.jsonl` into per-phase counts and `build/logs/query-fingerprints.csv`.

## Files

| Path | Purpose |
|---|---|
| `docker-compose.yml` | Project `pressgres-r003`; services `db`, `web`, `php` (profile `tools`, one-shot CLI) |
| `sql/01-schema.sql` | Minimal native schema: options, users, usermeta, posts, postmeta, terms, term_taxonomy, term_relationships, termmeta |
| `sql/02-seed-options.sql` | Minimum options to boot without the MySQL-only installer |
| `wordpress/db.php` | Prototype `wpdb` subclass (PDO pgsql, allow-list, `INSERT ... RETURNING`, JSON-lines query log) |
| `wordpress/wp-config.php` | Env-driven config; `WP_ENVIRONMENT_TYPE=local` so application passwords work over HTTP |
| `patches/wordpress-7.1.5-r003-uuid.patch` | Minimum core patch for this flow (13 files) |
| `scripts/*.php` | Setup, demos, log summary |
| `build/` | Generated: WordPress copy, logs, `state.json` (contains the throwaway application password) |

All credentials in this directory are fixed, public, throwaway test values.
