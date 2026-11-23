# 09 — Code standards, repository rules and Git workflow

## Language and style

- PHP 8.4 features allowed in Pressgres code; WordPress patched source retains necessary core style with minimal localized patchset. Do not impose new coding style across upstream WordPress files unnecessarily.
- New Pressgres code: PSR-12 formatting, PSR-4 autoloading, `declare(strict_types=1)` in new PHP modules, descriptive names, readonly immutable DTOs when practical, exceptions with stable error codes.
- Maintain WordPress-facing APIs and hooks using WordPress naming/behavior where compatibility requires it.
- PHPStan at maximum level without a baseline, PHPUnit 12, PHPCS with PSR-12, Composer audit and dependency checks. Composer locks the tool versions.
- SQL: versioned, checksummed migrations; explicit schema, quoted legacy identifiers where required; bind values, whitelist identifiers, never format values into SQL.
- JS/TS for admin tooling: TypeScript strict mode, ESLint/Prettier pinned, accessible UI and E2E tests.
- YAML/JSON: schema validated, deterministic key ordering for generated manifests; never check in secrets.
- Tests: meaningful failure-path coverage, regression fixtures for every SQL adapter bug, independent test DB, no tests against real operator production databases.

## Local PHP checks

Run from the repository root with PHP 8.4 and Composer 2.10.3.

```bash
composer validate --strict
composer validate --strict packages/contracts/composer.json
composer validate --strict apps/installer-cli/composer.json
composer install --no-interaction --prefer-dist --no-progress
composer check-platform-reqs
composer audit
composer cs
composer analyse
composer test
```

The PHP workflow runs the same checks. The contracts and installer CLI unit suites run without a database or WordPress installation.

## Coding guardrails

1. Never cast UUIDs to `int`; validate v7 at relevant entity boundaries.
2. No generic regex-based SQL rewrite accepted for production; parse AST and test semantics.
3. Never silently discard a SQL column/value or fall back to integer PK.
4. No DDL by web runtime; use explicit migration role and plan.
5. `wpdb` return types/field casing/affected-row behavior must be covered by compatibility tests.
6. Avoid runtime patching of third-party plugin files; use manifest adapters and controlled deployments.
7. Handle output escaping, input validation, nonces, roles/capabilities and CSRF on every admin endpoint.
8. Redact credentials, auth tokens, session IDs and PII from errors/telemetry.
9. Document any behavior divergence from WordPress and add an ADR for cross-module decisions.
10. Every feature includes docs, tests, safe failure, release compatibility impact.

## GitHub flow (recommended over Git Flow branching complexity)

- Protected `main`, short-lived branches `feat/<issue>-...`, `fix/<issue>-...`, `docs/...`, `research/...`, `security/...`.
- Small PRs, one functional concern each, linked issue, acceptance checklist, tests, ADR if behavior changes, migration risk, screenshots only for UI.
- Required status checks: lint/static analysis, unit, PG integration, UUID regression, Docker/DDEV smoke, security scan, license check; owner review for patches/migrations/security.
- Squash merge to `main`; SemVer tagged releases; optional `release/x.y` stabilization branches only when needed, cherry-pick urgent fixes.
- `CODEOWNERS`: database, identity, security, patchset and adapters require domain owners; two-person review for destructive migrations or auth/secret changes.

## Conventional Commits

`type(scope)!: summary` where `type` is `feat|fix|docs|refactor|test|build|ci|perf|security|chore`; `!` indicates breaking contract. Examples:

```text
feat(installer): add PostgreSQL UUIDv7 preflight
fix(identity): preserve UUID strings in post REST route
security(db): remove DDL grants from runtime role
feat(schema)!: replace legacy numeric post references with UUIDs
```

Breaking changes require `BREAKING CHANGE:` footer and migration notes. Use generated changelog and release notes from commits + manual security review. Signed commits/tags recommended for maintainer roles.

## Semantic versioning and compatibility

`0.x` for changing internals; `1.0` after published stable contracts. Distinguish Pressgres version, WordPress release, core patchset hash, schema version and individual adapter versions in a machine-readable lockfile. Plugin compatibility verdict applies **only** to stated tested versions.
