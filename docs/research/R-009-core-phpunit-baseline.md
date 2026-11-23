# R-009 — WordPress core PHPUnit baseline on PostgreSQL

**Issue:** pressgres/pressgres#9 · **Status:** research spike, evidence only · **Date:** 2026-11-22/23 · **Confidence:** high for counts (from real runs), medium for failure bucketing (regex heuristic, see [Triage](#triage-of-postgresql-failures)).

The upstream `wordpress-develop` PHPUnit suite is the project's primary objective compatibility metric (`docs/08-roadmap.md` R-009, I-010). This spike builds a reproducible harness, measures an environment baseline on MySQL, and measures the R-003 PostgreSQL 18 prototype against the same suite.

## Headline numbers

| Run | Database | Tests (JUnit) | Pass | Pass rate | Comparable pass rate¹ | Wall time |
|---|---|---|---|---|---|---|
| MySQL control | MySQL 8.4.13 | 30 900 | 30 868 | 99.90 % (100.00 % of non-skipped) | 100.00 % | 335 s |
| PG-A: R-003 `db.php` verbatim, stock test installer | PostgreSQL 18.6 | 0 | 0 | **0 %** — bootstrap aborts | 0 % | 1 s |
| PG-B: R-003 + harness wrapper + pre-created prototype schema | PostgreSQL 18.6 | 30 461 | 637 | 2.09 % | 2.07 % | 838 s |
| PG-C: as B, excluding the one class that leaks global state | PostgreSQL 18.6 | 30 452 | 23 928 | 78.58 % | **77.47 %** | 375 s |

¹ Comparable pass rate = tests (by `Class::method` ID) that pass on the MySQL control **and** on PostgreSQL, divided by the 30 801 distinct test IDs that pass on MySQL. It is the number I-010 should trend. It is inflated by DB-agnostic tests: the 26 directories at 100 % (`wp-token-map`, `html-api`, `unicode`, `block-supports`, …) hold 10 136 of the 30 801 tests; excluding them, the comparable rate is 13 725 / 20 665 = 66.4 %.

**The honest R-009 baseline for "R-003 prototype as delivered" is 0 %** (PG-A): the upstream bootstrap cannot install WordPress through an adapter that rejects DDL. PG-C is the most informative number: it shows how far a UUID-only adapter gets once the test-infrastructure statements are neutralised, and where it breaks.

## Scope and assumptions

- **WordPress:** `wordpress-develop` 7.1.5 source checkout (read-only reference), single site, default `phpunit.xml.dist` configuration. Excluded groups per `wordpress-develop-7.1.5/phpunit.xml.dist:28-32`: `ajax`, `ms-files`, `ms-required`, `external-http`, `html-api-web-platform-tests`. Both testsuites (`default` and `restapi-autosave`) run. Multisite (`tests/phpunit/multisite.xml`) is out of scope.
- **PostgreSQL candidate:** the R-003 prototype (`worktrees/R-003/prototypes/r-003`, read from its `HANDOFF.md`), snapshot taken 2026-11-22 22:22 UTC with sha256 `2310bf9a…` (`wordpress/db.php`), `ba580154…` (`patches/wordpress-7.1.5-r003-uuid.patch`), `d1ef3189…` (`sql/01-schema.sql`). It is throwaway research code with a SELECT/INSERT/UPDATE/DELETE allow-list, 9 tables, UUIDv7 keys, no DDL; it was **never designed to pass the suite**. The numbers below measure distance from the target, not the quality of R-003.
- **UUID-only:** no dual IDs. Tests that assume integer IDs fail by design until the patchset (D-001/D-002) addresses them.
- **Not changed:** no upstream file is modified in the reference tree; the harness works on a disposable copy inside a Docker volume. The only core change applied is R-003's own prototype patch, applied to that copy for PostgreSQL runs.

## Harness

Location: `tools/core-phpunit/` (README has exact commands).

| Component | Pin |
|---|---|
| Runner | `php:8.4.28-cli-bookworm` + gd (jpeg/webp/avif/freetype), mysqli, pdo_mysql, pgsql, pdo_pgsql, intl, zip, exif, bcmath, opcache, imagick 3.8.0, ghostscript |
| Composer | `composer:2.11.2` |
| PHPUnit | `phpunit/phpunit` 9.6.39 + `yoast/phpunit-polyfills` 1.1.5 (`tools/core-phpunit/composer.lock`), installed at `/srv/wp-test-tools`, outside the WordPress tree |
| MySQL | `mysql:8.4.13` (reports `8.4.13`), tmpfs datadir |
| PostgreSQL | `postgres:18.6-alpine` (reports `18.6`, `uuid_extract_version(uuidv7()) = 7`), tmpfs datadir, `fsync=off` |
| Host | Docker 29.8.2 / Compose v5.5.0, linux/aarch64 VM on Apple Silicon (10 vCPU, 7.8 GiB) |

Compose project `pressgres-r009`; host ports `127.0.0.1:53307` (MySQL) and `127.0.0.1:55434` (PostgreSQL).

Flow (`tools/core-phpunit/run.sh`):

1. `build` — runner image.
2. `prepare` — `rsync` the reference tree (minus `node_modules`, `vendor`, `.git`) into volume `pressgres-r009_wpdev` at `/srv/wordpress-develop`, add the harness `wp-tests-config.php` (DB settings from environment).
3. `test <mysql|pgsql> <label> [phpunit args]` — start the DB service, optionally wire the PostgreSQL prototype (`config/pg-wire.sh`), run `phpunit -c phpunit.xml.dist --log-junit …`, write `results/<label>/{junit.xml,phpunit.log,meta.env}` (gitignored; raw JUnit is 9 MB for MySQL, 40–353 MB for PostgreSQL because failures embed captured output).
4. `summarize.py` — counts overall, per test directory, per class-level `@group`, per failing test, per normalized failure signature, plus a *comparable pass rate* against the MySQL control (same test IDs).

### Harness fixes needed for a clean MySQL control

The first control run had 3 failures, all environmental; two were fixed in the harness (not in WordPress), one is documented:

| Failure | Cause | Fix |
|---|---|---|
| `Tests_Admin_WpAutomaticUpdater::test_is_allowed_dir_*open_basedir*` | Tree at `/wp` made the allowed directory `dirname(ABSPATH, 2)` equal `/`, so the assertion failed; after moving the tree to `/srv`, PHPUnit at `/opt` was outside the test's `open_basedir` and both `open_basedir` tests' child processes died | Tree at `/srv/wordpress-develop`, PHPUnit at `/srv/wp-test-tools` |
| `Tests_Image_Editor_Imagick::test_remove_pdf_alpha_channel_*` | No Ghostscript; Debian ImageMagick policy blocks PDF | Install `ghostscript`, drop the PDF policy line |
| `Tests_Script_Modules_WpScriptModules::test_default_script_module_files_exist` | Reference tree is an unbuilt source checkout (`src/wp-includes/js/` absent) | **Not fixed**: needs `npm ci && npm run build:dev`; recorded as the single environmental exclusion |

A fourth harness change came from PostgreSQL: `wpdb::print_error()` calls `error_log()`, which in the CLI defaults to stderr. With thousands of adapter errors, a test using `@runInSeparateProcess` filled the stderr pipe while PHPUnit 9 was blocked reading stdout, and the run deadlocked at test 21 299 of 30 900 (observed: parent in `anon_pipe_read`, child in `anon_pipe_write`, PostgreSQL idle). The runner now sets `error_log = /tmp/php-error.log` (`tools/core-phpunit/config/php.ini`). The final MySQL control was re-run with that setting.

## MySQL control run

Final run `mysql-control` (2026-11-22 23:06:50 UTC), PHP 8.4.28, PHPUnit 9.6.39, MySQL 8.4.13:

```text
Time: 05:32.019, Memory: 492.93 MB
Tests: 30900, Assertions: 4559045, Failures: 1, Warnings: 86, Skipped: 31.
```

- **1 failure**, environmental: `Tests_Script_Modules_WpScriptModules::test_default_script_module_files_exist` (unbuilt `src/wp-includes/js/dist/`). It is excluded from the PostgreSQL comparison (`--baseline docs/research/data/R-009-mysql-failures.csv` marks it `harness/environment`).
- **31 skipped**: test-declared preconditions (no AVIF/HEIC encoder, MariaDB-only, multisite-only, external object cache, etc.); listed in the JUnit.
- **86 warnings**: all PHPUnit 9 deprecation notices of the form `Expecting E_* is deprecated and will no longer be possible in PHPUnit 10`; they do not fail tests.
- Reproducibility: three earlier full runs gave 30 900 tests with 3 → 3 → 1 failures as the harness fixes above landed; the last two runs (before and after the `error_log` change) are identical (1 failure, 31 skipped).
- Per-directory and per-group counts: `docs/research/data/R-009-mysql-by-directory.csv`, `R-009-mysql-by-group.csv`.

## PostgreSQL runs

All three runs use the same runner image, PostgreSQL 18.6, and the R-003 snapshot named above, with R-003's core patch applied to the disposable `src/` copy (`config/pg-wire.sh`). The PostgreSQL database is reset (`DROP SCHEMA public CASCADE`) before each run.

### PG-A — prototype verbatim: fails in the bootstrap (0 %)

`R009_PG_SHIM=0 R009_PG_SCHEMA=none ./run.sh test pgsql pgsql-raw`. `tests/phpunit/includes/bootstrap.php:261` runs `install.php` in a subprocess; it exits **255** and the bootstrap exits before PHPUnit loads a single test.

Sequence from the R-003 query log (253 statements, `results/pgsql-raw/pressgres-query-log.jsonl`):

1. First query: `SELECT option_value FROM wptests_options WHERE option_name = 'siteurl'` (from `wp_not_installed()` → `is_blog_installed()`) → `SQLSTATE[42P01] relation "wptests_options" does not exist`.
2. **First statement rejected by the adapter:** `SET default_storage_engine = InnoDB` (`install.php:57`) → `unsupported: statement type 'SET' not in allow-list`; then `SET foreign_key_checks = 0` and 18 × `DROP TABLE IF EXISTS …` (`install.php:65-80`) rejected.
3. `wp_install()` → `make_db_current_silent()` → `dbDelta()`: 36 × `DESCRIBE` and 12 × `CREATE TABLE` rejected, so no table exists.
4. `populate_options()`: 174 statements fail on the missing `wptests_options`; one `REGEXP` and two multi-table `DELETE a, b FROM …` (`delete_expired_transients()`) fail.
5. **Fatal point:** `wp_install()` → `wp_create_user()` → `wp_insert_user()` → `$wpdb->insert( wptests_users … )` → `unsupported: unknown column wptests_users.user_pass` (the adapter's catalog has no such table) → `wp_die()` → exit 255.

### PG-B — with the harness wrapper and pre-created schema (2.07 %)

`./run.sh test pgsql pgsql-full` (defaults: `R009_PG_SHIM=1`, `R009_PG_SCHEMA=prototype`). The wrapper (`config/r009-db-wrapper.php`) no-ops only test-infrastructure statements and logs each one: 3 048 install-time DDL statements (72 installer runs — the bootstrap plus each `@runInSeparateProcess` child — × 18 `DROP`, 12 `CREATE TABLE`, plus `DESCRIBE`s) and 29 661 `SET` statements in run B. `pg-wire.sh` pre-creates R-003's 9 tables with the `wptests_` prefix. No comments, commentmeta or links tables exist.

```text
Time: 13:50.806, Memory: 3.01 GB
Tests: 30907, Assertions: 4528615, Errors: 3620, Failures: 4103, Warnings: 81, Skipped: 500, Risky: 21601.
```

21 413 of 29 324 failing tests share one signature, `relation "testprefix_options" does not exist`. Root cause: `Tests_Admin_IncludesSchema::test_populate_options` (`tests/phpunit/tests/admin/includesSchema.php:94-111`) points `$wpdb->options` at `testprefix_options`, whose `CREATE TABLE` the adapter rejected; a deprecation (`rtrim(null)` at `src/wp-admin/includes/upgrade.php:2883`) is converted to an exception before the test restores `$wpdb->options`, and **every later test in the run uses the wrong options table**. This is one schema/ddl failure amplified by a test-isolation assumption, so the 2 % figure says little about the adapter.

### PG-C — as B, excluding `Tests_Admin_IncludesSchema` (77.47 % comparable)

`./run.sh test pgsql pgsql-noleak --filter '/^(?!Tests_Admin_IncludesSchema::)/'` (excludes 9 tests).

```text
Time: 06:11.224, Memory: 712.00 MB
Tests: 30898, Assertions: 4538637, Errors: 2248, Failures: 3105, Warnings: 86, Skipped: 443, Risky: 728.
```

JUnit: 30 452 test cases, 23 928 pass, 3 105 failures, 2 976 errors (762 of them `OutputError`, i.e. printed database errors), 443 skipped. The console count (30 898) is higher than the JUnit count because PHPUnit reports a data provider that errors as one test; 521 control test IDs are missing from the PostgreSQL JUnit for that reason, and they count as not passing.

Comparable pass rate by directory (largest first, full table in `docs/research/data/R-009-pgsql-vs-mysql-by-directory.csv`):

| Directory | Passing on MySQL | Also passing on PG | Rate |
|---|---|---|---|
| `wp-token-map` | 4 474 | 4 474 | 100.00 % |
| `(root)` (`tests/*.php`) | 3 367 | 2 242 | 66.59 % |
| `rest-api` | 3 080 | 1 704 | 55.32 % |
| `html-api` | 1 713 | 1 713 | 100.00 % |
| `formatting` | 1 667 | 1 654 | 99.22 % |
| `user` | 1 060 | 856 | 80.75 % |
| `canonical` | 971 | 148 | 15.24 % |
| `admin` | 885 | 714 | 80.68 % |
| `query` | 800 | 157 | 19.62 % |
| `post` | 778 | 318 | 40.87 % |
| `term` | 611 | 240 | 39.28 % |
| `comment` | 491 | 115 | 23.42 % |
| `xmlrpc` | 330 | 159 | 48.18 % |
| `privacy` | 150 | 50 | 33.33 % |
| `db` | 141 | 12 | 8.51 % |

## Harness assumptions that break on PostgreSQL

Each item is test-infrastructure behaviour, independent of the code under test. Line references are relative to `wordpress-develop-7.1.5/`.

| # | Assumption | Where | Effect with the R-003 prototype | Handling in this spike |
|---|---|---|---|---|
| 1 | Installer drops and recreates tables with MySQL DDL via `wp_install()`/`dbDelta()` | `tests/phpunit/includes/install.php:57-80`, `bootstrap.php:261` | Statement allow-list rejects `SET`, `DROP`, `DESCRIBE`, `CREATE`; `wp_insert_user()` then fails on the missing table and `install.php` exits 255 | Variant A measures this. Variants B/C pre-create the prototype schema and no-op install-time DDL (`config/r009-db-wrapper.php`, every no-op logged) |
| 2 | `SET autocommit = 0; START TRANSACTION;` per test, `ROLLBACK` in tear-down | `tests/phpunit/includes/abstract-testcase.php:496-497,173` | `SET` rejected; `START TRANSACTION`/`ROLLBACK` work | `SET autocommit` no-op'd by the wrapper (29 445 calls in run B) |
| 3 | A failed statement leaves the transaction usable (MySQL) | implicit in every test | PostgreSQL aborts the whole transaction (`SQLSTATE 25P02`); every later query in the test fails until `ROLLBACK` | Not shimmed; it is real behaviour the adapter must handle (per-statement `SAVEPOINT` or fail-fast) |
| 4 | Fixed integer IDs: admin user `ID = 1`, *Uncategorized* `term_id = 1`; clean-up uses `WHERE ID != 1`, `term_id != 1` | `tests/phpunit/includes/functions.php:130-136` | `operator does not exist: uuid <> integer`; data is **never cleaned** between classes, so state accumulates | Not shimmed; needs a UUID-aware test-support patch (keep the admin/default-term UUIDs from install) |
| 5 | `SHOW TABLES` for clean-up | `tests/phpunit/includes/utils.php:545` | Rejected | Wrapper maps it to `pg_tables` |
| 6 | `CREATE TABLE`/`DROP TABLE` rewritten to `TEMPORARY` inside tests | `tests/phpunit/includes/abstract-testcase.php:517-537` | DDL rejected | Not shimmed |
| 7 | Tests mutate global `$wpdb` state and restore it at the end of the test body | e.g. `tests/phpunit/tests/admin/includesSchema.php:94-111` | An exception before the restore leaks `$wpdb->options = 'testprefix_options'` into **every later test** | Variant C excludes that one class to measure without the cascade |
| 8 | Every `@runInSeparateProcess` test re-runs `install.php` | `tests/phpunit/includes/bootstrap.php:257-264` | 72 installer runs per suite run; with pre-created tables and no-op DDL they no longer start from a clean schema | Documented; a real installer must make reinstall idempotent |
| 9 | Database errors are printed (`show_errors = true`) and printed output fails a test (`beStrictAboutOutputDuringTests`, `failOnRisky`) | `abstract-testcase.php:71-72`, `phpunit.xml.dist:7-9` | Any adapter error anywhere in a test fails it as `OutputError`; this is desirable strictness but multiplies cascades | Kept as upstream |
| 10 | `error_log()` goes to stderr | PHP CLI default | Pipe deadlock with `@runInSeparateProcess` under heavy error volume | `error_log` to a file |

## Triage of PostgreSQL failures

Run PG-C, 6 081 failing or erroring test cases (including the one control failure, tagged `harness/environment`). Buckets are assigned by `summarize.py` from the **first database error** in the failure text, falling back to the whole text (rules in `BUCKET_RULES`), and a UUIDv7 literal in an assertion message counts as `uuid-identity`. Because fixture failures in `wpSetUpBeforeClass()` print their database error only once, a second column lets an `unknown` test inherit its class's most common direct bucket.

| Bucket | Direct | Class-inferred |
|---|---|---|
| `uuid-identity` | 1 761 | 4 075 |
| `schema/ddl` | 267 | 939 |
| `sql-dialect` | 62 | 102 |
| `harness/environment` | 116 | 133 |
| `unknown` | 3 875 | 832 |
| **Total** | 6 081 | 6 081 |

Data: `docs/research/data/R-009-pgsql-buckets.csv`; every signature with counts and three example tests in `R-009-pgsql-signatures.csv` (`rank_in_bucket` ≤ 10 gives the top 10 per bucket).

**Confidence and false-positive estimate (manual sample, medium confidence).** I read 12 random failures per classified bucket and 30 random `unknown` failures (seed 9, script in Method). `schema/ddl` 12/12 correct (all missing `comments`/`links` tables). `sql-dialect` 10/12 correct (the 2 misfiled were unquoted UUIDs in `IN (…)`; the rule was then moved to `uuid-identity`). `uuid-identity` 9/12 clearly ID-related, 3 plausible but unproven (canonical feed redirects whose expected URL contains a UUID). `harness/environment` 12/12 were `current transaction is aborted` cascades, whose *root* cause is an earlier statement in the same transaction. Of the 30 `unknown`: 6 schema/ddl (missing comments table), 5 UUID-related, 3–4 data accumulation from assumption #4 (e.g. `actual size 246 matches expected size 12` in user queries), 3 the `Tests_DB` connection problem, 11 not attributable without deeper debugging. Treat bucket counts as ±20 %.

### Top signatures per bucket (PG-C)

Signatures are normalised (`<n>` numbers, `<s>` literals, `<uuid>`, `<path>`).

#### uuid-identity

| # | Count | Signature | Example |
|---|---|---|---|
| 1 | 388 | `operator does not exist: uuid = integer` | `Tests_Admin_WpListTable::test_should_only_add_primary_column_when_needed` |
| 2 | 349 | `Failed asserting that two strings are identical.` (expected URL with `p=<uuid>`) | `Tests_Canonical_PostStatus::test_canonical_redirects_to_plain_permalinks` |
| 3 | 327 | `Object of class WP_Error could not be converted to int` | `Tests_Admin_ExportWp::test_should_include_attachments` |
| 4 | 263 | `Failed asserting that two arrays are identical.` (UUIDs vs ints) | `Tests_Blocks_RenderReusableCommentTemplate::test_build_comment_query_vars_from_block_with_context` |
| 5 | 76 | `syntax error: trailing junk after numeric literal at or near "<s>"` (UUID interpolated unquoted, `IN (01a2…)`) | `Tests_Block_Template::test_page_home_block_template_takes_precedence_over_less_specific_block_templates` |
| 6 | 43 | `Failed asserting that '<s>' is of type "int".` | `Tests_Comment_WpComment::test_post_fields_should_be_null_when_the_comments_post_is_deleted` |
| 7 | 42 | `<path>:<n>` (TypeError: `int $user_id`, string given) | `Tests_Auth::test_auth_cookie_generated_with_phpass_hash_remains_valid` |
| 8 | 41 | `Failed asserting that <n> is identical to '<s>'.` | `Tests_Admin_IncludesPost::test__wp_translate_postdata_cap_checks_editor` |
| 9 | 39 | `operator does not exist: uuid <> integer` | `Tests_Editor_DisableContentEditorForNavigationPostType::test_should_not_disable` |
| 10 | 34 | `non-UUID value for uuid column wptests_posts.post_parent: int(<n>)` | `Test_WP_Customize_Custom_CSS_Setting::test_update_custom_css_updates_theme_mod` |

#### schema/ddl

| # | Count | Signature | Example |
|---|---|---|---|
| 1 | 102 | `relation "wptests_comments" does not exist` | `Tests_Admin_WpAutomaticUpdater::test_is_allowed_dir_should_return_true_if_open_basedir_is_set_and_path_is_allowed` |
| 2 | 96 | `Failed asserting that two arrays are identical.` (`Could not insert comment into the database.`) | `Tests_Comment_CommentsTemplate::test_should_respect_comment_order_asc_when_default_comments_page_is_newest` |
| 3 | 51 | `unsupported: unknown column wptests_comments.comment_post_ID` | `Tests_Blocks_Render::test_render_latest_comments_on_password_protected_post` |
| 4 | 3 | `Call to a member function prepare() on null` | `Tests_DB::test_get_table_from_query` |
| 5 | 2 | `unsupported: unknown column wptests_links.link_url` | `Tests_Bookmark_GetBookmarks::test_should_hit_cache` |
| 6–10 | 1 each | `Failed asserting that WP_Error Object … (` (comment insert) | `Tests_Comment::test_wp_new_comment_notify_postauthor_filter_*` |

Not visible as separate signatures because they are swallowed by the wrapper or by cascades: install-time `CREATE TABLE`/`DESCRIBE` (3 048 no-ops in run B) and in-test `CREATE TEMPORARY TABLE` (assumption #6).

#### sql-dialect

| # | Count | Signature | Example |
|---|---|---|---|
| 1 | 32 | `function year(character varying) does not exist` | `Tests_Blocks_Render::test_do_block_output` |
| 2 | 4 | `unsupported: MySQL-only keyword/function '<s>' not handled` | `Tests_Comment_Query::test_meta_vars_should_be_converted_to_meta_query` |
| 3 | 2 | `for SELECT DISTINCT, ORDER BY expressions must appear in select list` | `Tests_Admin_wpUserSearch::test_class_is_deprecated` |
| 4 | 2 | `syntax error at or near "<s>"` | `Tests_Comment_Query::test_cache_should_be_sensitive_to_parent__in` |
| 5 | 2 | `Failed asserting that <n> is identical to <n>.` (`SQL_CALC_FOUND_ROWS` emulation) | `Tests_Comment_Query::test_should_respect_no_found_rows_false` |
| 6 | 2 | `function rand() does not exist` | `Tests_Post_GetPages::test_get_pages_orderby` |
| 7 | 2 | `function rand(integer) does not exist` | `Tests_Post_Query::test_orderby_rand_with_seed` |
| 8 | 2 | `unsupported: SQL comments not supported` | `Tests_Query::test_posts_clauses_filter_should_receive_filtered_clauses` |
| 9 | 2 | `unterminated quoted string` (backslash escaping in serialized data) | `WP_REST_Pattern_Directory_Controller_Test::test_get_items_wdotorg_unavailable` |
| 10 | 2 | same, different payload | `WP_REST_Pattern_Directory_Controller_Test::test_get_items_invalid_response_data` |

The small dialect count is not good news: most dialect errors happen inside fixtures or after the first UUID error in a test, so they are counted under other buckets. `MONTH()`, `DAYOFMONTH()` and `HOUR()` appear further down the list (ranks 15–18).

#### harness/environment

| # | Count | Signature | Example |
|---|---|---|---|
| 1 | 105 | `SQLSTATE[25P02] current transaction is aborted, commands ignored until end of transaction block` | `Tests_Admin_IncludesMedia::test_attachment_submitbox_metadata_filesize` |
| 2 | 6 | same, printed as DB error | `Tests_Admin_wpPostsListTable::test_filter_button_should_not_be_shown_if_there_are_no_posts` |
| 3 | 3 | `Failed asserting that false is identical to '{\n` (built JS translation files missing) | `Tests_L10n_LoadScriptTextdomain::test_resolve_relative_path` |
| 4 | 1 | `file_get_contents(<path>): Failed to open stream` (built asset) | `Tests_Embed_Template::test_oembed_output_404` |
| 5 | 1 | control failure (unbuilt script module) | `Tests_Script_Modules_WpScriptModules::test_default_script_module_files_exist` |

Only 5 signatures exist in this bucket.

#### unknown (root cause not determined automatically)

| # | Count | Signature | Example | Manual note |
|---|---|---|---|---|
| 1 | 504 | `Call to a member function prepare() on null` | `Tests_DB::test_db_reconnect` | All 508 `Tests_DB` tests: the prototype's PDO handle is `null` and is never re-opened (`close()` nulls it and `check_connection()` does not reconnect, R-003 `db.php:143-160`); stock `wpdb` reconnects. Adapter gap, not dialect |
| 2 | 356 | `Failed asserting that <n> is identical to <n>.` | `Tests_Avatar::test_get_avatar_url_gravatar_url` | mixed: counts and IDs |
| 3 | 288 | `<path>:<n>` | `Admin_EditFormComment_Test::test_should_list_valid_parents_and_exclude_invalid_ones` | trace-only message |
| 4 | 266 | `Failed asserting that two strings are identical.` | `Tests_Admin_IncludesPost::test_bulk_edit_posts_should_publish_scheduled_post` | mixed |
| 5 | 236 | `Attempt to read property "ID" on null` | `Tests_Admin_wpMediaListTable::test_prepare_items_without_cron_option_does_not_throw_warning` | fixture post not created |
| 6 | 174 | `Object of class WP_Error could not be converted to string` | `Tests_Blocks_RenderReusableCommentTemplate::test_rendering_comment_template` | failed insert returned `WP_Error` |
| 7 | 141 | `The expected error code does not match.` | `Tests_REST_WpRestFontFacesController::test_get_item_invalid_font_face_id` | REST `id` route patterns are `(?P<id>[\d]+)` (e.g. `wordpress-develop-7.1.5/src/wp-includes/rest-api/endpoints/class-wp-rest-posts-controller.php:114`); likely UUID |
| 8 | 139 | `Failed asserting that two arrays are identical.` | `Tests_Admin_wpPostsListTable::test_get_views_should_return_views_by_default` | mixed |
| 9 | 109 | `Failed asserting that actual size <n> matches expected size <n>.` | `Tests_Admin_wpCommentsListTable::test_comments_list_table_does_not_show_note_comment_type` | data accumulation (assumption #4) or missing comments table |
| 10 | 107 | `Failed asserting that false is true.` | `Tests_Blocks_Register::test_has_blocks` | mixed |

## Recommendation for I-010 (CI)

Measured cost on the development host (10 vCPU Apple Silicon VM, single PHPUnit process): MySQL full suite 335 s wall, PostgreSQL PG-C 375 s, PostgreSQL PG-B 838 s (error-heavy runs print hundreds of MB of output and are 2× slower). GitHub-hosted runners are typically slower per core; budget 10–20 min for one unsharded job until measured there.

1. **Per PR: full default suite on PostgreSQL, single job, no sharding yet.** At ~6 min the whole suite is cheaper than the complexity of sharding. Job timeout 30 min (a hang is a real failure mode, see the pipe deadlock above). Upload `summary` CSVs plus gzipped JUnit; raw PostgreSQL JUnit reached 350 MB in PG-B.
2. **Gate on a ratchet, not on a percentage.** Commit an expected-pass list (test IDs passing on `main`, from `summarize.py --fail-csv` / JUnit). A PR fails if any test in that list stops passing (regression), and it prints newly passing tests so the list is updated in the same PR. Additionally fail the job if the bootstrap does not reach PHPUnit (PG-A-style 0 tests) or if the JUnit test count drops by more than 1 % (data-provider or fatal collapse). A plain percentage threshold would hide trades such as PG-B, where one leaked global turned 21 413 tests red.
3. **Trend:** record `comparable_pass_rate` (vs the MySQL control) and the bucket counts per `main` commit; this is the R-009/I-010 metric. Also publish the DB-agnostic-adjusted rate (excluding directories that are 100 % on both), since a third of the passing tests (10 136 / 30 801) sit in directories that pass 100 % on both databases.
4. **Nightly:** (a) MySQL control on the same image to detect environmental drift; any control failure blocks interpreting the PostgreSQL delta; (b) PostgreSQL with `--group ajax,ms-files,external-http` separately (excluded by default); (c) multisite (`-c tests/phpunit/multisite.xml`) once multisite is in scope; (d) a "no harness shim" job that reports how many test-infrastructure statements still need the wrapper (goal: zero).
5. **Sharding, when the suite gets slower:** shard by test directory using the measured per-directory times (`R-009-mysql-by-directory.csv` `seconds`; `rest-api` alone is 47 % of attributed test time), one database per shard (PHPUnit 9 has no in-process parallelism, and the transaction-per-test model needs isolation), and keep the `restapi-autosave` testsuite in its own last step because it defines `DOING_AUTOSAVE` (`phpunit.xml.dist:21-22`). Merge JUnit files before summarising.
6. **Build parity:** run `npm ci && npm run build:dev` (or use a built release artifact) in CI so the control has 0 failures; the reference checkout here is unbuilt.
7. **Keep `error_log` redirected** and `display_errors` as upstream; otherwise `@runInSeparateProcess` tests can deadlock.

## Summary of findings

- The harness reproduces the upstream suite on MySQL 8.4.13 with **30 868 / 30 900 passing (99.90 %), 1 environmental failure, 31 skips, ~5.5 min**.
- The R-003 prototype as delivered gives a **0 % baseline**: the stock test bootstrap installs WordPress with MySQL DDL, the adapter rejects it, and `install.php` exits 255 in `wp_install()` → `wp_insert_user()`.
- With a logged test-infrastructure shim and pre-created schema, the same prototype passes **2.07 %** of comparable tests (one leaked `$wpdb->options` value poisons 21 413 later tests) and **77.47 %** once that single class is excluded (66.4 % if DB-agnostic directories are excluded).
- In PG-C, UUID/integer identity is the largest identifiable cause (1 761 direct, ~4 075 class-inferred failures); missing tables (comments, links, commentmeta) are next; SQL dialect errors are few in count but widespread underneath (YEAR/HOUR/RAND, comments, DISTINCT/ORDER BY).
- Upstream test infrastructure itself assumes MySQL in at least ten places (table above); the most consequential for Pressgres are integer sentinel IDs in clean-up, transaction abort semantics, and the DDL-based installer.

## Implications for the UUID patchset

| Category | Evidence (PG-C) | Patch strategy |
|---|---|---|
| uuid-identity in core (`uuid = integer`, `post_parent = 0`, `(int)`/`absint()` on IDs, unquoted `IN (…)`) | 1 761 direct; top signatures 1, 3, 5, 9, 10 | Core patchset (D-001/D-002): ID type helpers instead of `absint()`, `%s` placeholders for IDs, `NULL` for the `0` sentinel, quoted `IN` lists. Highest-yield area |
| uuid-identity in routing/REST (`p=<uuid>`, `(?P<id>[\d]+)`) | canonical 15 % pass, `rest-api` 55 %, REST `invalid_param` codes | Core patchset: rewrite tags and REST route patterns accept UUIDs; needs R-012 for clients |
| uuid-identity in **tests** (`assertSame( 1, …)`, `int` type hints, `ID != 1` clean-up) | assumption #4, signatures 6–8 | Version-pinned test-support patch under `patches/wordpress/<version>` for `tests/phpunit/includes/*` (clean-up by remembered UUIDs); test files themselves keep failing until upstream-able changes exist. Track as expected failures, not hidden |
| schema/ddl (missing tables, DDL in installer, `dbDelta()`, temporary tables) | 267 direct / 939 inferred; PG-A | Native PostgreSQL schema + installer path (Q-003); `dbDelta()` replacement or translator; test installer must call the Pressgres installer instead of `wp_install()`'s MySQL DDL |
| sql-dialect (date functions, `RAND`, comments, `DISTINCT`/`ORDER BY`, multi-table `DELETE`, `REGEXP`) | 62 direct, more hidden | AST-based translator (R-004/Q-001), fail-closed; each construct gets a regression test |
| Transaction semantics (25P02) | 111 direct + cascades | Adapter: per-statement `SAVEPOINT` inside explicit transactions, or fail the test fast; decide in the adapter ADR |
| Connection lifecycle (`close()` / reconnect) | 508 `Tests_DB` | Adapter: implement `check_connection()` reconnect like stock `wpdb` |

## Open questions

- Which test closes the PDO handle before `Tests_DB` runs (all 508 `Tests_DB` tests see a `null` handle, including the first)? The reconnect gap is confirmed in the adapter code, the trigger is not identified.
- Are there more global-state leaks like `Tests_Admin_IncludesSchema` that only surface when a test aborts mid-body? PG-C excluded one class; a per-class isolation run (one PHPUnit process per class) would reveal others, at higher cost.
- The 832 class-inferred `unknown` failures need per-class debugging; the ±20 % bucket uncertainty matters if I-010 trends buckets.
- Should Pressgres carry a patched `tests/phpunit/includes/` (installer, clean-up, temporary tables) as part of the managed patchset, or keep it as a harness-only layer? This decides whether the "official" pass rate is measured with or without the wrapper.
- GitHub-hosted runner duration and memory (PG-B peaked at 3.01 GB in PHPUnit) are not measured.
- Multisite suite and the excluded groups (`ajax`, `ms-files`, `external-http`, `html-api-web-platform-tests`) were not run.
- R-003's `rows_affected` (matched vs changed rows) and `is_mysql = false` (disables charset stripping) effects are visible in `option`/`formatting` failures but not isolated.

## Method and reproduction

Commands (from `tools/core-phpunit/`, see its README; `WP_DEVELOP_REF` defaults to the pinned reference):

```bash
./run.sh build && ./run.sh prepare
./run.sh test mysql mysql-control-final

export PG_PROTOTYPE_DIR=<snapshot of worktrees/R-003/prototypes/r-003>
R009_PG_SHIM=0 R009_PG_SCHEMA=none ./run.sh test pgsql pgsql-raw          # PG-A
./run.sh prepare && PRESSGRES_QUERY_LOG=/dev/null ./run.sh test pgsql pgsql-full     # PG-B
./run.sh prepare && PRESSGRES_QUERY_LOG=/dev/null \
  ./run.sh test pgsql pgsql-noleak --filter '/^(?!Tests_Admin_IncludesSchema::)/'    # PG-C

D=../../docs/research/data
python3 summarize.py results/mysql-control-final/junit.xml --src "$WP_DEVELOP_REF" \
  --dir-csv $D/R-009-mysql-by-directory.csv --group-csv $D/R-009-mysql-by-group.csv \
  --fail-csv $D/R-009-mysql-failures.csv
python3 summarize.py results/pgsql-noleak/junit.xml --src "$WP_DEVELOP_REF" \
  --control-junit results/mysql-control-final/junit.xml \
  --compare-csv $D/R-009-pgsql-vs-mysql-by-directory.csv \
  --dir-csv $D/R-009-pgsql-by-directory.csv --group-csv $D/R-009-pgsql-by-group.csv \
  --baseline $D/R-009-mysql-failures.csv \
  --fail-csv results/pgsql-noleak/failures.csv --sig-csv $D/R-009-pgsql-signatures.csv
./run.sh down
```

- `R-009-runs.csv` and `R-009-pgsql-buckets.csv` were assembled from `results/*/meta.env`, the PHPUnit console summary and the `summarize.py` output above.
- `prepare` is re-run before every PostgreSQL run because `pg-wire.sh` patches `src/` in the volume; MySQL runs remove `db.php` but do not un-apply the R-003 patch, so always `prepare` before a MySQL run (done for the final control).
- Manual bucket sample: `random.seed(9)`, 12 per classified bucket and 30 `unknown` from `results/pgsql-noleak` failures (inline Python over `summarize.iter_cases`/`triage`).
- Raw artifacts (gitignored, `tools/core-phpunit/results/<label>/`): `junit.xml` (MySQL 9 MB; PG-B 353 MB; PG-C 40 MB), `phpunit.log`, `meta.env`, `r009-shim.log`, `failures.csv`, and for PG-A the R-003 query log.
- Pinned versions: see [Harness](#harness). Durations are wall-clock seconds around the runner container (`meta.env`) and PHPUnit's own `Time:` line.
- No WordPress, vendor or prototype code is committed; the R-003 worktree was only read.
