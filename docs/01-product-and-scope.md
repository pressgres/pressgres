# 01 — Product requirements and scope

## Problem statement

WordPress assumes MySQL/MariaDB across core queries, schema installation, upgrades and its third-party plugin ecosystem. Teams wishing to standardize on PostgreSQL cannot reliably deploy stock WordPress without translation layers and manually maintained compatibility fixes. WordPress IDs are numeric across public and internal APIs, making wholesale native UUIDv7 replacement a core-runtime modernization, not a database configuration switch.

## Vision

A repeatable installer and managed compatibility runtime so organizations can run a **documented subset of WordPress and plugins** on PostgreSQL 18+ with native UUIDv7 entity identifiers, Redis object caching and hardened security, while exposing compatibility limits before data is touched.

## Users / JTBD

- Platform engineer: install, upgrade, observe and recover the stack deterministically.
- WordPress developer: develop UUID-aware plugins, test legacy plugin adapters and debug SQL translations.
- Site operator: understand whether a plugin is supported, why activation is blocked and how to resolve it.
- Security reviewer: inspect privileges, verified artifacts, change provenance and backup/restore evidence.

## Principles (priority order)

1. No silent data corruption; fail closed on unknown schema/SQL semantics.
2. Native UUIDv7 is a hard constraint for managed runtime; never covertly reintroduce numeric PKs.
3. Stock WordPress interoperability is a **long-term goal**, not an initial promise; version-pinned core patchset is allowed and mandatory.
4. Every capability is explicitly tested, versioned and reversible when possible.
5. Installation is declarative, noninteractive, resumable and auditable.
6. Least privilege, encrypted transport, secure defaults and secrets externalized.
7. Make local development close to CI and production, without equating local Docker defaults to production security.

## In scope (MVP -> 1.0)

- `wps init`, `doctor`, `plan install`, `install`, `verify`, `plugin scan/check/plan/install/activate`, `migrate plan/apply/verify`, `upgrade plan/apply`, `rollback`, `backup`/`restore`/`restore-test` (phased; see [CLI table](03-installer-cli.md)).
- Managed WordPress release with UUID-string-safe core API/REST contracts.
- PDO PostgreSQL database drop-in with parser-based MySQL compatibility for vetted statements.
- Versioned native PostgreSQL schema and migration registry; schema drift detection.
- Redis object cache drop-in integration and isolation.
- Plugin install/activation gating, manifest registry, sandbox dry-run, approved adapters.
- DDEV and Docker Compose dev environments; container production reference deployment, not mandatory Docker runtime.
- Release compatibility matrix, CI and support policy.

## Explicitly out of scope for 1.0

- Guaranteed support for all WordPress plugins/themes or unsupported WordPress upgrades.
- Seamless MySQL-to-PostgreSQL migration for arbitrary production sites; start with limited/validated source profiles.
- Automatically rewriting arbitrary plugin PHP or enabling unreviewed generated patches.
- Native multisite, cross-database joins, SQLite and alternate SQL engines.
- New admin UI, passkeys, SSO, 2FA product suite, headless CMS overhaul.
- Claiming that UUIDs by themselves deliver authorization or privacy.

## Success metrics / release gates

- Upstream WordPress core PHPUnit suite pass rate on the pinned stack is published per build and does not regress (primary objective compatibility metric).
- 100% of supported core identity-bearing tables have UUID PK/FK contracts and referential tests.
- 100% of targeted core CRUD/REST/editor flows in the published test suite pass on pinned stack.
- 0 known silent coercions of UUIDs to integers in supported paths.
- 100% of plugin installs trigger scan+approval gate; unsupported modifications blocked.
- Reproducible clean install and restore on supported Linux architecture with independently verified backups.
- CI passes unit, integration, end-to-end, migration-replay, rollback, vulnerability and fault-injection suites.
- Explicit supported plugin list and migration limitations published before 1.0.

## Non-functional targets (initial SLO proposals, subject to measurement)

- Zero loss of acknowledged committed writes in normal operation; durability inherits PostgreSQL storage/backup design.
- Installer resumes idempotently after process interruption; schema steps tracked with checksums.
- Query translation cache with bounded memory; budget and latency benchmarked before setting numerical SLOs.
- Diagnostic output must redact secrets and personal data.
- No dependency on running an internet-hosted installer endpoint.

## Decisions to record as ADRs

The canonical ADR list and numbering live in [14 — Open decisions](14-open-decisions.md#pending-adrs-and-default-recommendation); ADR files go in `docs/adr/`.
