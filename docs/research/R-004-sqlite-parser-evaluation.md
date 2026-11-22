# R-004 — SQLite Database Integration parser evaluation

**ADR-003 recommendation.** Reuse the pinned standalone `wordpress/mysql-parser` package as the MySQL front end, behind a Pressgres-owned AST adapter. Build a PostgreSQL 18 emitter and UUID-aware `wpdb` contracts in Pressgres. Both parsers accepted the same 435 of 437 syntax inputs, and the standalone package had lower median and p95 latency on this run. It also exposes a documented API without loading SQLite. Keep the SQLite driver as a source of semantic and regression cases. Proceed with the prototype while tracking review of the generated grammar's upstream notices and corresponding source as a redistribution gate. The standalone package documents its API and build inputs at `sqlite-database-integration-3.1.3/packages/mysql-parser/README.md:8` and `sqlite-database-integration-3.1.3/packages/mysql-parser/README.md:30`.

## Scope and acceptance

This spike covers the parser wired into SQLite Database Integration 3.1.3 and the separate parser shipped in the same reference tree. The WordPress input is `7.1.5-src`. PHP 8.4 and PostgreSQL 18 remain proposed Pressgres release targets. The PostgreSQL side assumes the UUID-only, case-preserving schema in the [data model](../04-data-model.md) and the typed adapter contract in the [architecture](../02-architecture.md). Versions are recorded at `sqlite-database-integration-3.1.3/packages/plugin-sqlite-database-integration/load.php:3` and `wordpress-develop-7.1.5/src/wp-includes/version.php:19`.

The deliverables are this report, the [corpus JSON](data/R-004-corpus.json), the [per-engine CSV](data/R-004-parse-results.csv), and the [extractor](../../tools/research/R-004/extract.php) and [harness](../../tools/research/R-004/parse.php). Acceptance checks cover source locations, every schema table definition, stable extraction, counts keyed by source and engine, and rejection of malformed input. Relevant failure modes are PHP assembly fragments that look like SQL, tokenization that stops before the end of a query, grammar drift, and syntax accepted with incompatible data or execution semantics. This run loaded parser files directly and executed zero SQL statements. Compatibility matrix status remains unverified. Schema and UUID contract changes would require the review described in [AI agent rules](../10-ai-agents.md).

## License and provenance

| Scope | Evidence and finding |
| --- | --- |
| Repository and WordPress plugin | The root and plugin Composer manifests declare GPL-2.0-or-later. The plugin header agrees, and both ship the GPL version 2 text. See `sqlite-database-integration-3.1.3/composer.json:3`, `sqlite-database-integration-3.1.3/LICENSE:1`, `sqlite-database-integration-3.1.3/packages/plugin-sqlite-database-integration/composer.json:3`, `sqlite-database-integration-3.1.3/packages/plugin-sqlite-database-integration/load.php:9` and `sqlite-database-integration-3.1.3/packages/plugin-sqlite-database-integration/LICENSE:1`. |
| Driver's own PHP under `packages/mysql-on-sqlite/src/{mysql,parser,sqlite}` and its loader | Package license is GPL-2.0-or-later, with the GPL v2 text. Classes have descriptive headers without individual license grants. The Workbench-derived lexer and grammar need the provenance checks in the next row. See `sqlite-database-integration-3.1.3/packages/mysql-on-sqlite/composer.json:7`, `sqlite-database-integration-3.1.3/packages/mysql-on-sqlite/LICENSE:1`, `sqlite-database-integration-3.1.3/packages/mysql-on-sqlite/src/mysql/class-wp-mysql-parser.php:3`, `sqlite-database-integration-3.1.3/packages/mysql-on-sqlite/src/parser/class-wp-parser.php:3`, `sqlite-database-integration-3.1.3/packages/mysql-on-sqlite/src/sqlite/class-wp-mysql-on-sqlite.php:32` and `sqlite-database-integration-3.1.3/packages/mysql-on-sqlite/src/load.php:9`. |
| Workbench-derived input, generator, generated driver grammar and lexer | `MySQLParser.g4` names Workbench 8.0.38, documents manual fixes, and retains two Oracle GPL-2.0-only notices with additional permission for separately licensed software included or referenced by the authors. `convert-grammar.php` has no separate grant and strips comments. Its output `mysql-grammar.php` has a generation marker and no license header. The driver lexer cites the Workbench lexer, token list and base lexer, and says it preserves Workbench token names and IDs. Those three upstream sources' original headers were unavailable in the pinned inputs. See `sqlite-database-integration-3.1.3/grammar-tools/MySQLParser.g4:2`, `sqlite-database-integration-3.1.3/grammar-tools/MySQLParser.g4:11`, `sqlite-database-integration-3.1.3/grammar-tools/MySQLParser.g4:63`, `sqlite-database-integration-3.1.3/grammar-tools/convert-grammar.php:26`, `sqlite-database-integration-3.1.3/grammar-tools/convert-grammar.php:291`, `sqlite-database-integration-3.1.3/packages/mysql-on-sqlite/src/mysql/mysql-grammar.php:2` and `sqlite-database-integration-3.1.3/packages/mysql-on-sqlite/src/mysql/class-wp-mysql-lexer.php:14` and `:51`. |
| Standalone `packages/mysql-parser/src/` and tooling | The package declares GPL-2.0-or-later and ships the GPL v2 text. The factory, token and parser files carry descriptive headers. The generated table names MySQL Server `mysql-8.4.10`. The lexer identifies generated MySQL token data and cites Workbench 8.0.38 for handwritten scanning behavior. The generation scripts pin `sql_yacc.yy` and `lex.h` by SHA-256. The snapshot lacks those Oracle source files and their original notices, so the exact upstream grants for these inputs remain unverified. See `sqlite-database-integration-3.1.3/packages/mysql-parser/composer.json:7`, `sqlite-database-integration-3.1.3/packages/mysql-parser/LICENSE:1`, `sqlite-database-integration-3.1.3/packages/mysql-parser/src/class-wp-mysql-parser-factory.php:3`, `sqlite-database-integration-3.1.3/packages/mysql-parser/src/parser/class-wp-parser-token.php:3`, `sqlite-database-integration-3.1.3/packages/mysql-parser/src/mysql-parse-table.php:2`, `sqlite-database-integration-3.1.3/packages/mysql-parser/src/class-wp-mysql-lexer.php:9` and `:23`, and `sqlite-database-integration-3.1.3/packages/mysql-parser/tools/fetch-mysql-grammar.sh:13`. |

The package declarations align with the Pressgres GPL-2.0-or-later license. For the Workbench-derived grammar, GPLv2 is the common version for a combined distribution. The package-level declaration supplies no evidence that Oracle's v2-only material can be relicensed under a later GPL version. Preserve copyright notices and exceptions, identify the applicable grants per artifact, and include the required corresponding source and build scripts when distributing. Review the MySQL Server inputs and Workbench lexer lineage before signing off on the standalone artifact. The GPL v2 text covers preservation of notices, modification and corresponding source at `sqlite-database-integration-3.1.3/LICENSE:79`, `:89` and `:137`, and version selection at `:239`. Pressgres's declaration is in the [repository README](../../README.md#license).

## Parser and driver architecture

### Parser wired into the SQLite driver

- The plugin release build packages `packages/mysql-on-sqlite/src/` under its `wp-includes/database` symlink. The loader wires `src/mysql/` and `src/parser/` to the AST-based driver in `src/sqlite/`. The root README describes the symlink packaging, and the driver points directly at its own grammar. See `sqlite-database-integration-3.1.3/README.md:20`, `sqlite-database-integration-3.1.3/packages/mysql-on-sqlite/src/load.php:12` and `sqlite-database-integration-3.1.3/packages/mysql-on-sqlite/src/sqlite/class-wp-mysql-on-sqlite.php:40`.
- The lexer scans bytes into `WP_MySQL_Token` objects with token IDs, byte locations and accessors for raw bytes and decoded values. Its inputs include the server version and SQL modes, with MySQL 8.0.38 the lexer default. The custom PHP generator consumes the edited ANTLR `.g4` with no ANTLR runtime, and writes numeric productions and rule names to `mysql-grammar.php`. `WP_Parser_Grammar` inflates the rules and computes lookahead. The recursive-descent parser tests alternative branches and inlines synthetic grammar fragments. See `sqlite-database-integration-3.1.3/packages/mysql-on-sqlite/src/mysql/class-wp-mysql-lexer.php:2230` and `:2323`, `sqlite-database-integration-3.1.3/packages/mysql-on-sqlite/src/mysql/class-wp-mysql-token.php:52`, `sqlite-database-integration-3.1.3/grammar-tools/convert-grammar.php:26` and `:269`, `sqlite-database-integration-3.1.3/packages/mysql-on-sqlite/src/parser/class-wp-parser-grammar.php:65` and `sqlite-database-integration-3.1.3/packages/mysql-on-sqlite/src/parser/class-wp-parser.php:49`.
- The output is a grammar-shaped tree with `WP_Parser_Node` branches and token leaves. A typical path is `query → simpleStatement → selectStatement`. The driver-facing API is `WP_MySQL_Lexer::remaining_tokens()`, `WP_Parser_Grammar($table)`, and `WP_MySQL_Parser($grammar, $tokens)` with `reset_tokens()`, `next_query()` and `get_query_ast()`. The parser and driver's `create_parser()` carry private-access annotations, so consuming them would couple Pressgres to implementation details. See `sqlite-database-integration-3.1.3/packages/mysql-on-sqlite/src/parser/class-wp-parser-node.php:3`, `sqlite-database-integration-3.1.3/packages/mysql-on-sqlite/src/mysql/class-wp-mysql-parser.php:3` and `:47`, and `sqlite-database-integration-3.1.3/packages/mysql-on-sqlite/src/sqlite/class-wp-mysql-on-sqlite.php:1611` and `:1862`.
- The physical separation works at the parser boundary. The harness loaded lexer, grammar and AST classes without a connection or WordPress bootstrap. The SQLite emitter itself lives inside the PDO driver. `execute_mysql_query()` dispatches on statement rules. Private `translate()` and `translate_token()` dispatch on branch names and token IDs, and recurse through ordered children when applicable. Execution handlers call PDO, use emulated information schema metadata and update driver state. Some translations also execute queries during the walk, as with `FOUND_ROWS()`. See `sqlite-database-integration-3.1.3/packages/mysql-on-sqlite/src/sqlite/class-wp-mysql-on-sqlite.php:1647`, `:1862`, `:3849`, `:4317`, `:4564`, `:4641` and `:5378`. Default token passthrough and removal of locking clauses are further reasons to build a PostgreSQL emitter with explicit semantic rules. See the same file at `:4546` and `:4628`.
- The driver package declares PHP >=7.2, PDO and PDO SQLite. The driver also documents use of PCRE and registers SQLite-specific functions. The isolated parser ran on PHP 8.4.27 in this spike. See `sqlite-database-integration-3.1.3/packages/mysql-on-sqlite/composer.json:18` and `sqlite-database-integration-3.1.3/packages/mysql-on-sqlite/src/sqlite/class-wp-mysql-on-sqlite.php:35` and `:956`.

### Standalone parser

- The standalone package uses a PHP LALR(1) shift/reduce parser. Bison 3.8.2 generates an automaton from MySQL Server 8.4.10's `sql_yacc.yy`. PHP tools convert the automaton and `lex.h` to a compact PHP parse table and lexer constants. The build discards Bison's generated C source. Bash, curl, Docker, Bison and PHP are build dependencies, and the package declares PHP >=7.2 as its only runtime requirement. See `sqlite-database-integration-3.1.3/packages/mysql-parser/bin/build-grammar:3`, `sqlite-database-integration-3.1.3/packages/mysql-parser/tools/run-bison.sh:24`, `sqlite-database-integration-3.1.3/packages/mysql-parser/composer.json:18` and `sqlite-database-integration-3.1.3/packages/mysql-parser/src/parser/class-wp-parser.php:53`.
- Use the documented `WP_MySQL_Parser_Factory::create_parser()`, `WP_MySQL_Lexer($sql, $version, $modes)->remaining_tokens()` and `WP_Parser::parse($tokens)`. The relevant AST API is `rule_name`, ordered children and child or descendant queries. Token IDs match grammar terminals, with raw byte spans and decoded values available. Rule names such as `select_item` and `simple_expr` differ from the driver's camel-case rules. These are grammatical nodes, so Pressgres still needs its own identifier, type and semantic context. Keep rule names and token constants inside the adapter and snapshot representative AST shapes on every pin update. Both packages declare overlapping global class names, which prevents loading both under their original names in one PHP process. See `sqlite-database-integration-3.1.3/packages/mysql-parser/README.md:30`, `sqlite-database-integration-3.1.3/packages/mysql-parser/src/class-wp-mysql-lexer.php:364`, `sqlite-database-integration-3.1.3/packages/mysql-parser/src/parser/class-wp-parser-node.php:13` and `:205`, `sqlite-database-integration-3.1.3/packages/mysql-parser/src/parser/class-wp-parser-token.php:11`, and `sqlite-database-integration-3.1.3/packages/mysql-on-sqlite/src/parser/class-wp-parser-node.php:6`.
- Version and mode settings affect lexing. The standalone table remains fixed to its generation input. The standalone package's own tests pin an expected failure list against MySQL Server's corpus. Those tests were outside this run. Pin and test the intended input mode profile for WordPress on every dependency update. See `sqlite-database-integration-3.1.3/packages/mysql-parser/src/class-wp-mysql-lexer.php:364`, `sqlite-database-integration-3.1.3/packages/mysql-parser/src/mysql-parse-table.php:2` and `sqlite-database-integration-3.1.3/packages/mysql-parser/tests/WP_MySQL_Server_Suite_Parser_Tests.php:15`.

## Corpus and grammar coverage

The extractor recorded **1,282 call sites** across `src` and `tests/phpunit`, plus **19 schema definitions** and **14 supplemental cases**. The 19 include the single-site and multisite variants of `users` and the multisite-only DDL. See `wordpress-develop-7.1.5/src/wp-admin/includes/schema.php:56`, `:192`, `:210`, `:230` and `:248`.

| Input or classification | Core | PHPUnit | Total | Accepted by each parser |
| --- | ---: | ---: | ---: | ---: |
| Heuristic statement | 282 | 122 | 404 | 402 |
| Schema definitions | 19 | 0 | 19 | 19 |
| Dynamic or nested wrapper | 346 | 119 | 465 | — |
| Table-name argument to a CRUD helper | 114 | 87 | 201 | — |
| Fragment or non-SQL literal | 104 | 6 | 110 | — |
| Indirect argument with no literal | 90 | 12 | 102 | — |
| Materialized examples from assembled SQL | 9 | 1 | 10 | 10 |
| Synthetic dialect probes, with contextual sources | 4 | 0 | 4 | 4 |

Each engine received 423 extracted SQL inputs (321 distinct byte strings) and 14 supplemental inputs. Each accepted **421/423 extracted inputs (99.53%)** and **435/437 overall**. Both had two grammar rejects, zero lexical rejects, zero trailing-token rejects and zero runtime errors in the corpus. A qualifying AST gives evidence about syntax for the input bytes and mode used. It gives no evidence about matched rows, types, constraints, behavior on a live MySQL server, or PostgreSQL translation. For example, the corpus includes MySQL-only test procedures and historical WordPress upgrade DDL. See `wordpress-develop-7.1.5/tests/phpunit/tests/db.php:732` and `wordpress-develop-7.1.5/src/wp-admin/includes/upgrade.php:3768).

Both failures were fixtures where the extractor identified a SQL-looking prefix:

| Corpus ID | Observed failure | Source review |
| --- | --- | --- |
| `R004-0566` | Both lexers completed. Both parsers returned null. | The prepared prefix leaves a parenthesis open. WordPress appends optional author email and a closing clause before `get_var()`. Both engines accepted the separately materialized branch without email. See `wordpress-develop-7.1.5/src/wp-includes/comment.php:759` and `:771`. |
| `R004-1090` | Both lexers completed. Both parsers returned null. | This is a negative PHPUnit test. PHP single quotes preserve literal `{$wpdb->postmeta}` and `$part`. The test expects `prepare()` to return null. See `wordpress-develop-7.1.5/tests/phpunit/tests/db.php:2160` and `:2169`. |

### Manual audit and confidence

I reviewed the source and rendered SQL for a deterministic sample of 40 eligible inputs (22 core call-site statements, 13 PHPUnit call-site statements and five schema definitions), plus the one rejected input outside that sample and ten excluded hits. Of the 40, **one** was a false positive for a self-contained SQL input, an estimated **2.5% false-positive rate** in this sample. The sample's false positive is the comment prefix. The other reject, `R004-1090`, was outside the sample and is a second known false positive in the total. The ten exclusions comprised three dynamic SQL shapes, one nested dynamic format, four wrappers with a separately extracted inner statement and two clause fragments. Examples are at `wordpress-develop-7.1.5/src/wp-includes/taxonomy.php:4111`, `wordpress-develop-7.1.5/tests/phpunit/tests/option/wpSetOptionsAutoload.php:140`, `wordpress-develop-7.1.5/tests/phpunit/tests/option/option.php:431` and `wordpress-develop-7.1.5/src/wp-includes/class-wp-query.php:2103`. This excluded sample checks the rule's behavior. It leaves recall across runtime SQL undetermined.

- **High confidence** applies to reversible PHP lexical captures, direct statement-shaped literals and the schema reconstruction for the chosen charset and prefix. **Medium confidence** applies to synthetic placeholder substitutions, assembled examples and the heuristic split between dynamic templates and fragments. The exact `wpdb::prepare()` formatting, quoting and argument validation are richer than the benchmark substitution. See `wordpress-develop-7.1.5/src/wp-includes/class-wpdb.php:1395`, `:1483` and `:1597`.
- **Low confidence** applies to any extrapolation to runtime coverage. Query builders assemble, filter and cache requests. The corpus underrepresents those paths, and test calls can intentionally exercise mismatched formats or malformed inputs. See `wordpress-develop-7.1.5/src/wp-includes/class-wp-query.php:3207` and `wordpress-develop-7.1.5/tests/phpunit/tests/db.php:2163`.
- The 40 reviewed IDs in sample order are `0305 0223 0311 0894 0139 1103 1187 0317 1172 0274 1203 0135 1181 0566 1025 0267 0134 1131 0322 0127 0491 0917 0182 0085 0277 0131 0789 0098 1034 0573 0643 0562 1045 1053 0972 1033 0509 0240 0256 1156`. The ten excluded IDs are `1169 0266 1186 0738 0902 0439 0398 0458 1228 0621`. Each has prefix `R004-` and a path and line in the corpus.

## Performance

One local CLI run per parser on a MacBook Pro (`MacBookPro18,1`, arm64), macOS 27.0.1 (Darwin 27.0.0), Laravel Herd PHP **8.4.27 NTS**, CLI OPcache disabled. Each input was tokenized and parsed once after grammar initialization. The driver and standalone lexers used their default versions (8.0.38 and 8.4.10 respectively) and an empty SQL-mode array. The full SQLite driver passes its configured SQL modes to the lexer, so the driver column measures the front end in isolation. See `sqlite-database-integration-3.1.3/packages/mysql-on-sqlite/src/mysql/class-wp-mysql-lexer.php:2230`, `sqlite-database-integration-3.1.3/packages/mysql-parser/src/class-wp-mysql-lexer.php:364` and `sqlite-database-integration-3.1.3/packages/mysql-on-sqlite/src/sqlite/class-wp-mysql-on-sqlite.php:1619`.

| Metric | SQLite driver's front end | Standalone |
| --- | ---: | ---: |
| Minimum per statement | 12.292 µs | 6.166 µs |
| Median per statement | 140.125 µs | 26.708 µs |
| p95 per statement | 434.208 µs | 92.959 µs |
| Total timed lexer + parser and result checks | 79.745 ms | 17.165 ms |
| Whole corpus-loop wall time, including CSV writes | 87.902 ms | 19.230 ms |
| Grammar initialization plus class loading | 4.397 ms | 5.591 ms |
| PHP heap before initialization, corpus loaded | 3,326,784 bytes | 3,326,832 bytes |
| PHP heap after initialization | 6,436,328 bytes | 7,426,104 bytes |
| Peak PHP heap through corpus loop | 7,411,176 bytes | 8,284,952 bytes |
| Peak reserved PHP heap | 8,388,608 bytes | 10,485,760 bytes |

The driver caches its inflated grammar in a static property and resets one parser instance per driver with each fresh token stream. The standalone factory shares an expanded grammar among parsers. Its parser creates fresh stacks per query. Both lexer/parser paths reprocess SQL on subsequent calls. The driver's `current_ast` holds the current parse until reset. The measurements include the loaded JSON in heap totals and say nothing about process RSS, web workers, a PostgreSQL emitter, DB latency or capacity. See `sqlite-database-integration-3.1.3/packages/mysql-on-sqlite/src/sqlite/class-wp-mysql-on-sqlite.php:959` and `:1619`, `sqlite-database-integration-3.1.3/packages/mysql-on-sqlite/src/mysql/class-wp-mysql-parser.php:17`, `sqlite-database-integration-3.1.3/packages/mysql-parser/src/class-wp-mysql-parser-factory.php:12` and `sqlite-database-integration-3.1.3/packages/mysql-parser/src/parser/class-wp-parser.php:66`.

## Fit for PostgreSQL

The following are proposed rules and acceptance tests for a Pressgres emitter. Parser acceptance was measured. PostgreSQL semantics still require disposable PostgreSQL fixtures with UUID schema constraints, plus comparison against MySQL where equivalence is claimed. The SQLite code supplies useful test ideas, including ASCII-only behavior it documents for `LIKE` and the count query it issues for `FOUND_ROWS()`. See `sqlite-database-integration-3.1.3/packages/mysql-on-sqlite/src/sqlite/class-wp-mysql-on-sqlite.php:2403` and `:5129`.

| SQL category | Proposed PostgreSQL handling and test cases | WordPress or driver evidence |
| --- | --- | --- |
| Identifiers and `"ID"` | Resolve qualified names, aliases and column scope against the pinned schema map. Emit separately quoted PostgreSQL components, including `"ID"` and mixed-case names such as `"comment_ID"`. Bind values and resolve identifiers from metadata. Test lower-case and quoted input, joins, wildcard projections, result keys and ambiguous names. | `wordpress-develop-7.1.5/src/wp-admin/includes/schema.php:101` and `:159`. `sqlite-database-integration-3.1.3/packages/mysql-on-sqlite/src/sqlite/class-wp-mysql-on-sqlite.php:4717`. |
| `LIMIT x,y` | Emit `LIMIT y OFFSET x` from the AST with typed numeric binds. Test asymmetric offset and count, zero count, and order stability on paged core paths. | `wordpress-develop-7.1.5/src/wp-admin/includes/class-wp-importer.php:35`. |
| `SQL_CALC_FOUND_ROWS` / `FOUND_ROWS()` | Patch managed pagination to request a count with the same filters and cardinality as the unpaginated relation. Keep count and page in one consistent snapshot. Test DISTINCT, GROUP BY, UNION, empty page, nested limits and repeated calls. For approved raw callers, emulate paired state only with a defined same-session contract. | `wordpress-develop-7.1.5/src/wp-includes/class-wp-query.php:3191`, `:3207` and `:3722`. `sqlite-database-integration-3.1.3/packages/mysql-on-sqlite/src/sqlite/class-wp-mysql-on-sqlite.php:2356` and `:5378`. |
| `ON DUPLICATE KEY UPDATE` | Use `ON CONFLICT (known_key) DO UPDATE` for a reviewed unique key, with `EXCLUDED` for inserted-value references where equivalent. Preserve the existing row's UUID. Test competing constraints, repeated keys within a batch, trigger effects and affected-row expectations. Reject ambiguous conflict targets. | `wordpress-develop-7.1.5/src/wp-includes/option.php:1142` and `wordpress-develop-7.1.5/src/wp-admin/includes/schema.php:141`. `sqlite-database-integration-3.1.3/packages/mysql-on-sqlite/src/sqlite/class-wp-mysql-on-sqlite.php:2474` and `:4956`. |
| `INSERT IGNORE` | Approve targeted `ON CONFLICT (option_name) DO NOTHING` for known option locks, where zero affected rows means another claimant won. Let other constraint and conversion errors surface. Test simultaneous lock attempts and invalid input. | `wordpress-develop-7.1.5/src/wp-admin/includes/class-wp-upgrader.php:1096`, `wordpress-develop-7.1.5/src/wp-includes/comment.php:4424` and `wordpress-develop-7.1.5/src/wp-admin/includes/schema.php:147`. |
| `REPLACE` | Block generic translation. Deleting and reinserting on conflict can change UUID identity, foreign keys, defaults, trigger behavior and row counts. Patch a managed caller to an explicit update or insert after reviewing its contract. Test the replacement expectations for an existing key and for omitted columns. | `wordpress-develop-7.1.5/src/wp-includes/class-wpdb.php:2557` and `wordpress-develop-7.1.5/tests/phpunit/tests/db.php:677`. `sqlite-database-integration-3.1.3/packages/mysql-on-sqlite/src/sqlite/class-wp-mysql-on-sqlite.php:2436`. |
| `IFNULL(a,b)` | Consider `COALESCE(a,b)` for approved type pairs. Check inferred result type, collation, NULL and empty values. Reject mixed coercions that change value semantics. | The corpus's `synthetic_ifnull` was a syntax probe. The standalone parser retains grammar rule and token children at `sqlite-database-integration-3.1.3/packages/mysql-parser/src/parser/class-wp-parser.php:92`. |
| `FIELD()` | Patch managed inclusion ordering to use a typed UUID list. An emitter rule could use a typed `array_position()` or ordered `CASE` with an explicit zero fallback. Test duplicate matches, missing items, NULLs, mixed types and text collation. | `wordpress-develop-7.1.5/src/wp-includes/class-wp-term-query.php:930` and `wordpress-develop-7.1.5/src/wp-includes/class-wp-query.php:1785`. `sqlite-database-integration-3.1.3/packages/mysql-on-sqlite/src/sqlite/class-wp-sqlite-pdo-user-defined-functions.php:603`. |
| `DATE_ADD`, `DATE_SUB`, `DATE_FORMAT` and other date functions | Translate known interval units and format directives to typed interval/date expressions and an allowlisted format map. Test time zones and DST, month-end behavior, compound units, zero-date policy and escaped percent directives. | `wordpress-develop-7.1.5/src/wp-includes/comment.php:431`, `wordpress-develop-7.1.5/src/wp-includes/post.php:8385`, `wordpress-develop-7.1.5/src/wp-includes/general-template.php:2632` and `wordpress-develop-7.1.5/src/wp-admin/includes/upgrade.php:1037`. |
| `REGEXP` / `NOT REGEXP` | Allow reviewed patterns through bound regex operands with explicit binary or case behavior. Treat PostgreSQL regex operators as candidate equivalents for a bounded subset. Test Unicode, escaping, anchors and negation. Reject unknown pattern semantics. | `wordpress-develop-7.1.5/src/wp-admin/includes/schema.php:708` and `wordpress-develop-7.1.5/src/wp-includes/class-wp-meta-query.php:752`. `sqlite-database-integration-3.1.3/packages/mysql-on-sqlite/src/sqlite/class-wp-mysql-on-sqlite.php:5161`. |
| `SHOW TABLES/COLUMNS/INDEX`, `DESCRIBE` | Build catalog-backed metadata queries or patch managed introspection to consume native schema metadata. Match expected names, order, visibility and index details for any compatible response, including `Field`, `Type`, `Key_name`, `Column_name`, `Sub_part` and `Seq_in_index`. Restrict metadata to the allowed schema and test both `LIKE` and supported filters. Keep `EXPLAIN` on a separate path. | `wordpress-develop-7.1.5/src/wp-admin/includes/upgrade.php:2269`, `:2632`, `:3027` and `:3270`. `sqlite-database-integration-3.1.3/packages/mysql-on-sqlite/src/sqlite/class-wp-mysql-on-sqlite.php:3849`. |
| Collations and case-insensitive `LIKE` | Make text comparison a column and operation policy. Test candidate PostgreSQL collations or `ILIKE` against representative accented and case-variant Unicode, binary comparisons, escaped wildcards and index behavior. Include uniqueness and sorting in that review. | `wordpress-develop-7.1.5/src/wp-includes/class-wpdb.php:901` and `:1763`. `sqlite-database-integration-3.1.3/packages/mysql-on-sqlite/src/sqlite/class-wp-mysql-on-sqlite.php:5115`. |
| `LAST_INSERT_ID()`, `LAST_INSERT_ID(expr)` and `$wpdb->insert_id` | Capture generated UUIDs with statement-scoped `RETURNING "ID"` or the mapped PK. Patch managed PHP to preserve the returned canonical string. Reject raw `LAST_INSERT_ID` calls by default, including the setter-like argument form. For any reviewed adapter, define transaction and connection state, multirow result policy, rollback and failed insert behavior. | Both raw forms are synthetic probes. WordPress reads MySQL insert identity at `wordpress-develop-7.1.5/src/wp-includes/class-wpdb.php:2313` and casts it at `wordpress-develop-7.1.5/src/wp-includes/post.php:5041`. The SQLite driver's wrapper explicitly converts numeric IDs at `sqlite-database-integration-3.1.3/packages/mysql-on-sqlite/src/sqlite/class-wp-sqlite-driver.php:159`. |

**Reuse, fork, or build.** Pin the standalone artifact and add a small Pressgres adapter that enforces complete lexing, one statement, resource bounds and an allowlist of semantic AST shapes. The parser shares grammar labels with the generated table, so fixture and AST snapshots should gate upgrades. Keep a narrowly scoped fork as a fallback for required fixes that upstream cannot ship or for packaging required to avoid class collisions. A fork would inherit grammar provenance and update obligations. A new parser would add grammar maintenance with no demonstrated gain on this corpus. The Workbench driver parser remains a feasible prototype fallback if needed, with private interfaces and lower measured throughput here. See `sqlite-database-integration-3.1.3/packages/mysql-parser/README.md:40`, `sqlite-database-integration-3.1.3/packages/mysql-parser/src/parser/class-wp-parser.php:92` and `sqlite-database-integration-3.1.3/packages/mysql-on-sqlite/src/mysql/class-wp-mysql-parser.php:3`.

**Upstream collaboration.** The documented issue tracker and standalone parser tests offer a place to propose minimized grammar regressions, token diagnostics, clearer notices and a stable AST contract. The monorepo describes its execution layer as MySQL emulation on SQLite, with SQLite-specific PDO, connection and metadata behavior. A PostgreSQL emitter is architecturally feasible as a separate consumer of the parser. An upstream package for PostgreSQL would depend on maintainer interest, which this snapshot cannot establish. See `sqlite-database-integration-3.1.3/packages/mysql-parser/composer.json:14`, `sqlite-database-integration-3.1.3/packages/mysql-parser/README.md:96`, `sqlite-database-integration-3.1.3/README.md:12` and `sqlite-database-integration-3.1.3/packages/mysql-on-sqlite/src/sqlite/class-wp-mysql-on-sqlite.php:35`.

## Summary of findings

- Both parser paths accepted 421 of 423 extracted inputs, including all 19 schema definitions, and all 14 supplemental inputs. Source review attributed both rejects to extraction or test context. The [CSV](data/R-004-parse-results.csv) records each result.
- The standalone parser exposes a documented PHP front end, with a 26.708 µs local median versus 140.125 µs for the SQLite driver's front end. Its measured heap peak was higher. The underlying cache in both paths is the prepared grammar, with per-query lexing and parsing. See `sqlite-database-integration-3.1.3/packages/mysql-parser/src/class-wp-mysql-parser-factory.php:19` and `sqlite-database-integration-3.1.3/packages/mysql-on-sqlite/src/sqlite/class-wp-mysql-on-sqlite.php:959` and `:1619`.
- Package license declarations align with Pressgres's GPL choice. The Workbench grammar retains Oracle's GPLv2 terms and a linking permission. The original notices for the standalone generated inputs are pending verification. See `sqlite-database-integration-3.1.3/grammar-tools/MySQLParser.g4:11`, `sqlite-database-integration-3.1.3/packages/mysql-parser/composer.json:7` and `sqlite-database-integration-3.1.3/packages/mysql-parser/tools/fetch-mysql-grammar.sh:13`.

## Implications for the UUID patchset

| Category | Patch strategy |
| --- | --- |
| Identity-bearing arguments, results and predicates | Patch PHP at the managed `wpdb` and core boundaries to preserve full UUIDv7 strings. For SQL use schema-aware bind types and quote case-sensitive names. Convert legacy zero sentinels to NULL only at known absent-reference fields, including predicate semantics. Replace identity `%d` formats and PHP integer casts. Leave legitimate numeric offsets and counts numeric. See `wordpress-develop-7.1.5/src/wp-includes/class-wpdb.php:1395`, `wordpress-develop-7.1.5/src/wp-includes/post.php:5041` and `wordpress-develop-7.1.5/src/wp-includes/class-wp-query.php:3362`. |
| Generated IDs and identity-sensitive writes | Patch insert result handling around UUID-valued `RETURNING`. Handle reviewed conflicts in the semantic emitter, and patch managed callers that need explicit replacement semantics. Gate raw `LAST_INSERT_ID` and generic `REPLACE` on an approved contract. See `wordpress-develop-7.1.5/src/wp-includes/class-wpdb.php:2313` and `:2557`, and `wordpress-develop-7.1.5/tests/phpunit/tests/db.php:677`. |
| Query shaping and scalar syntax | Implement identifier resolution, comma `LIMIT`, approved scalar/date functions, regex and text comparison in the emitter. Patch managed pagination and ID-list ordering where SQL assembly or PHP coercion needs changing. See `wordpress-develop-7.1.5/src/wp-admin/includes/class-wp-importer.php:35`, `wordpress-develop-7.1.5/src/wp-includes/class-wp-query.php:1785` and `:3191`. |
| Installation and introspection | Supply native PostgreSQL DDL via versioned schema migrations, and patch WordPress install/upgrade to use managed metadata or approved catalog-backed result shapes. Carry over semantic fixtures for legacy DDL where the migration path requires it. See `wordpress-develop-7.1.5/src/wp-admin/includes/schema.php:56` and `wordpress-develop-7.1.5/src/wp-admin/includes/upgrade.php:3027` and `:3270`. |

## Open questions

- Confirm original notices and corresponding-source requirements for the pinned MySQL Server `sql_yacc.yy` and `lex.h` and the Workbench lexer files. Determine a packaging approach that preserves the notices and avoids global class collisions. See `sqlite-database-integration-3.1.3/packages/mysql-parser/tools/fetch-mysql-grammar.sh:13` and `sqlite-database-integration-3.1.3/packages/mysql-parser/src/class-wp-mysql-lexer.php:23`.
- Measure runtime coverage with a redacted capture from disposable WordPress fixtures, including filter-generated SQL, dynamic lists, upgrade paths and plugin queries. Confirm the pinned SQL mode profile, PostgreSQL semantics, error and row-count behavior, and resource limits with one configuration per tested release. The current corpus captures shape gaps such as filtered request assembly at `wordpress-develop-7.1.5/src/wp-includes/class-wp-query.php:3207` and driver mode selection at `sqlite-database-integration-3.1.3/packages/mysql-on-sqlite/src/sqlite/class-wp-mysql-on-sqlite.php:1619`.
- Confirm whether upstream wants AST stabilization or a separate PostgreSQL consumer in its repository. The published scope centers on SQLite at `sqlite-database-integration-3.1.3/README.md:9`.

## Method/reproduction

The extractor uses PHP's tokenizer over `src/**/*.php` and `tests/phpunit/**/*.php`, skips comments, and visits direct `$wpdb` calls plus `$this` calls inside `class-wpdb.php`. One row represents an occurrence, including nested `prepare()` calls. The first argument is stored with its literal tokens, source location and unresolved expressions. The CRUD helpers accept tables and arrays, so the table arguments are inventoried and selected helper-generated queries appear as separate materialized cases. The extractor folds literal concatenation, resolves allowlisted table and prefix interpolations, and supplies fixed placeholder values (`7`, `1.25`, `'r004'` and the quoted identifier `wp_r004`). It instantiates every schema definition with prefix `wp_`, index prefix length 191 and one `utf8mb4_unicode_520_ci` variant. PHP strings with non-UTF-8 SQL bytes are stored as base64. This is a static extraction with no variable tracing or real `wpdb::prepare()` execution. Examples of assembly, formatting and binary fixtures are at `wordpress-develop-7.1.5/src/wp-includes/class-wpdb.php:1458`, `:2610` and `:4110`, `wordpress-develop-7.1.5/src/wp-admin/includes/schema.php:39` and `:53`, and `wordpress-develop-7.1.5/tests/phpunit/tests/db.php:1272`.

The harness checks that the lexer reached EOF and tests complete single-statement parsing. Smoke inputs cover valid SQL with and without a semicolon, missing quotes with and without a preceding valid statement, invalid grammar and multiple statements. Neither parser exposes a grammar-error position via the exercised API. The CSV records each parser's status and first AST child rule or root rule. Timing starts after reading the corpus, with grammar initialization measured separately. p95 uses the nearest-rank index. See `sqlite-database-integration-3.1.3/packages/mysql-on-sqlite/src/mysql/class-wp-mysql-lexer.php:2332`, `sqlite-database-integration-3.1.3/packages/mysql-on-sqlite/src/sqlite/class-wp-mysql-on-sqlite.php:1115`, `sqlite-database-integration-3.1.3/packages/mysql-parser/src/class-wp-mysql-lexer.php:449` and `sqlite-database-integration-3.1.3/packages/mysql-parser/src/parser/class-wp-parser.php:113`.

Run from the worktree root with PHP 8.4 CLI and its tokenizer extension. Use an already installed markdownlint-cli2 for the final command.

```sh
set -e
wp_ref=../../reference/wordpress-develop-7.1.5
sqlite_ref=../../reference/sqlite-database-integration-3.1.3
corpus=docs/research/data/R-004-corpus.json
results=docs/research/data/R-004-parse-results.csv

for file in tools/research/R-004/*.php; do php -l "$file"; done
php -d display_errors=stderr tools/research/R-004/extract.php "$wp_ref" > "$corpus"
{
  php -d opcache.enable_cli=0 tools/research/R-004/parse.php "$sqlite_ref" "$corpus" driver
  php -d opcache.enable_cli=0 tools/research/R-004/parse.php "$sqlite_ref" "$corpus" standalone --no-header
} > "$results"
markdownlint-cli2 docs/research/R-004-sqlite-parser-evaluation.md
```

The following recreates the classification counts, compares engine statuses and selects the two review samples. Sample judgments require opening each referenced source.

```sh
python3 - <<'PY'
import base64
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

data = Path('docs/research/data')
with (data / 'R-004-corpus.json').open() as stream:
    corpus = json.load(stream)
with (data / 'R-004-parse-results.csv').open(newline='') as stream:
    results = list(csv.DictReader(stream))

def scope(row):
    return 'core' if '/src/' in row['source'] else 'test'

def rank(row):
    return hashlib.sha256(('R-004-review-v1:' + row['id']).encode()).hexdigest()

print(Counter((scope(row), row['kind']) for row in corpus))
print(Counter((row['engine'], row['kind'], scope(row), row['status']) for row in results))
eligible = [row for row in corpus if row['kind'] in {'statement', 'schema'}]
excluded = [row for row in corpus if row['kind'] in {'dynamic', 'fragment_or_non_sql'}]
status = {
    engine: {row['id']: row['status'] for row in results if row['engine'] == engine}
    for engine in ('driver', 'standalone')
}
assert status['driver'] == status['standalone']
assert len(status['driver']) * 2 == len(results)
sql = [row['sql'].encode() if row['sql'] is not None else base64.b64decode(row['sql_base64'])
       for row in eligible]
print('distinct extracted SQL byte strings', len(set(sql)))
for sample in (sorted(eligible, key=rank)[:40], sorted(excluded, key=rank)[:10]):
    for row in sample:
        print(row['id'], row['source'], row.get('php_argument', row['sql']))
PY
```
