# 08 — Roadmap, tasks, milestones, dependencies

This is a **dependency-based roadmap, not a date forecast**. Milestones require objective evidence; phases may run partly in parallel only where safe. Size levels: S 1–3 days, M 1–2 weeks, L multi-week / research; estimates deliberately not commitments.

## M0 — Feasibility and ADR sign-off (Research)

- [ ] R-001 audit WP 7.1 integer ID assumptions in PHP and editor/REST (L).
- [ ] R-002 enumerate WP schema and plugin installation/upgrade SQL paths (M).
- [ ] R-003 prototype `uuidv7()` and `INSERT ... RETURNING "ID"` via `$wpdb` adapter (M).
- [ ] R-004 choose SQL parser license, grammar scope and performance approach (M).
- [ ] R-005 choose WordPress patching mechanism and verify redistribution/licensing obligations (M).
- [ ] R-006 implement threat model and proof-of-concept plugin sandbox (M).
- [ ] R-007 record ADR-001..011 and go/no-go decision (S).
- [ ] R-008 user discovery: interview 5–10 PostgreSQL-standardized organizations, pick first persona (M).
- [ ] R-009 baseline the upstream WordPress core PHPUnit suite against the PostgreSQL prototype; publish pass rate (M).
- [ ] R-010 ADR: object cache backend, Redis vs Valkey licensing (S).
- [ ] R-011 document the UUID-only rationale and requirements (why not dual IDs) (S).
- [ ] R-012 audit block editor / JS packages / REST clients for numeric-ID assumptions (L).
- [ ] R-013 estimate core patchset size and per-release rebase cost (M).
- [ ] R-014 select the two initial plugin compatibility targets (S).
- [ ] R-015 licensing and trademark clearance for name and repository LICENSE (M).

**Exit:** demonstrable UUID insert/get across PHP + REST without truncation, and documented patch scope. **Hard stop** if viable managed patchset strategy not found.

## M1 — Installer foundation (Alpha skeleton)

- [ ] I-001 PHP Composer monorepo, autoload and interfaces (M).
- [ ] I-002 `wps init`, config JSON schema, secret ref validation (M).
- [ ] I-003 `wps doctor`, preflight, structured error codes (M).
- [ ] I-004 release lockfile, artifact integrity verification (M).
- [ ] I-005 install plan/state machine, idempotent resume and advisory lock (L).
- [ ] I-006 base Docker Compose and DDEV PostgreSQL + Redis profile (M).
- [ ] I-007 CI gates, issue templates, CODEOWNERS and agents (S).
- [ ] I-009 `wps version` and `--format=json` output contract (S).
- [ ] I-010 CI: WordPress core PHPUnit suite on PostgreSQL with pass-rate trend (M).
- [ ] I-011 CI matrix: required stack plus exploratory PHP 8.5 / PG 19 (M).

**Exit:** deterministic no-write plan and reproducible local stack; invalid environment fails before mutation; core PHPUnit pass rate tracked in CI.

## M2 — Core PostgreSQL + native UUIDv7 alpha

- [ ] D-001 implement PHP PDO PostgreSQL driver, result shape mapping (L).
- [ ] D-002 implement `$wpdb` facade, `insert_id` UUID-aware contract (L).
- [ ] D-003 schema registry and PG native core schema migrations (L).
- [ ] D-004 query source attribution and unsupported-query logging (M).
- [ ] U-001 managed core patchset ID casts and type constraints (L).
- [ ] U-002 adapt core REST schemas/routes and editor consumers (L).
- [ ] U-003 adapt users/comments/terms/meta/relations and null sentinel behavior (L).
- [ ] U-004 UUID integrity and cache-key test corpus (M).
- [ ] U-005 patchset tooling: patch series, hash manifest, rebase workflow (M).
- [ ] I-008 clean install, admin bootstrap, verification CLI (L).
- [ ] I-012 `wps verify` runtime and identity integrity checks (M).

**Exit:** passing WP core CRUD, login, basic editor and REST flows; all supported core PKs UUIDv7; no silent conversion.

## M3 — Compatibility SQL engine and Redis beta

- [ ] Q-001 parser/AST integration and query source attribution (L).
- [ ] Q-002 transform approved core MySQL SQL patterns (L).
- [ ] Q-003 `dbDelta` / schema manager compatibility plan (L).
- [ ] Q-004 semantic differential SQL corpus MySQL vs PG (L).
- [ ] C-001 vetted object-cache integration and namespace isolation (M).
- [ ] C-002 Redis failure, invalidation and concurrency tests (M).
- [ ] S-001 enforce migrator vs runtime role separation (M).
- [ ] S-002 TLS `verify-full` for PostgreSQL and cache (M).
- [ ] S-003 secret references and log redaction (M).
- [ ] S-004 immutable release layout and hardened wp-config defaults (M).

**Exit:** no unsupported unclassified SQL in pinned core test suite; Redis fallback safe; security negative tests pass.

## M4 — Plugin install and migration beta

- [ ] P-001 plugin static scanner and evidence reports (L).
- [ ] P-002 adapter manifest schema, registry, hash signing (M).
- [ ] P-003 isolated plugin activation and migration test harness (L).
- [ ] P-004 `wps plugin scan/check/install/activate` gated flow (L).
- [ ] P-005 native PG plugin schema diff engine and review plan (L).
- [ ] X-001 selected **two** low-complexity plugins end-to-end, then expand (L).
- [ ] X-002 controlled MySQL import pilot with IDs crosswalk for **core-only** content (L).
- [ ] X-003 plugin payload migration only by typed adapters; unknowns blocked (L).
- [ ] P-006 public compatibility list generated from CI plugin runs (M).
- [ ] M-001 `wps migrate plan/apply/verify` CLI (L).
- [ ] B-001 `wps backup` / `restore` / `restore-test` (L).

**Exit:** two named plugins pass defined functionality/upgrade/uninstall tests; unsupported plugins blocked; core-only migration reconciles.

## M5 — Operational RC / 1.0 candidate

- [ ] O-001 release upgrade and rollback/restore rehearsals (L).
- [ ] O-002 backup & media consistency, RPO/RTO runbooks (M).
- [ ] O-003 fuzz, security, fault injection, perf and load tests (L).
- [ ] O-004 publish compatibility matrix with pinned versions (M).
- [ ] O-005 reproducible builds, SBOM and artifact provenance (M).
- [ ] O-006 document incident response, support policy, CVE process (M).
- [ ] O-007 production deployment guide and migration disclaimers (M).
- [ ] O-008 `wps support bundle --redact` (M).

**Exit:** release checklist signed by maintainers, successful fresh install + staging upgrade + recovery drill; no high/critical known data-loss issues.

## Dependencies / critical path

M0 ID audit -> core patch strategy -> M2 UUID core correctness -> M3 SQL semantics -> M4 plugin compatibility -> M5 stable release. Installer skeleton, DDEV and security scaffolding can begin in parallel after M0. Do **not** build admin redesign until core correctness is stable.

## Deliverable tracking

Tracked on the [Pressgres Roadmap project](https://github.com/orgs/pressgres/projects/1): each milestone section maps to one or more Epics, each task ID to a Story sub-issue; dependencies use GitHub "blocked by" links.

Every task: GitHub issue with owner, phase, dependencies, acceptance tests, security impact, PR, ADR link when relevant and evidence artifact. Milestone status is determined from CI and review evidence, not percentage of boxes checked.
