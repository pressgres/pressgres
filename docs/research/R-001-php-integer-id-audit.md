# R-001 · WordPress 7.1.5 PHP integer-ID audit

This spike inventories integer assumptions and adjacent ID contracts in the pinned WordPress PHP sources. The checkout identifies itself as `7.1.5-src`, has schema version `61833`, and is at commit `984163c92ef66b6186538ecf01bacb97fc097541`. The release target remains the proposed managed WordPress 7.1 patchset on PHP 8.4 and PostgreSQL 18 with canonical UUIDv7 strings and a single identity per entity. `wordpress-develop-7.1.5/src/wp-includes/version.php:19` · `wordpress-develop-7.1.5/src/wp-includes/version.php:26` · [Pressgres data model](../04-data-model.md) · [Version policy](../07-compatibility.md)

The audit changes this report, two CSVs, and the scanner and reporting helpers. It covers PHP in `src/wp-admin`, `src/wp-includes`, `src/xmlrpc.php`, and top-level `src/wp-*.php`. The `sites/blogs` category includes site, blog, and network IDs for out-of-scope multisite review. User or post IDs referenced by multisite code retain their own entity category. PHP REST routes and argument/response schemas are recorded for R-012. Gutenberg JavaScript, SQLite translation, themes, plugins, and WordPress test files are outside this inventory. [Product scope](../01-product-and-scope.md) · [Roadmap](../08-roadmap.md)

## Inventory

The [hit CSV](data/R-001-php-id-hits.csv) contains one row per matched pattern and classified operand or SQL slot. `file` is relative to the WordPress checkout, `line` is 1-based, and `function` names the enclosing function or method when available. A site can have multiple rows, such as an ID cast and the query-var key it reads. `entity` is the identity being manipulated, so `post_author` counts under users. Each row carries the source-line snippet. Multiline SQL bind rows point to the call line. Identity-related cache calls and getters are review surfaces, including calls that already accept strings.

The scanner emitted **5,741** candidates across the pinned checkout. It classified **3,103** as identity (2,538 high confidence and 565 medium), **1,847** as ambiguous, and **791** as non-identity numeric. The identity matrix includes multisite for visibility.

| Entity | cast | validation | sql-format | sentinel | type-decl | query-var | cache-key | other | Total |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| posts | 386 | 31 | 92 | 666 | 35 | 103 | 20 | 100 | 1433 |
| users | 126 | 15 | 63 | 213 | 6 | 44 | 7 | 18 | 492 |
| comments | 54 | 1 | 15 | 97 | 3 | 0 | 3 | 10 | 183 |
| terms | 143 | 11 | 43 | 202 | 3 | 76 | 6 | 40 | 524 |
| term_taxonomy | 8 | 0 | 27 | 13 | 0 | 0 | 0 | 3 | 51 |
| meta | 6 | 6 | 3 | 7 | 0 | 0 | 0 | 2 | 24 |
| options | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 1 |
| links | 13 | 0 | 5 | 21 | 0 | 0 | 4 | 1 | 44 |
| sites/blogs | 87 | 15 | 27 | 173 | 0 | 0 | 35 | 14 | 351 |
| Total | 823 | 79 | 276 | 1392 | 47 | 223 | 75 | 188 | 3103 |

Of the identity-classified rows, 223 are query-var references and 75 are cache-key or namespace references. The scanner found 39 identity integer REST schemas, 22 numeric identity route matches, 8 native integer parameters classified as IDs, and 27 ID getter declarations assigned to an entity. It recorded 19 native integer return declarations without enough evidence to classify them as entity IDs. It found 28 `insert_id` property or access rows, including 13 generic or unresolved rows, plus the separate driver call. [Count method](#methodreproduction)

## Hotspots

The file and function columns are independent rankings by identity rows. Ties sort by checkout-relative path and then by function name. Each reference points to the first classified hit for that file or function. `<file>` includes top-level code and class members outside a method.

| Rank | File and first classified line | Hits | Function and first classified line | Hits |
| --- | --- | ---: | --- | ---: |
| 1 | `wordpress-develop-7.1.5/src/wp-includes/class-wp-query.php:584` | 295 | `WP_Query::get_posts` at `wordpress-develop-7.1.5/src/wp-includes/class-wp-query.php:2052` | 118 |
| 2 | `wordpress-develop-7.1.5/src/wp-includes/post.php:1003` | 178 | `WP_Query::parse_tax_query` at `wordpress-develop-7.1.5/src/wp-includes/class-wp-query.php:1237` | 81 |
| 3 | `wordpress-develop-7.1.5/src/wp-includes/taxonomy.php:891` | 127 | `WP_Query::parse_query` at `wordpress-develop-7.1.5/src/wp-includes/class-wp-query.php:832` | 48 |
| 4 | `wordpress-develop-7.1.5/src/wp-includes/class-wp-xmlrpc-server.php:420` | 93 | `<file>` at `wordpress-develop-7.1.5/src/wp-admin/nav-menus.php:85` | 37 |
| 5 | `wordpress-develop-7.1.5/src/wp-admin/includes/ajax-actions.php:256` | 89 | `WP_Comment_Query::get_comment_ids` at `wordpress-develop-7.1.5/src/wp-includes/class-wp-comment-query.php:553` | 33 |
| 6 | `wordpress-develop-7.1.5/src/wp-includes/comment.php:136` | 89 | `upgrade_230` at `wordpress-develop-7.1.5/src/wp-admin/includes/upgrade.php:1325` | 32 |
| 7 | `wordpress-develop-7.1.5/src/wp-admin/includes/upgrade.php:111` | 65 | `redirect_canonical` at `wordpress-develop-7.1.5/src/wp-includes/canonical.php:54` | 31 |
| 8 | `wordpress-develop-7.1.5/src/wp-admin/includes/post.php:33` | 63 | `_wp_menu_item_classes_by_context` at `wordpress-develop-7.1.5/src/wp-includes/nav-menu-template.php:339` | 22 |
| 9 | `wordpress-develop-7.1.5/src/wp-includes/user.php:119` | 63 | `<file>` at `wordpress-develop-7.1.5/src/wp-admin/edit-form-comment.php:32` | 21 |
| 10 | `wordpress-develop-7.1.5/src/wp-includes/rest-api/endpoints/class-wp-rest-posts-controller.php:114` | 57 | `wp_insert_post` at `wordpress-develop-7.1.5/src/wp-includes/post.php:4619` | 21 |
| 11 | `wordpress-develop-7.1.5/src/wp-admin/includes/media.php:47` | 56 | `_split_shared_term` at `wordpress-develop-7.1.5/src/wp-includes/taxonomy.php:4318` | 20 |
| 12 | `wordpress-develop-7.1.5/src/wp-includes/class-wp-customize-manager.php:1000` | 51 | `wp_insert_term` at `wordpress-develop-7.1.5/src/wp-includes/taxonomy.php:2492` | 20 |
| 13 | `wordpress-develop-7.1.5/src/wp-includes/rest-api/endpoints/class-wp-rest-comments-controller.php:70` | 51 | `wp_get_db_schema` at `wordpress-develop-7.1.5/src/wp-admin/includes/schema.php:36` | 19 |
| 14 | `wordpress-develop-7.1.5/src/wp-includes/nav-menu.php:235` | 48 | `WP_Query::fill_query_vars` at `wordpress-develop-7.1.5/src/wp-includes/class-wp-query.php:584` | 19 |
| 15 | `wordpress-develop-7.1.5/src/wp-includes/link-template.php:192` | 44 | `WP_Term_Query::get_terms` at `wordpress-develop-7.1.5/src/wp-includes/class-wp-term-query.php:388` | 19 |
| 16 | `wordpress-develop-7.1.5/src/wp-includes/media.php:1444` | 42 | `<file>` at `wordpress-develop-7.1.5/src/wp-includes/class-wp.php:18` | 17 |
| 17 | `wordpress-develop-7.1.5/src/wp-admin/includes/schema.php:36` | 38 | `wp_new_comment` at `wordpress-develop-7.1.5/src/wp-includes/comment.php:2379` | 17 |
| 18 | `wordpress-develop-7.1.5/src/wp-includes/class-wp-comment-query.php:302` | 38 | `wp_set_wpdb_vars` at `wordpress-develop-7.1.5/src/wp-includes/load.php:747` | 17 |
| 19 | `wordpress-develop-7.1.5/src/wp-includes/deprecated.php:115` | 38 | `wp_update_nav_menu_item` at `wordpress-develop-7.1.5/src/wp-includes/nav-menu.php:418` | 17 |
| 20 | `wordpress-develop-7.1.5/src/wp-includes/ms-functions.php:125` | 38 | `WP_REST_Posts_Controller::prepare_item_for_database` at `wordpress-develop-7.1.5/src/wp-includes/rest-api/endpoints/class-wp-rest-posts-controller.php:1293` | 17 |
| 21 | `wordpress-develop-7.1.5/src/wp-admin/nav-menus.php:85` | 37 | `wp_install_defaults` at `wordpress-develop-7.1.5/src/wp-admin/includes/upgrade.php:188` | 16 |
| 22 | `wordpress-develop-7.1.5/src/wp-includes/ms-blogs.php:47` | 36 | `wp_delete_user` at `wordpress-develop-7.1.5/src/wp-admin/includes/user.php:354` | 16 |
| 23 | `wordpress-develop-7.1.5/src/wp-includes/canonical.php:54` | 32 | `map_meta_cap` at `wordpress-develop-7.1.5/src/wp-includes/capabilities.php:64` | 15 |
| 24 | `wordpress-develop-7.1.5/src/wp-includes/comment-template.php:24` | 31 | `wp_update_term` at `wordpress-develop-7.1.5/src/wp-includes/taxonomy.php:3269` | 15 |
| 25 | `wordpress-develop-7.1.5/src/wp-includes/option.php:706` | 31 | `edit_comment` at `wordpress-develop-7.1.5/src/wp-admin/includes/comment.php:57` | 14 |
| 26 | `wordpress-develop-7.1.5/src/wp-includes/ms-site.php:72` | 30 | `export_wp` at `wordpress-develop-7.1.5/src/wp-admin/includes/export.php:126` | 14 |
| 27 | `wordpress-develop-7.1.5/src/wp-includes/class-wp.php:18` | 27 | `WP_User_Query::prepare_query` at `wordpress-develop-7.1.5/src/wp-includes/class-wp-user-query.php:335` | 13 |
| 28 | `wordpress-develop-7.1.5/src/wp-includes/rest-api/endpoints/class-wp-rest-terms-controller.php:107` | 26 | `wp_xmlrpc_server::_insert_post` at `wordpress-develop-7.1.5/src/wp-includes/class-wp-xmlrpc-server.php:1451` | 12 |
| 29 | `wordpress-develop-7.1.5/src/wp-includes/nav-menu-template.php:211` | 25 | `get_blog_details` at `wordpress-develop-7.1.5/src/wp-includes/ms-blogs.php:137` | 12 |
| 30 | `wordpress-develop-7.1.5/src/wp-includes/rest-api/endpoints/class-wp-rest-revisions-controller.php:85` | 25 | `wp_delete_term` at `wordpress-develop-7.1.5/src/wp-includes/taxonomy.php:2063` | 12 |

## Zero and absence semantics

The 1,392 identity sentinel rows include 338 PHP matches with explicit zero, 5 with explicit `-1`, 19 SQL zero matches (15 schema defaults and 4 predicates or assignments), and 1,030 PHP null, false, empty, presence, or truthiness matches. These are syntactic counts. The zero group can include selection, defaults, and signed filters alongside root or missing-reference cases. Presence checks can already work for strings. [Count method](#methodreproduction)

| Legacy use | Evidence | UUID patch decision |
| --- | --- | --- |
| No post parent | `wp_insert_post()` sets `post_parent` to zero when omitted. The schema defaults it to zero, and `WP_Query` accepts zero as a root-only filter. `wordpress-develop-7.1.5/src/wp-includes/post.php:4845` · `wordpress-develop-7.1.5/src/wp-admin/includes/schema.php:177` · `wordpress-develop-7.1.5/src/wp-includes/class-wp-query.php:769` | Use a nullable parent FK and `IS NULL` for root-only. Preserve the difference between a root-only filter and an omitted filter. |
| No comment parent or authenticated commenter | Comment submission initializes `comment_parent` and `user_id` to zero and resolves a supplied parent separately. The schema defaults both columns to zero. `wordpress-develop-7.1.5/src/wp-includes/comment.php:3942` · `wordpress-develop-7.1.5/src/wp-includes/comment.php:3960` · `wordpress-develop-7.1.5/src/wp-admin/includes/schema.php:115` | Represent root comments and anonymous authors with nullable FKs. Keep parent lookup and anonymous authorization checks explicit. |
| No term parent | The term-taxonomy table defaults `parent` to zero. Term insertion checks whether the parent is positive before verifying that it exists. `wordpress-develop-7.1.5/src/wp-admin/includes/schema.php:79` · `wordpress-develop-7.1.5/src/wp-includes/taxonomy.php:2497` | Resolve a non-null parent in the terms domain and preserve the hierarchical root case. |
| No user or owner supplied | `get_current_user_id()` documents zero when logged out. `post_author` defaults to zero. Link creation uses the current user if an owner is empty, while the stock link schema defaults the owner column to **1**. `wordpress-develop-7.1.5/src/wp-includes/user.php:724` · `wordpress-develop-7.1.5/src/wp-admin/includes/schema.php:161` · `wordpress-develop-7.1.5/src/wp-admin/includes/bookmark.php:212` · `wordpress-develop-7.1.5/src/wp-admin/includes/schema.php:132` | Resolve any current-user default before binding a nullable owner. Replace the schema's fixed owner with an explicit install or creation rule. Review every anonymous and capability branch. |
| Selection and failure states | `wp_insert_post()` can return zero on a failed insert, and the featured-image AJAX path treats `-1` as removal. `WP_Query` branches on positive and negative category and author selections. `wordpress-develop-7.1.5/src/wp-includes/post.php:5036` · `wordpress-develop-7.1.5/src/wp-admin/includes/ajax-actions.php:2828` · `wordpress-develop-7.1.5/src/wp-includes/class-wp-query.php:1247` · `wordpress-develop-7.1.5/src/wp-includes/class-wp-query.php:2404` | Define separate failure, omission, clear, and exclusion states. Use explicit inclusion and exclusion lists for query args. |
| SQL fragments and ordinary numbers | The attachment detach action sets `post_parent = 0`. XML-RPC uses `post_parent = '0'` to find unattached files. The wpdb format map binds ordinary numeric `menu_order` with `%d`. `wordpress-develop-7.1.5/src/wp-admin/includes/media.php:3877` · `wordpress-develop-7.1.5/src/wp-includes/class-wp-xmlrpc-server.php:5815` · `wordpress-develop-7.1.5/src/wp-includes/load.php:749` | Rewrite zero predicates from schema and statement context. Preserve numeric fields and parameters. Review the null semantics of `<> 0`, outer joins, and mixed ID/absence lists. |

## Summary of findings

**Rough patch scope is about 1,350 distinct source lines.** The reproducible proxy is 1,347 lines with integer-sensitive matches and shared `insert_id` driver lines. The in-scope entity inventory covers 2,752 identity rows on 2,409 distinct source lines. Broadening the proxy to include all classified sentinel guards brings the direct review queue to 2,164 lines. These metrics count source locations, since several operands and patterns can share a line. Shared helper changes can cover multiple callers. Ambiguous paths and dynamic constructs can add edits. [Count method](#methodreproduction)

Post, user, comment, term, and metadata writes read back identities through `insert_id` and cast them at the PHP call site. This makes ID preservation a contract across the driver and its consumers. `wordpress-develop-7.1.5/src/wp-includes/post.php:5041` · `wordpress-develop-7.1.5/src/wp-includes/user.php:2575` · `wordpress-develop-7.1.5/src/wp-includes/comment.php:2203` · `wordpress-develop-7.1.5/src/wp-includes/taxonomy.php:2628` · `wordpress-develop-7.1.5/src/wp-includes/meta.php:143`

UUID adoption also reaches positional XML-RPC args, ID-bearing options, and query-cache normalization. PHP REST routes can reject incoming IDs before endpoint code runs. These are source findings from the pinned checkout. `wordpress-develop-7.1.5/src/wp-includes/class-wp-xmlrpc-server.php:1799` · `wordpress-develop-7.1.5/src/wp-includes/class-wp-query.php:1112` · `wordpress-develop-7.1.5/src/wp-includes/class-wp-query.php:5058` · `wordpress-develop-7.1.5/src/wp-includes/rest-api/endpoints/class-wp-rest-posts-controller.php:114`

## Implications for the UUID patchset

Treat these as proposed changes for the version-pinned managed patchset, subject to the WordPress core, identity, schema, and security review gates. [Agent review rules](../10-ai-agents.md) · [Pressgres data model](../04-data-model.md)

| Category | Proposed patch strategy and regression |
| --- | --- |
| Casts and ID lists | Use a common UUIDv7 parser with field-specific error and absence handling. Parse ID lists to full canonical strings and deduplicate using string equality. Preserve list order where it controls result order. Test malformed values, leading digits and letters, identical prefixes, duplicates, and explicit empty lists. Core's `wp_parse_id_list()` currently maps through `absint()`. `wordpress-develop-7.1.5/src/wp-includes/functions.php:5065` · `wordpress-develop-7.1.5/src/wp-includes/class-wp-query.php:1783` |
| Validation, comparisons, and identity outputs | Dispatch slug/name/email modes explicitly. Use strict equality on parsed UUIDs and separate sign-based include/exclude behavior into query inputs. Patch string formatting and serialized identity outputs where the format remains numeric. Test same-prefix UUIDs, authorization mismatches, and the documented selectors. `wordpress-develop-7.1.5/src/wp-includes/class-wp-query.php:1247` · `wordpress-develop-7.1.5/src/wp-includes/class-wp-query.php:2404` · `wordpress-develop-7.1.5/src/wp-includes/rest-api/endpoints/class-wp-rest-menu-items-controller.php:205` |
| SQL formats and generated IDs | Patch field-specific explicit and implicit `%d` bindings to typed UUID parameters, preserve actual numeric slots, and bind each list member or use a typed UUID array. Use an AST/schema-aware translation path for vetted SQL. Define `INSERT … RETURNING`, failure/reset semantics, and correct table-specific PK casing for the drop-in. Test multiple statements in sequence, failed inserts, rows affected, and UUID round trips with disposable PostgreSQL fixtures. `wordpress-develop-7.1.5/src/wp-includes/load.php:746` · `wordpress-develop-7.1.5/src/wp-includes/class-wpdb.php:2315` · `wordpress-develop-7.1.5/src/wp-includes/class-wpdb.php:2879` |
| Sentinels | Apply the field-specific decisions above at input, authorization, and storage boundaries. Test root-only versus unrestricted query, parent changes, anonymous comments, and failed create flows. `wordpress-develop-7.1.5/src/wp-includes/comment.php:3942` · `wordpress-develop-7.1.5/src/wp-includes/class-wp-query.php:769` |
| Native types, getters, and REST schemas | Change ID-bearing PHP signatures and public getter contracts to string or a documented nullable/error result. Align REST route matching, input validation, and output schemas with R-012. Keep scalar numeric signatures such as attachment file size. Add tests for invalid routes, omitted and null fields, permission callbacks, and response round trips. `wordpress-develop-7.1.5/src/wp-includes/user.php:724` · `wordpress-develop-7.1.5/src/wp-includes/rest-api/endpoints/class-wp-rest-attachments-controller.php:2487` · `wordpress-develop-7.1.5/src/wp-includes/rest-api/endpoints/class-wp-rest-posts-controller.php:114` |
| Query vars | Give `WP_Query` distinct UUID scalar, UUID list, root-only, slug, and numeric schemas. Preserve order-by-input behavior and make cache normalization use the same rules as SQL generation. Apply the same field review to comment, user, and taxonomy queries. `wordpress-develop-7.1.5/src/wp-includes/class-wp-query.php:1783` · `wordpress-develop-7.1.5/src/wp-includes/class-wp-query.php:2244` · `wordpress-develop-7.1.5/src/wp-includes/class-wp-query.php:5058` · `wordpress-develop-7.1.5/src/wp-includes/class-wp-comment-query.php:897` |
| Cache keys and groups | Use complete canonical UUID string keys and retain group/namespace semantics across population, reads, and invalidation. The stock cache accepts nonempty strings, while the bulk cache priming helper validates and coerces IDs as integers. Verify Redis behavior with UUID-prefix collisions, bulk key maps, parent/relationship groups, and invalidation after writes. `wordpress-develop-7.1.5/src/wp-includes/class-wp-object-cache.php:140` · `wordpress-develop-7.1.5/src/wp-includes/functions.php:7422` · `wordpress-develop-7.1.5/src/wp-includes/functions.php:7452` · `wordpress-develop-7.1.5/src/wp-includes/class-wp-query.php:3306` · `wordpress-develop-7.1.5/src/wp-includes/taxonomy.php:269` |
| Other identity contracts | Review ID-valued options separately from the `option_id` PK, and entity IDs separately from IDs that name widgets, blocks, or theme templates. Test option lookup, export/import boundaries, and supported XML-RPC behavior if that surface is retained. `wordpress-develop-7.1.5/src/wp-includes/class-wp-query.php:1112` · `wordpress-develop-7.1.5/src/wp-admin/includes/schema.php:142` · `wordpress-develop-7.1.5/src/wp-includes/class-wp-xmlrpc-server.php:1799` |

## Open questions

- How much of historical install/upgrade, deprecated APIs, XML-RPC, and customization is reachable in the managed profile? The SQL and callers are present in the pin. The patch estimate includes detected lines in these paths until release scope is resolved. `wordpress-develop-7.1.5/src/wp-admin/includes/upgrade.php:1325` · `wordpress-develop-7.1.5/src/wp-includes/class-wp-xmlrpc-server.php:1799`
- Which API boundaries retain an explicit clear or root selection and which use omission? Root filtering, anonymous identity, and featured-image removal each need their own contract. `wordpress-develop-7.1.5/src/wp-includes/class-wp-query.php:769` · `wordpress-develop-7.1.5/src/wp-includes/user.php:724` · `wordpress-develop-7.1.5/src/wp-admin/includes/ajax-actions.php:2828`
- How many candidates require a source edit after shared helper changes? Dynamic callables, SQL fragments, hooks, generic variables, and serialized payloads require flow tracing. The audit gives a review estimate and a measured sample classification error. It cannot establish recall. `wordpress-develop-7.1.5/src/wp-includes/class-wp-query.php:5062` · `wordpress-develop-7.1.5/src/wp-includes/functions.php:7430`
- What is the verified behavior of the future driver and core patch against PostgreSQL and persistent cache? Acceptance requires regression runs through create/get/delete, authentication, hierarchy, signed query filters, REST, and cache invalidation. This spike performed static analysis. [Roadmap exit criteria](../08-roadmap.md)

## Method/reproduction

### Extraction and classification

The WordPress checkout had no `vendor/` directory. PHP CLI 8.4.27 exposed `token_get_all()`. The scanner lexes without loading WordPress, removes comments and inline HTML, keeps strings with their source position, and indexes balanced delimiters, call arguments, and named function scopes. Python applies the operand rules. It lexed 1,281 files. Of these, 829 were core paths and 452 bundled paths were screened for explicit core entity use. The bundled filter is in `source_files()` and `audit()` in the scanner. No reference checkout was modified.

| Kind | Detection and source example |
| --- | --- |
| Cast | Native integer casts, `absint()`, `intval()`, `abs()`, `wp_parse_id_list()`, and integer callback maps. `wordpress-develop-7.1.5/src/wp-includes/functions.php:5065` |
| Validation | Numeric predicates, integer filters, simple numeric route patterns, positive-number tests and loose ID comparison or membership. `wordpress-develop-7.1.5/src/wp-includes/class-wp-query.php:2264` |
| SQL format | Literal or locally resolved `prepare()` formats, argument positions, direct insert/update/replace/delete format arrays, and implicit wpdb field formats for resolved arrays or `compact()`. `wordpress-develop-7.1.5/src/wp-includes/load.php:746` · `wordpress-develop-7.1.5/src/wp-includes/taxonomy.php:3446` |
| Sentinel | Zero and selected `-1` defaults and comparisons, null/false/empty and recognizable presence or truthiness checks, and literal SQL zero predicates and schema defaults. `wordpress-develop-7.1.5/src/wp-includes/comment.php:3942` · `wordpress-develop-7.1.5/src/wp-admin/includes/schema.php:115` |
| Type declaration | Native `int` parameter and return declarations, including nullable and union forms, and REST array definitions with integer scalar or item schemas. `wordpress-develop-7.1.5/src/wp-includes/rest-api/endpoints/class-wp-rest-attachments-controller.php:94` · `wordpress-develop-7.1.5/src/wp-includes/rest-api/endpoints/class-wp-rest-attachments-controller.php:2462` |
| Query var | Known WP_Query keys at recognized definitions and call or array boundaries. Shared keys can also be found in other query classes that use the same argument conventions. `wordpress-develop-7.1.5/src/wp-includes/class-wp-query.php:626` · `wordpress-develop-7.1.5/src/wp-includes/class-wp-comment-query.php:897` |
| Cache key | Key operands, recognizable literal groups, bulk key calls and selected composite keys or group expressions. `wordpress-develop-7.1.5/src/wp-includes/class-wp-query.php:3306` · `wordpress-develop-7.1.5/src/wp-admin/includes/taxonomy.php:269` |
| Other | `insert_id` reads and writes, getter declarations, identity projections and options, selected arithmetic, sorting and numeric output formatting. `wordpress-develop-7.1.5/src/wp-includes/class-wpdb.php:2315` · `wordpress-develop-7.1.5/src/wp-includes/user.php:726` |

High confidence uses explicit fields, recognized query keys, or a directly identified entity column. Medium confidence uses contextual evidence such as controller/file names, known cache groups, local aliases, or a numeric field name. Low confidence marks unresolved operands. Ambiguous and numeric rows use a blank `entity`. Identity counts group by classified referenced entity. The patch proxy deduplicates by file and line after selecting in-scope casts, validations, SQL formats, native/REST types, explicit numeric and SQL sentinels, ID arithmetic, and `insert_id` consumers plus shared driver lines. The larger direct-review count selects every classified sentinel alongside those same kinds, with the shared driver lines excluded.

The scan has no interprocedural dataflow, PHPDoc parser, SQL AST, or runtime instrumentation. It can miss IDs passed through dynamic keys, wrappers, or serialized payloads. For example, the note mention parser combines a numeric regex against a class token with a separate ID assignment. The cast is detectable without following the regex capture. The install path embeds a literal sample post ID in a GUID. Both are additional source-review surfaces. `wordpress-develop-7.1.5/src/wp-includes/comment.php:2623` · `wordpress-develop-7.1.5/src/wp-admin/includes/upgrade.php:212`

### Manual validation

The [review sample](data/R-001-php-id-sample.csv) contains **80 source-reviewed rows**. The deterministic frame uses seed 1001 and draws 8 identity-classified rows per kind, 8 ambiguous rows, and 8 non-identity numeric rows. Each review checked the expression and surrounding code, including following a look-up or inspecting a schema field where needed.

- **Identity false-positive estimate in the sample was 0/64 (0%).** All 43 high-confidence and 21 medium-confidence sampled identity classifications matched the entity and the recorded pattern. The sample draws equally by kind, so this is an observed sample rate. It does not establish a corpus-wide error bound or exhaustiveness.
- **2/8 ambiguous rows were identity-related.** One was a cache helper with caller-dependent entities, and one was a cast in a deprecated attachment lookup. Four were ordinary numeric values and two were negated permission expressions. `wordpress-develop-7.1.5/src/wp-includes/functions.php:7430` · `wordpress-develop-7.1.5/src/wp-includes/deprecated.php:2000` · `wordpress-develop-7.1.5/src/wp-admin/includes/ajax-actions.php:2726`
- **0/8 sampled non-identity numerics were entity identities.** Examples include a widget instance number, a pagination count, and image dimensions or related presentation controls. `wordpress-develop-7.1.5/src/wp-admin/includes/ajax-actions.php:2426` · `wordpress-develop-7.1.5/src/wp-includes/sitemaps/providers/class-wp-sitemaps-taxonomies.php:174` · `wordpress-develop-7.1.5/src/wp-includes/widgets.php:565`

### Commands and acceptance checks

From the worktree root, with the pinned local checkout available at the given path:

```sh
ref=../../reference/wordpress-develop-7.1.5
hits=docs/research/data/R-001-php-id-hits.csv
php -l tools/research/R-001/tokens.php
python3 tools/research/R-001/scan.py "$ref" "$hits"
python3 -B tools/research/R-001/summarize.py "$hits"
python3 -B tools/research/R-001/summarize.py "$hits" --sample
```

`php -l` passed. A rerun to `/tmp/pressgres-r001-repeat.csv` matched the delivered inventory byte for byte using `cmp "$hits" /tmp/pressgres-r001-repeat.csv`. A Python check parsed both helpers, checked all 5,741 snippets against their source lines, confirmed 13 representative classifications, and matched the 80 reviewed rows to the generated sample frame. The locally cached `markdownlint-cli2` 0.24.0 reported zero issues with the repository config.
