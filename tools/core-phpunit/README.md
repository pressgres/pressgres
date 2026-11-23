# Core PHPUnit harness (R-009, I-010)

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

Base images are pinned by tag and multi-arch index digest in `Dockerfile` and `compose.yaml`.
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

## CI (I-010)

Workflow: `.github/workflows/core-phpunit.yml`. Triggers: pull requests touching `tools/core-phpunit/**`, `prototypes/**`, `patches/**`, `packages/**` or the workflow itself; pushes to `main` on the same paths; weekly schedule; `workflow_dispatch`.

| Job | When | What |
|---|---|---|
| `ratchet-unit` | always | `python3 -m unittest discover -s tools/core-phpunit/tests` (fixture JUnit files under `tests/fixtures/`) |
| `pgsql` | always | PG-C: PostgreSQL 18.6 + R-003 prototype (`prototypes/r-003`) behind the harness wrapper, prototype schema pre-created, `Tests_Admin_IncludesSchema` excluded. Gate: the ratchet |
| `mysql-control` | weekly schedule, or `workflow_dispatch` with `mysql_control: true` | MySQL 8.4.13 on stock WordPress, checked against `baseline/mysql-control-pass.txt` to detect environmental drift |

`pgsql` steps: checkout; fetch `wordpress-develop` tag `7.1.5` shallowly and fail unless it resolves to `984163c92ef66b6186538ecf01bacb97fc097541`; build the runner image (GitHub Actions cache); `run.sh prepare`; `run.sh test pgsql pgsql-c --filter '/^(?!Tests_Admin_IncludesSchema::)/'` with a 30 min step timeout; `summarize.py` CSVs; `ratchet.py check`, which writes the job summary; upload artifact `core-phpunit-pgsql` (90 days); `run.sh down`.

Artifact `core-phpunit-pgsql`: `junit.xml.gz`, `phpunit.log.gz`, `meta.env.gz`, `r009-shim.log.gz`, `by-directory.csv`, `by-group.csv`, `failures.csv`, `signatures.csv`, `run-summary.csv` (one trend row), `newly-passing.txt`, `regressions.txt`, `expected-pass.candidate.txt`, `baseline.candidate.json`.

### The ratchet is the gate, the pass rate is a trend

Per ADR-0006 and R-009, CI fails on regressions, not below a percentage. `ratchet.py check` (stdlib only) fails when:

1. the bootstrap did not reach PHPUnit: no JUnit file, invalid XML or 0 test cases (PG-A style). The job summary shows the tail of `phpunit.log`;
2. the JUnit test count is more than 1 % below `baseline/baseline.json` `tests` (data-provider or fatal collapse);
3. any ID in `baseline/expected-pass.txt` is not passing: failure, error, skipped or missing.

Newly passing tests never fail the job. They are listed in the job summary and in `newly-passing.txt`. IDs in `baseline/flaky.txt` (tests shown to be nondeterministic, each with its evidence) are ignored in both directions.

The job summary also reports pass/failure/error/skipped counts, the pass rate and the *comparable pass rate*: IDs passing on PostgreSQL divided by IDs passing in the MySQL control (`baseline/mysql-control-pass.txt`), each with the delta to `baseline/baseline.json`. On `main` these numbers (artifact `run-summary.csv`) are the published trend; they are not a threshold.

Committed baseline (generated 2026-11-23 from two local PG-C runs and one MySQL control run on the pinned stack, Docker linux/aarch64):

| Run | Tests (JUnit) | Pass | Failure | Error | Skipped | Pass rate | Comparable pass rate | Wall time |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| PG-C run 1 | 30 452 | 23 928 | 3 105 | 2 976 | 443 | 78.58 % | 77.47 % (23 861 / 30 801) | 550 s |
| PG-C run 2 | 30 452 | 23 929 | 3 104 | 2 976 | 443 | 78.58 % | 77.47 % (23 862 / 30 801) | 497 s |
| MySQL control | 30 900 | 30 868 | 1 | 0 | 31 | 99.90 % | 100 % | 450 s |

These match R-009 exactly (same inputs: wordpress-develop `984163c`, R-003 hashes `2310bf9a…`/`ba580154…`/`d1ef3189…`). The only difference between the two PostgreSQL runs is `WP_Navigation_Fallback_Test::test_should_return_the_most_recently_created_navigation_menu` (two posts created in the same second, tie order not deterministic), now in `flaky.txt`. `expected-pass.txt` holds the 23 861 IDs passing in both runs. Wall times are higher than R-009's 375 s / 335 s because the host ran other containers.

Baseline files (`baseline/`):

| File | Content |
|---|---|
| `expected-pass.txt` | sorted `Class::name` IDs (as in JUnit, data-set names included; `\`, newline and CR escaped) that passed in every local generating run |
| `baseline.json` | counts of the generating run, `comparable_pass_rate`, inputs (wordpress-develop commit, prototype hashes, images) |
| `mysql-control-pass.txt`, `mysql-control.json` | the same for the MySQL control |
| `flaky.txt` | IDs excluded from the ratchet, with a comment line per reason |

An ID that occurs more than once (the `restapi-autosave` testsuite re-runs some tests) passes only if every occurrence passes.

### Updating the baseline in the same PR

When a change makes tests pass, ratchet them in the same PR:

```bash
# Either: download artifact core-phpunit-pgsql from the PR run and copy
cp expected-pass.candidate.txt tools/core-phpunit/baseline/expected-pass.txt
cp baseline.candidate.json     tools/core-phpunit/baseline/baseline.json

# Or: run the CI configuration locally and regenerate (several JUnit files = intersection of passing IDs)
cd tools/core-phpunit && ./run.sh prepare && PG_PROTOTYPE_DIR=$PWD/../../prototypes/r-003 PRESSGRES_QUERY_LOG=/dev/null \
  ./run.sh test pgsql pgsql-c --filter '/^(?!Tests_Admin_IncludesSchema::)/' && cd ../..
python3 tools/core-phpunit/ratchet.py update tools/core-phpunit/results/pgsql-c/junit.xml
python3 tools/core-phpunit/ratchet.py update --merge results/a/junit.xml   # only add, never remove
```

Removing IDs (a deliberate regression, or a test deleted upstream after a WordPress update) is the same command without `--merge`; the diff of `expected-pass.txt` shows it for review. Check locally before pushing:

```bash
python3 tools/core-phpunit/ratchet.py check tools/core-phpunit/results/pgsql-c/junit.xml
```

### MySQL control

Running MySQL on every PR would double the cost for a number that only changes with the environment, so the comparable pass rate uses the committed `mysql-control-pass.txt`. The weekly `mysql-control` job re-runs the control and ratchets it against that list; a failure there means the environment drifted (image, runner, upstream fetch) and blocks interpreting PostgreSQL deltas until fixed.

## Known environmental differences from upstream CI

- The pinned reference is a source checkout without the npm/Grunt build (`src/wp-includes/js/` is absent), so tests depending on built JS/CSS assets fail identically on both databases.
- No memcached, no Xdebug, no network-dependent groups (`external-http` is excluded by `phpunit.xml.dist`).
- No per-test timeout: set a job-level timeout in CI.
