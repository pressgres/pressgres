# Core PHPUnit harness (R-009)

Runs the upstream `wordpress-develop` 7.1.5 PHPUnit suite (single site, default groups from `phpunit.xml.dist`) in disposable containers against either:

- **MySQL 8.4.13** — the control run on stock WordPress, used to separate environmental failures from PostgreSQL ones;
- **PostgreSQL 18.6** — a Pressgres `db.php` prototype (for example the R-003 prototype) wired into the test bootstrap.

It produces JUnit XML plus CSV summaries per test directory, per `@group`, per failing test and per normalized failure signature. Report and numbers: `docs/research/R-009-core-phpunit-baseline.md`.

No WordPress or Composer vendor code is committed. The pinned source tree is mounted read-only and copied into the Docker volume `pressgres-r009_wpdev`; PHPUnit lives in the image under `/srv/wp-test-tools`.

## Pinned components

| Component | Pin |
|---|---|
| Runner base image | `php:8.4.28-cli-bookworm` with gd (jpeg/webp/avif/freetype), mysqli, pdo_mysql, pgsql, pdo_pgsql, intl, zip, exif, bcmath, opcache, imagick 3.8.0 |
| Composer | `composer:2.11.2` (copied into the runner image) |
| PHPUnit / polyfills | `phpunit/phpunit` 9.6.39, `yoast/phpunit-polyfills` 1.1.5 (`composer.lock` in this directory) |
| MySQL control | `mysql:8.4.13` (tmpfs datadir, `innodb-flush-log-at-trx-commit=2`) |
| PostgreSQL | `postgres:18.6-alpine` (tmpfs datadir, `fsync=off`) |
| WordPress | `wordpress-develop` 7.1.5 checkout (`WP_DEVELOP_REF`) |

Compose project name `pressgres-r009`; host ports bound to `127.0.0.1` only: MySQL `53307`, PostgreSQL `55434`.

## Commands

```bash
cd tools/core-phpunit
export WP_DEVELOP_REF=/path/to/reference/wordpress-develop-7.1.5   # default: ../../../../reference/wordpress-develop-7.1.5

./run.sh build                       # build runner image (needs network once for apt/pecl/composer)
./run.sh prepare                     # rsync reference -> wpdev volume, install wp-tests-config.php

# MySQL control, full default suite (both testsuites: default + restapi-autosave)
./run.sh test mysql mysql-control-final

# PostgreSQL prototype runs; PG_PROTOTYPE_DIR is mounted read-only at /prototype.
# Use a snapshot copy so the prototype cannot change between runs.
export PG_PROTOTYPE_DIR=/path/to/snapshot/of/R-003/prototypes/r-003
R009_PG_SHIM=0 R009_PG_SCHEMA=none ./run.sh test pgsql pgsql-raw              # A: prototype verbatim
./run.sh prepare && PRESSGRES_QUERY_LOG=/dev/null ./run.sh test pgsql pgsql-full         # B: wrapper + schema
./run.sh prepare && PRESSGRES_QUERY_LOG=/dev/null \
  ./run.sh test pgsql pgsql-noleak --filter '/^(?!Tests_Admin_IncludesSchema::)/'        # C: B minus leaking class

# Any extra arguments go to PHPUnit, e.g. a subset:
./run.sh test pgsql pgsql-option --group option

./run.sh down                        # stop containers, remove volumes
```

Always run `prepare` before a run that follows a PostgreSQL run: `pg-wire.sh` applies the prototype's core patch to `src/` in the volume.

`run.sh test` writes `results/<label>/` (gitignored): `junit.xml`, `phpunit.log`, `meta.env` (DB version, wall-clock duration, exit code, PostgreSQL wiring), `php-version.txt`, and for PostgreSQL `r009-shim.log` (every statement the wrapper neutralised) and the prototype query log unless `PRESSGRES_QUERY_LOG=/dev/null` (recommended for full runs: the log grows to gigabytes).

### PostgreSQL wiring

`config/pg-wire.sh` runs inside the runner before PHPUnit:

1. resets the database (`DROP SCHEMA public CASCADE`) and checks `uuidv7()`;
2. applies `patches/*.patch` from the prototype directory to the disposable `src/`;
3. with `R009_PG_SHIM=1` (default) installs the prototype as `src/wp-content/pressgres-prototype-db.php` behind `config/r009-db-wrapper.php`; with `0` installs it verbatim as `db.php`;
4. with `R009_PG_SCHEMA=prototype` (default) loads the prototype's `sql/01-schema.sql` with `wp_` replaced by `wptests_`.

The wrapper is test-harness code only. It no-ops `SET autocommit|default_storage_engine|foreign_key_checks`, maps `SHOW TABLES` to `pg_tables`, and, only inside `tests/phpunit/includes/install.php`, no-ops `DROP/CREATE/ALTER TABLE`, `DESCRIBE` and `SHOW`. Everything else reaches the prototype unchanged.

`config/php.ini` sends `error_log()` to `/tmp/php-error.log`. With the CLI default (stderr), `@runInSeparateProcess` tests deadlocked PHPUnit 9 when the adapter printed thousands of errors.

## Summaries

```bash
D=../../docs/research/data
python3 summarize.py results/mysql-control-final/junit.xml --label mysql-control --src "$WP_DEVELOP_REF" \
  --dir-csv $D/R-009-mysql-by-directory.csv --group-csv $D/R-009-mysql-by-group.csv \
  --fail-csv $D/R-009-mysql-failures.csv

python3 summarize.py results/pgsql-noleak/junit.xml --label pgsql-C --src "$WP_DEVELOP_REF" \
  --control-junit results/mysql-control-final/junit.xml \
  --compare-csv $D/R-009-pgsql-vs-mysql-by-directory.csv \
  --dir-csv $D/R-009-pgsql-by-directory.csv --group-csv $D/R-009-pgsql-by-group.csv \
  --baseline $D/R-009-mysql-failures.csv \
  --fail-csv results/pgsql-noleak/failures.csv --sig-csv $D/R-009-pgsql-signatures.csv
```

Output: overall counts (`tests pass failure error skipped warnings pass_rate pass_rate_excl_skipped test_seconds`); with `--control-junit` the *comparable pass rate* (control-passing test IDs that also pass here); with `--fail-csv`/`--sig-csv` the bucket counts. `--baseline` marks tests that also fail in the MySQL control as `harness/environment`. Buckets (`uuid-identity`, `sql-dialect`, `schema/ddl`, `harness/environment`, `unknown`) come from regex rules over the first database error in each failure (`BUCKET_RULES`); `bucket_inferred` lets an `unknown` test inherit its class's most common bucket. See the report for the measured accuracy.

PHPUnit 9 can write characters that XML 1.0 forbids (for example U+FFFE) into JUnit; `summarize.py` strips them before parsing.

## Known environmental differences from upstream CI

- The pinned reference is a source checkout without the npm/Grunt build (`src/wp-includes/js/` is absent), so tests depending on built JS/CSS assets fail identically on both databases.
- No memcached, no Xdebug, no network-dependent groups (`external-http` is excluded by `phpunit.xml.dist`).
- No per-test timeout: set a job-level timeout in CI.
