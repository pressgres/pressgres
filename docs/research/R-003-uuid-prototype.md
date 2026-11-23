# R-003: UUIDv7 primary keys and `INSERT … RETURNING "ID"` through a minimal `$wpdb` adapter

| | |
|---|---|
| Issue | pressgres/pressgres#5 (roadmap task R-003, milestone M0) |
| Status | Prototype runs green; throwaway code, not a design |
| Pinned inputs | wordpress-develop 7.1.5 (`src/`, `$wp_db_version = 61833`), PHP 8.4.27 (`php:8.4.27-cli-alpine` + `pdo_pgsql`), PostgreSQL 18.6 (`postgres:18.6-alpine`), Docker 29.8.2 linux/arm64 |
| Prototype | [`prototypes/r-003/`](../../prototypes/r-003/README.md) ([handoff for R-009](../../prototypes/r-003/HANDOFF.md)) |
| Evidence | [`data/R-003-run-output.txt`](data/R-003-run-output.txt), [`data/R-003-baseline-unpatched-output.txt`](data/R-003-baseline-unpatched-output.txt), [`data/R-003-query-fingerprints.csv`](data/R-003-query-fingerprints.csv) |

Paths below are relative to the reference root (`wordpress-develop-7.1.5/src/...`) unless they start with `prototypes/`. Line numbers are those of the **unpatched** 7.1.5 source.

## Scope and setup

Question: can a WordPress post be created and read through WordPress PHP APIs **and** the REST API when every primary key is a PostgreSQL 18 `uuid DEFAULT uuidv7()`, with `$wpdb->insert_id` set from `INSERT … RETURNING`? What is the minimum that must change?

Deliberately out of scope: a general SQL translator (Q-001), `dbDelta`/installer DDL (Q-003), comments, multisite, the block editor, plugins, performance.

What was built (all under `prototypes/r-003/`):

- `sql/01-schema.sql`: 9 tables (`wp_options`, `wp_users`, `wp_usermeta`, `wp_posts`, `wp_postmeta`, `wp_terms`, `wp_term_taxonomy`, `wp_term_relationships`, `wp_termmeta`). Every entity PK is `uuid PRIMARY KEY DEFAULT uuidv7()`, every ID reference is a nullable `uuid` (no FK constraints yet, as `docs/04-data-model.md` recommends), `"ID"` is quoted.
- `sql/02-seed-options.sql`: 31 options so WordPress boots without `wp_install()`.
- `wordpress/db.php`: `Pressgres_R003_wpdb extends wpdb` on PDO pgsql. `insert()`/`update()`/`delete()` are rebuilt with bound parameters using a column-type map read from `information_schema`; `insert()` appends `RETURNING <pk>` and sets `insert_id` to the UUID **string**. `query()` accepts only `SELECT`/`INSERT`/`UPDATE`/`DELETE`/`START`/`COMMIT`/`ROLLBACK`, applies 6 named token-level rewrites, rejects a deny-list of MySQL-only keywords, comments and double-quoted strings, and logs every statement (original, SQL sent, rules, status, error, caller, REST request; never parameter values) to JSON lines.
- `patches/wordpress-7.1.5-r003-uuid.patch`: the core patch, discovered iteratively (run, read failing statement, patch the smallest site, re-run).
- `scripts/setup.php`: creates roles, the admin user, the default category and an application password **through WordPress APIs** (`populate_roles()`, `wp_insert_user()`, `wp_insert_term()`, `WP_Application_Passwords::create_new_application_password()`), so those paths are exercised too.
- `scripts/demo-php.php`, `scripts/demo-rest.php`: the assertions below.

REST authentication: an application password over HTTP Basic. Application passwords normally require HTTPS; `wp_is_application_passwords_supported()` also accepts `wp_get_environment_type() === 'local'`, so `wp-config.php` sets `WP_ENVIRONMENT_TYPE` to `local`. No cookie/nonce shortcut and no auth-bypass code was needed. REST is served by `php -S` with plain permalinks (`?rest_route=`).

## What works (verified)

With the patch applied, `./run.sh all` passes **29/29 checks** with **0 errors and 0 unsupported statements** in the query log (captured in [`data/R-003-run-output.txt`](data/R-003-run-output.txt)). Excerpt of the actual output:

```text
== WordPress PHP API: wp_insert_post() / get_post() ==
PASS wp_set_current_user(uuid) -> get_current_user_id()  ['01a20555-4323-7fc7-b10c-0a6cce968d46']
PASS wp_insert_post() returned a string  ['01a20555-4774-71c7-a185-770d093cc6a9']
PASS returned ID is a canonical UUIDv7 (36 chars)  [len=36]
PASS $wpdb->insert_id after insert is not an int  ['01a20555-4787-7f59-9c05-74090ca43ab3']
PASS get_post(uuid) returned WP_Post
PASS get_post()->ID === returned UUID (untruncated)  ['01a20555-4774-71c7-a185-770d093cc6a9']
PASS get_post()->post_author === admin UUID  ['01a20555-4323-7fc7-b10c-0a6cce968d46']
PASS get_post()->post_parent is legacy 0/empty sentinel  [0]
PASS post_title round-trips
PASS default category assigned (UUID term_id)  [["01a20555-4343-7f55-9164-4e3917efcf35"]]
PASS PostgreSQL row exists for 01a20555-4774-71c7-a185-770d093cc6a9
PASS SELECT uuid_extract_version("ID") = 7  [got 7, uuid_extract_timestamp=2026-11-22 22:16:44.66+00]
PASS stored "ID" equals returned ID byte-for-byte
== REST API: POST/GET /wp/v2/posts (application password) ==
PASS GET /wp/v2/users/me -> 200  [HTTP 200]
PASS POST /wp/v2/posts -> 201  [HTTP 201]
PASS response id is a JSON string  ['01a20555-4c94-733d-9b71-924b26fb8f2d' ]
PASS response id is canonical UUIDv7 (36 chars, untruncated)  [len=36]
PASS response author === admin UUID  ['01a20555-4323-7fc7-b10c-0a6cce968d46']
PASS raw JSON contains the quoted UUID
PASS GET /wp/v2/posts/<uuid> -> 200  [HTTP 200 ]
PASS GET id === POST id (untruncated)  ['01a20555-4c94-733d-9b71-924b26fb8f2d']
PASS _links.self ends with the full UUID  [http://localhost:58080/index.php?rest_route=/wp/v2/posts/01a20555-4c94-733d-9b71-924b26fb8f2d]
PASS GET categories === [default category UUID]  [["01a20555-4343-7f55-9164-4e3917efcf35"]]
PASS GET /wp/v2/posts/<uuid of PHP-created post> -> 200 + same id  [HTTP 200]
PASS SELECT uuid_extract_version("ID") = 7  [got 7, uuid_extract_timestamp=2026-11-22 22:16:45.972+00]
     REST response excerpt: {"id":"01a20555-4c94-733d-9b71-924b26fb8f2d","status":"publish","type":"post","link":"http://localhost:58080/?p=01a20555-4c94-733d-9b71-924b26fb8f2d","author":"01a20555-4323-7fc7-b10c-0a6cce968d46","categories":["01a20555-4343-7f55-9164-4e3917efcf35"]}
```

(Some PASS lines omitted here for length; the full capture has all 29.) The `uuid_extract_version` checks use a separate PDO connection, not the adapter. The `$wpdb->insert_id` value after `wp_insert_post()` is the last insert of the call (a `wp_postmeta` row), as in stock WordPress; the check only asserts it is not an `int`.

The same run created the admin user, its usermeta, the `Uncategorized` term, its `term_taxonomy` row, term relationships, postmeta and options rows, all with PostgreSQL-generated UUIDv7 keys.

## Baseline without the core patch (verified)

`R003_NO_PATCH=1 ./run.sh all` ([`data/R-003-baseline-unpatched-output.txt`](data/R-003-baseline-unpatched-output.txt)) stops in setup:

```text
[setup] admin user ID                1
[setup] wp_insert_term FAILED        'Could not insert term taxonomy into the database.'
setup         110     81     16           13
```

`wp_insert_user()` returned the integer `1`: `user.php:2575` does `(int) $wpdb->insert_id`, and PHP's `(int) "01a2…"` is `1` (leading digits of the UUIDv7 timestamp). This is **silent truncation**, the failure mode the PRD warns about; only the adapter's refusal to bind a non-UUID to a `uuid` column (`non-UUID value for uuid column wp_usermeta.user_id: int(1)`) and PostgreSQL's `operator does not exist: uuid = integer` made it loud. Note the truncated value depends on the clock: today's UUIDv7s start `01a2…`, so the cast yields `1`; other prefixes yield other small integers or `0`.

## Query log summary (happy path)

Counted by `scripts/query-log-summary.php` over `build/logs/query-log.jsonl` of the final run. A fingerprint is the original SQL with string, number and UUID literals replaced by `?`; for `insert()`/`update()` the fingerprint is table + column list. "Happy path" = phases `php-api` (demo-php) and `rest` (the 3 REST requests), de-duplicated.

| Measure | php-api | rest | Happy path (union) | setup (for reference) |
|---|---:|---:|---:|---:|
| Statements executed (WordPress-issued) | 49 | 173 | 222 | 116 |
| Adapter-internal statements (catalog load, found-rows count) | 2 | 11 | 13 | 2 |
| Distinct fingerprints | 26 | 31 | **33** | 24 |
| … raw `query()` fingerprints | | | 25 | |
| … of which needed a rewrite | | | **7** | |
| … of which sent unchanged | | | 18 | |
| … `insert()`/`update()` fingerprints (always rebuilt with bound params) | | | 8 (3 insert, 5 update) | |
| Errors / unsupported | 0 | 0 | 0 | 0 |

REST requests: `GET users/me` 31 statements, `POST posts` 64, `GET posts/<uuid>` 78 (two GETs). Most of the per-request volume is option loading and application-password bookkeeping.

Rewrite rules that fired on the happy path (number of distinct fingerprints): `quote-mixed-case-column` (bare `ID` → `"ID"`) 6, `backtick-to-double-quote` 1, `options-on-duplicate-key-to-on-conflict` 1 (`add_option()`'s `INSERT … ON DUPLICATE KEY UPDATE` → `ON CONFLICT ("option_name") DO UPDATE SET … = EXCLUDED."…"`), `strip-sql-calc-found-rows` 1 + `limit-offset-comma` 1 (the revision-count `WP_Query`; `FOUND_ROWS()` is emulated with a `COUNT(*)` over the same query minus `LIMIT`), `insert-returning-pk` 3, `uuid-zero-sentinel-to-null` 1. Full list: [`data/R-003-query-fingerprints.csv`](data/R-003-query-fingerprints.csv).

Confidence: high for the counts (mechanical). The fingerprint normalisation is heuristic; two statements differing only in an `IN (…)` list length collapse into one fingerprint (`?+`).

## Core patch set for this flow

`patches/wordpress-7.1.5-r003-uuid.patch`: **13 files, 57 hunks, 97 lines added / 83 removed**: **45 patched sites** (counted per function below) plus one new helper. It adds one helper, `pressgres_sql_id_list()` (quoted `IN (…)` list of validated UUIDs; an empty list becomes the nil UUID so `IN` matches nothing and `NOT IN` excludes nothing), and reuses core's existing `wp_is_uuid()` (`functions.php:8124`) as the ID validator. Two batch-applied sites (`delete_metadata()`, `metadata_exists()`) and one cast (`sanitize_user_field()` restore cast, `user.php:1994`) were removed again after the flow passed without them, so every site listed was needed for a check, a clean query log or a correct result in this run.

Failure class key: **C** explicit `(int)`/`absint`/`intval` cast; **N** `is_numeric()`/`is_int()` gate; **P** `%d` placeholder; **L** unquoted `implode()` ID list; **S** sanitizer int field; **Z** `= 0` sentinel compared to a `uuid` column; **R** REST route/schema; **D** SQL dialect (not ID-related).

| # | Site (unpatched line) | Function | Class | Symptom before the patch |
|---|---|---|---|---|
| 1 | `wp-includes/functions.php:5068` | `wp_parse_id_list()` | C | `absint` of every ID list; now returns lower-case UUIDs, drops anything else |
| 2 | `wp-includes/functions.php:5069` (added) | `pressgres_sql_id_list()` | L | new helper used by sites 12, 15, 29, 30, 40, 41 |
| 3 | `wp-includes/functions.php:7423`, `:7434` | `_get_non_cached_ids()` | C | cache keys truncated |
| 4 | `wp-includes/functions.php:7457-7458` | `_validate_cache_id()` | N | `_doing_it_wrong`: "Object ID must be an integer, string given" |
| 5 | `wp-includes/formatting.php:4957` | `sanitize_option( 'default_category' )` | C | option saved as `"1"`; posts silently got **no** category |
| 6 | `wp-includes/class-wp-post.php:281-282`, `:289`, `:296` | `WP_Post::get_instance()` | C, P | `get_post( $uuid )` → `false` / `"ID" = 1` |
| 7 | `wp-includes/post.php:1153`, `:1157-1158` | `get_post()` | N, C | UUID not numeric → `null` |
| 8 | `wp-includes/post.php:3026` | `sanitize_post_field()` | S | `ID`/`post_parent` cast to int |
| 9 | `wp-includes/post.php:4406` | `wp_get_post_categories()` | C | query for nil UUID → `[]` |
| 10 | `wp-includes/post.php:4453` | `wp_get_post_terms()` | C | as 9 |
| 11 | `wp-includes/post.php:5041` | `wp_insert_post()` | C | `(int) $wpdb->insert_id` |
| 12 | `wp-includes/post.php:5662-5663` | `wp_unique_post_slug()` | P, Z | `"ID" != 0` → `uuid <> integer` |
| 13 | `wp-includes/post.php:5810-5812`, `:5833` | `wp_set_post_terms()` | C | object and term IDs truncated |
| 14 | `wp-includes/post.php:5855` | `wp_set_post_categories()` | C | as 13 |
| 15 | `wp-includes/class-wp-query.php:2260` | `WP_Query::get_posts()` `post__not_in` | L | `"ID" NOT IN (0)` |
| 16 | `wp-includes/class-wp-query.php:2264-2265` | `WP_Query::get_posts()` `post_parent` | N, P | **filter silently dropped**: revision count ran over all revisions site-wide (observed in the first clean run before this patch) |
| 17 | `wp-includes/class-wp-user.php:155` | `WP_User::__construct()` | N | UUID treated as a **login name** |
| 18 | `wp-includes/class-wp-user.php:186` | `WP_User::init()` | C | `$user->ID` = 1 |
| 19 | `wp-includes/class-wp-user.php:213-217` | `WP_User::get_data_by( 'id' )` | N, C | lookup refused / truncated |
| 20 | `wp-includes/user.php:731` | `get_current_user_id()` | C | returns 1 |
| 21 | `wp-includes/user.php:1901` | `sanitize_user_field()` | S | `ID` cast |
| 22 | `wp-includes/user.php:2036` | `clean_user_cache()` | N | fatal `Call to a member function exists() on string` (`user.php:2040`) |
| 23 | `wp-includes/user.php:2575` | `wp_insert_user()` | C | returned `1` (baseline above) |
| 24 | `wp-includes/meta.php:43`, `:47`, `:97`, `:143` | `add_metadata()` | N, C, P | meta insert refused / truncated |
| 25 | `wp-includes/meta.php:199`, `:203`, `:265` | `update_metadata()` | N, C, P | `user_id = 1` |
| 26 | `wp-includes/meta.php:629`, `:633` | `get_metadata_raw()` | N, C | meta reads return nothing |
| 27 | `wp-includes/meta.php:1156`, `:1201`, `:1208` | `update_meta_cache()` | C, L | `user_id IN (1)` |
| 28 | `wp-includes/class-wp-term.php:119-120`, `:132` | `WP_Term::get_instance()` | C, P | `term_id = 1` |
| 29 | `wp-includes/class-wp-term-query.php:476` | `WP_Term_Query` `include` | L | `t.term_id IN ( 1 )` |
| 30 | `wp-includes/class-wp-term-query.php:596`, `:600` | `WP_Term_Query` `object_ids` | C, L | `tr.object_id IN (1)` |
| 31 | `wp-includes/class-wp-term-query.php:614-615` | `WP_Term_Query` `parent` | C, Z | `tt.parent = '0'` → invalid uuid |
| 32 | `wp-includes/class-wp-term-query.php:744` | `WP_Term_Query::get_terms()` | **D** | `SELECT DISTINCT … ORDER BY t.name` → SQLSTATE 42P10 (PostgreSQL requires ORDER BY expressions in the DISTINCT select list) |
| 33 | `wp-includes/class-wp-term-query.php:987`, `:991` | `fields => ids / tt_ids` | C | category IDs returned as ints |
| 34 | `wp-includes/taxonomy.php:1650` | `term_exists()` | N | UUID treated as slug/name |
| 35 | `wp-includes/taxonomy.php:1787` (+ restore at `:1937`) | `sanitize_term_field()` | S | `term_id`, `term_taxonomy_id`, `parent`, `object_id` cast |
| 36 | `wp-includes/taxonomy.php:2312` | `wp_get_object_terms()` | C | object IDs truncated |
| 37 | `wp-includes/taxonomy.php:2628`, `:2643`, `:2656`, `:2664` | `wp_insert_term()` | C, P, Z | `(int) insert_id`; `tt.parent = 0`; `t.term_id < %d` |
| 38 | `wp-includes/taxonomy.php:2854`, `:2892`, `:2906` | `wp_set_object_terms()` | C, N, P | relationship check / insert |
| 39 | `wp-includes/taxonomy.php:3626` | `wp_update_term_count_now()` | C | term IDs truncated |
| 40 | `wp-includes/taxonomy.php:3731-3732` | `clean_term_cache()` | C, L | `term_taxonomy_id IN (1)` |
| 41 | `wp-includes/taxonomy.php:4165` | `_prime_term_caches()` | C, L | `t.term_id IN (1)` |
| 42 | `wp-includes/taxonomy.php:4237` | `_update_post_term_count()` | P | `term_taxonomy_id = 1` |
| 43 | `wp-includes/rest-api/endpoints/class-wp-rest-posts-controller.php:114`, `:119` | route `(?P<id>[\d]+)`, arg `type: integer` | R | `GET /wp/v2/posts/<uuid>` → 404 `rest_no_route` |
| 44 | `wp-includes/rest-api/endpoints/class-wp-rest-posts-controller.php:560`, `:564` | `get_post()` (controller) | C | invalid post ID |
| 45 | `wp-includes/rest-api/endpoints/class-wp-rest-posts-controller.php:2056` | `prepare_item_for_response()` `author` | C | response `"author": 1` |
| 46 | `wp-includes/rest-api.php:3247` | `rest_get_route_for_post()` | C (`%d` in `sprintf`) | `_links.self` → `/wp/v2/posts/1` (silent) |

Class tally over the 46 rows (a row can have several; computed from this table): C 31, N 11, P 9, L 7, S 3, Z 3, R 1, D 1. Confidence: high that each listed site was on the path (each was found from a failing statement, a failed check, a PHP fatal/notice, or a nil-UUID query in the log); medium that the set is minimal (only three sites were removal-tested).

## Failures hit and workarounds (chronological)

1. **Silent truncation of `insert_id`** (`user.php:2575`) → returned `1`. Patched every `(int) $wpdb->insert_id` on the path (sites 11, 23, 24, 37). Core has **15** `(int) $wpdb->insert_id` sites in `wp-includes` + `wp-admin` (`grep -rnF '(int) $wpdb->insert_id' wp-includes wp-admin`); this flow touched 5.
2. **`is_numeric()` gates** turned UUIDs into names (`WP_User`, `term_exists()`), into `null` (`get_post()`), into a PHP fatal (`clean_user_cache()`), or **dropped a WHERE filter** (`WP_Query` `post_parent`, site 16). The last one is the most dangerous class found: no error, wrong (broader) result.
3. **`uuid = integer` / invalid uuid `'0'`** from `%d` placeholders and the `0` "no parent" sentinel compared in SQL (sites 12, 31, 37). The adapter maps `0`/`''` to `NULL` for `insert()`/`update()`/`delete()` bindings (`uuid-zero-sentinel-to-null`), but cannot fix sentinel comparisons inside hand-written SQL without type-aware parsing; those were patched in core to `IS NULL`.
4. **Option sanitiser**: `default_category` was silently saved as `"1"` (site 5), so posts got no category and no error was raised. Found only because a check asserted the category.
5. **wordpress-develop `src/index.php`** is a "build the assets" nag (`index.php:42`) that `wp_die()`s every front-end request → REST returned HTTP 500. Workaround (not a core patch): copy `_index.php` over `index.php`, which is what the wordpress-develop build does. JS/CSS assets are still unbuilt; REST does not need them.
6. **REST route regex** `(?P<id>[\d]+)` → 404 for UUIDs (site 43). Core registers **15** `(?P<id>[\d]+)` routes in **11** files under `wp-includes/rest-api/` plus **5** `(?P<parent>[\d]+)` routes (`grep -rn '(?P<id>\[\\d\]+)' wp-includes/rest-api`).
7. **REST output casts**: `"author": 1` and `_links.self` ending in `/posts/1` (sites 45, 46) while `id` itself was correct. Both silent.
8. **`SELECT DISTINCT` + `ORDER BY` not in the select list** (site 32): a PostgreSQL dialect difference, not an ID issue; patched in core because the adapter must not rewrite select lists.
9. Prototype tooling: the summary script's literal-stripping regex hit PCRE's backtrack limit on large serialised option values (returned `null`); fixed with a possessive pattern. No effect on WordPress.

## Known unpatched issues seen or inferred near this path

| Site | What | Evidence |
|---|---|---|
| `wp-includes/author-template.php:387` | `get_author_posts_url()` casts `(int) $author_id`; `GET users/me` returns `"link": "…/?author=1"` | Verified in the captured output |
| `wp-includes/capabilities.php:149`, `:252`, `:374` | `$user_id === (int) $post->post_author` in `map_meta_cap()`; an Author/Contributor would lose edit/delete rights on their own posts | Inferred from source; the demo uses an administrator (`edit_others_posts`), so not exercised |
| `wp-includes/meta.php:1799` | `get_object_subtype()` casts `(int) $object_id`, so subtype-registered meta (e.g. `footnotes` for `post`) is looked up with subtype `''` | Inferred from source; not asserted |
| `wp-includes/rest-api/endpoints/class-wp-rest-posts-controller.php:2448`, `:2908-2909` | Item schema still declares `id` and the `author` link target as `integer` (schema/OPTIONS output, client generators, Gutenberg) | Source; response bodies already carry strings |
| `wp-includes/rest-api/endpoints/class-wp-rest-posts-controller.php:1396`, `:1447-1460` | `(int) $request['author']`, `(int) $request['parent']` on create/update | Source; the demo sends neither |
| `wp-includes/taxonomy.php:2497`, `:2512`, `:3311` | `(int) $args['parent']` in `wp_insert_term()` / `wp_update_term()` | Source; only parent `0` exercised |
| `wp-includes/user.php:1994` | `sanitize_user_field()` restore cast for non-raw contexts | Removal-tested: flow passes without it, so not exercised |
| `post_parent` read-back | Stored `NULL`, read back as `0` after `sanitize_post_field()`; `WP_Term->parent` is `NULL` when not sanitised | Verified (`[0]` in output; `get_term()` raw dump during development) |

## Adapter findings (D-001 / D-002 inputs)

- **Result shape**: with the schema quoting `"ID"`, PDO returns the key `ID` unchanged, so no result-key mapping was needed for posts/users. `PDO::ATTR_STRINGIFY_FETCHES` was required to match mysqli's string results; `uuid` columns arrive as lower-case canonical strings.
- **Type-aware binding** from the live catalog (2 `information_schema` queries per PHP process) was enough to rebuild `insert()`/`update()`/`delete()` with bound parameters and `RETURNING`. Rejecting non-UUID values for `uuid` columns converted every silent truncation that reached a write into a loud failure; recommend making this a D-002 contract. The catalog load should be cached (it is 2 of the 13 adapter statements on the happy path).
- **`insert_id`**: setting it to the UUID string works for `wp_posts`, `wp_users`, `wp_usermeta`, `wp_postmeta`, `wp_terms`, `wp_term_taxonomy` and `wp_options` (the upsert). Tables with composite keys (`wp_term_relationships`) get no `RETURNING`; `insert_id` stays `0` there, as with MySQL.
- **Escaping**: PostgreSQL's `standard_conforming_strings=on` means `_real_escape()` only doubles single quotes; backslashes are literal, which also keeps `esc_like()` output working with PostgreSQL's default `LIKE` escape. No backslash-containing literal reached the adapter on this path.
- **Semantic gaps accepted for the prototype**: `rows_affected` for `UPDATE` is PostgreSQL's matched-row count, not MySQL's changed-row count (`class-wpdb.php:2311`); `is_mysql = false` disables WordPress's charset/invalid-text stripping; `db_version()` reports `8.0` so core feature gates pass; datetime columns are `varchar(19)` because WordPress writes `0000-00-00 00:00:00`.
- **Statement volume**: 18 of the 25 raw happy-path fingerprints ran unchanged; the 7 rewrites were mostly quoting `ID`. The fail-closed deny-list was never hit after patching, which says more about how narrow the flow is than about the size of Q-001.

## Implications

- **D-001 (PDO driver, result shape)**: PDO pgsql with stringified fetches and catalog-driven type info is sufficient for core CRUD on this flow; the schema-quoting policy in `docs/04-data-model.md` avoids result-key remapping for `"ID"`. Add matched-vs-changed row semantics, catalog caching and charset/invalid-text handling to its acceptance tests.
- **D-002 (`$wpdb` facade, `insert_id`)**: `INSERT … RETURNING <pk>` with a string `insert_id` works. The facade alone cannot deliver UUIDs: every consumer site casts. The facade should also (a) reject non-UUID values bound to `uuid` columns, (b) map the `0`/`''` sentinel to `NULL` only on typed bindings, never in raw SQL, and (c) log original + sent SQL with source attribution (D-004).
- **U-001 (core ID casts and types)**: 45 sites for one post-create/read flow (posts, users, meta, terms, REST) is a lower bound. The classes above suggest centralising: `wp_parse_id_list()` and a quoted-ID-list helper absorb the **C/L** classes for list-shaped IDs; `wp_is_uuid()` replaces `is_numeric()` gates (**N**); `%d` → `%s` for ID placeholders (**P**); sentinel comparisons need `IS NULL` (**Z**). Class **N** must be audited first because it fails **open** (wrong results, dropped filters) rather than closed. R-001's audit should count by these classes.
- **U-002 (REST schemas, routes, editor)**: route regexes and `integer` arg schemas block UUID lookups outright (20 route patterns to change); response casts and link builders silently emit truncated IDs even when `id` itself is correct, so REST tests must assert every ID-bearing field and link, not just `id`. Schema `type`/`format` changes are client-visible (R-012).
- **Patch strategy**: a version-pinned patch series (as in `docs/02-architecture.md`) was workable here: the 13-file patch applies cleanly with `patch -p1` to a fresh 7.1.5 copy. Each site is small, but they are spread across core, so rebase cost (R-013) scales with the number of sites, not lines.

## Open questions

1. How many sites does the full M2 exit (CRUD, login, editor, REST collections, comments) need? This run gives a floor of 45 for one flow; R-001 should give the ceiling.
2. Should the `0` "no ID" sentinel survive in PHP (read back as `0`, as here) or become `null` everywhere? Plugins compare `0 === $post->post_parent`; `NULL` in PHP would break them differently.
3. Does `wp_is_uuid()` need a v7-aware mode? Core's `wp_is_uuid( $uuid, 7 )` currently rejects every version except 4 (`functions.php:8130-8132`); this prototype used the version-less form.
4. `uuidv7()` ordering made `t.term_id < %s` in `wp_insert_term()`'s duplicate check behave like the integer original (older = smaller). Is relying on UUIDv7 time ordering acceptable anywhere in core, given `docs/04-data-model.md` says never to infer order from the timestamp?
5. Datetime storage: `timestamp` with zero-date → `NULL` mapping (needs read-side mapping) or text? Not decided here (D-003).
6. Not verified: REST collection `GET /wp/v2/posts` (`SQL_CALC_FOUND_ROWS` + `FOUND_ROWS()` emulation was exercised only via the revision count), `PUT`/`DELETE`, `_embed`, non-admin roles, cookie + nonce auth.
7. Builds of wordpress-develop: is the release package (built `index.php`, assets) the intended patch target rather than `src/`? It affects patch line numbers and the index.php workaround.

## Summary of findings

- A WordPress 7.1.5 post can be created and read through `wp_insert_post()`/`get_post()` and through `POST`/`GET /wp/v2/posts` with PostgreSQL 18 `uuidv7()` primary keys; full 36-character UUIDs come back untruncated in PHP and JSON, and `uuid_extract_version("ID") = 7` (29/29 checks, 0 SQL errors).
- It needs both pieces: a minimal adapter (catalog-typed binding, `INSERT … RETURNING`, 6 token-level rewrite rules; 9 distinct rewrite/binding rules fired in the run) **and** a 13-file core patch touching 45 sites. Without the patch, user creation silently returns ID `1`.
- Happy path: 222 WordPress-issued statements, 33 distinct fingerprints; 7 of 25 raw fingerprints needed a rewrite and all 8 `insert()`/`update()` fingerprints are rebuilt with bound parameters.
- The most dangerous failures were silent: `is_numeric()` gates dropping a WHERE filter, an option sanitiser zeroing the default category, and REST link/author fields truncated to `1` while `id` was correct.
- One PostgreSQL dialect issue surfaced (`SELECT DISTINCT` + `ORDER BY`); the rest were integer-ID assumptions.

## Implications for the UUID patchset

| Category | Strategy suggested by this run |
|---|---|
| `(int) $wpdb->insert_id` (C) | Remove the cast; the facade guarantees a UUID string. 15 core sites. |
| ID list helpers (C/L) | Patch `wp_parse_id_list()` once; add one quoted-UUID list helper; convert `implode()` sites to it. |
| `is_numeric()` / `is_int()` gates (N) | Replace with `wp_is_uuid()`; audit first, because these fail open. |
| `%d` for IDs (P) | `%s`; the facade rejects non-UUIDs. |
| `0` sentinel in SQL (Z) | `IS NULL` in core SQL; facade maps `0` → `NULL` only for typed bindings. |
| Sanitisers / options (S) | Treat ID fields as UUID-or-0; option sanitisers for ID-valued options. |
| REST routes, schemas, links (R) | UUID route regex, `type: string, format: uuid`, `%s` in route builders; assert every ID-bearing field. |
| Dialect (D) | Core patch only when the fix is local (site 32); otherwise Q-001/Q-002. |

## Method and reproduction

Tools: Docker 29.8.2 (linux/arm64), `postgres:18.6-alpine` (PostgreSQL 18.6), `php:8.4.27-cli-alpine` + `pdo_pgsql` (PHP 8.4.27), WordPress from the pinned `wordpress-develop-7.1.5/src` (read-only; copied, never modified in place).

```sh
cd prototypes/r-003
./run.sh all                      # patched run: exits 0, prints the checks and the query-log summary
R003_NO_PATCH=1 ./run.sh all      # baseline without the core patch: exits 1 in setup
./run.sh down                     # removes containers and the database volume
```

Discovery loop: start from no patch; run `./run.sh iterate`; read failing statements (`build/logs/query-log.jsonl`, `"status":"error"|"unsupported"`), PHP fatals/notices (`build/logs/wp-debug.log`), failing checks, and queries containing the nil UUID (`00000000-0000-0000-0000-000000000000`, the marker for an ID that was cast away); patch the smallest site in `build/wordpress`; repeat; `./run.sh mkpatch` regenerates the patch. Minimality was spot-checked by reverting three candidate sites and re-running (they were dropped). Final evidence was produced by a fresh `./run.sh all` (fresh copy + patch + fresh database), then `./run.sh down`.

Counts: statement and fingerprint counts from `scripts/query-log-summary.php`; patch size from the patch file (`grep -c '^@@'`, added/removed lines excluding headers); REST route counts from `grep -rn '(?P<id>\[\\d\]+)' wp-includes/rest-api` (15 lines, 11 files) and `(?P<parent>\[\\d\]+)` (5); `(int) $wpdb->insert_id` count from `grep -rnF '(int) $wpdb->insert_id' wp-includes wp-admin` (15). UUID values in the captured output differ on every run.
