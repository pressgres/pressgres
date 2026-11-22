# 10 — AI skills and agent operating rules

## Purpose

Allow AI coding agents to contribute in bounded, auditable changes without giving them authority to bypass security, approve unsupported plugin behavior or run destructive operations on live sites.

## Mandatory agent skills / knowledge areas

| Skill | Required competence | Test of competence |
|---|---|---|
| WordPress internals | `$wpdb`, drop-ins, hooks, core install/update, REST schemas | trace post create/retrieve ID end-to-end |
| PostgreSQL | SQL dialect, catalogs, locks, PG DDL, UUID functions, roles | design safe migration with `uuidv7()` |
| PHP 8.4 | strict types, PDO, Composer, error handling | implement tested typed module |
| SQL parsing | AST rewriting, binds, semantics, collations | build differential test corpus |
| Database migration | FK crosswalk, backups, restore, checksum, idempotence | dry-run + restore verified |
| Security | threat modeling, credentials, sandbox and least privilege | adversarial fixture rejects unsafe plugin |
| Redis | object-cache semantics, key namespaces, invalidation | fault injection on cache outage |
| DevOps | Docker, DDEV, GitHub Actions, SBOM and signed releases | green reproducible CI job |
| Testing | PHPUnit, WP integration, E2E, fixtures, fuzz | regression test for bug |
| Documentation | ADR, changelog, release notes | explain assumptions and version impact |

## Role specialization

- **Architect agent**: ADR drafts, interface decisions, dependency maps; no production changes.
- **Core compatibility agent**: analyzes and patches one known WordPress release; requires snapshot tests and patch ownership review.
- **SQL engine agent**: grammar/AST/semantic adapters; emits negative tests for unsupported transformations.
- **Migration agent**: builds schema diffs and UUID crosswalks; operates only on disposable DBs unless authorized human operation.
- **Security reviewer agent**: reviews least privilege, secrets, CVEs, unsafe plugin PHP; can recommend block, cannot waive policy.
- **QA agent**: fixture generation, differential and E2E tests, CI triage; cannot mark untested paths supported.
- **Docs/release agent**: versioned docs, changelog, support matrix, SBOM provenance; human signs release.

## Mandatory AI workflow

1. Read `/AGENTS.md`, PRD relevant file(s), current ADRs, compatibility lockfile and touched module tests.
2. Create an issue-sized plan; state files and contracts affected and whether migration/UUID/security risk exists.
3. Write failing regression test before code for bug fixes where practical.
4. Implement minimal change; avoid touching WordPress core except isolated pinned patch files.
5. Execute lint, static analysis and targeted tests; report exact commands and outcomes. Do not claim checks ran if they did not.
6. Produce PR summary, risk, limitations, rollback path and compatibility matrix impact.
7. Request human review for data migrations, runtime privileges, plugin execution, core patch and release tags.

## Prohibited autonomous actions

- Never access production data or secrets, run destructive migrations, deploy to production, sign release or approve unknown plugin code without explicit human authorization.
- Never mark an inferred transformation as verified. No imaginary screenshots, test results, vulnerabilities or benchmark numbers.
- Never change UUID primary IDs to numeric, weaken TLS, widen DB privileges, disable safety checks or hide failing tests to reach green CI.
- Never copy GPL/plugin code into incompatible licenses without legal review; record code origin and license.
- Never edit `wp-content` deployed files when source-controlled release artifacts are expected.

## Prompts / task contracts

**SQL agent task template:** "For WordPress release X, plugin Y version Z, analyze SQL class Q; provide parsed AST conversion, PG SQL, parameter mapping, differences in behavior, negative cases, PHPUnit/integration tests and explicit unsupported cases. Do not perform schema writes."

**Migration agent task template:** "Given fixture source schema A and target schema B, generate a read-only migration plan, ID mapping table, dependency order, checksums, validation SQL, forward migration and verified recovery design. Do not modify target database."

**Code reviewer prompt:** "Review UUID-string correctness, SQL bind safety, role permissions, plugin side effects, field naming, security logging, version pinning, test gaps and rollback claims. Mark blockers clearly."

## Definition of done for AI-produced PR

Code + tests + docs + reproducible commands + risk list + new/updated ADR where needed + reviewer approval. `AGENTS.md` in root is canonical and can be copied into a future code repository.
