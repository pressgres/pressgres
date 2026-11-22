# 14 — Missing topics, questions and decision log

## Items likely overlooked

1. **Licensing/trademarks:** GPL obligations when distributing patched WordPress, adapters, and upstream parser code; assess names/trademarks and domain availability professionally.
2. **Support model:** which exact plugin versions are promised, how long supported WordPress versions receive updates, how vulnerabilities are reported and fixed.
3. **Data governance:** PII logs, EU/GDPR deployment, data retention, backup restoration deletion obligations, privacy exports/erase APIs.
4. **Operational ownership:** who can run migrations, rotate credentials, respond to incidents and approve unsupported plugins.
5. **Upgrade lifecycle:** patching WordPress core is a recurring engineering commitment, even for minor/security releases.
6. **Reference behavior:** timezone handling, collation, case sensitivity, string coercion, `LIKE` semantics, full-text search and index types differ from MySQL.
7. **External integrations:** WooCommerce/payment systems, analytics, webhooks and imports may assume numeric IDs; explicitly exclude until tested.
8. **Backups/media consistency:** site database restore alone may omit uploads and external object storage.
9. **Multisite:** distinct users/table prefixes, network tables, caching and tenancy boundaries; not v1.
10. **Plugin trust:** sandboxing is not guaranteed by merely using Docker; runtime network/FS limits matter.
11. **Performance:** UUIDv7 improves insertion locality relative to random UUIDs but does not make queries faster automatically; test indexes and metadata workloads.
12. **UX:** explain why a plugin is blocked, provide remediation and show certainty/evidence, not opaque "compatibility score".
13. **Installer governance:** privilege escalation, installer expiration, recovery of partial steps and correct idempotency.
14. **WordPress CLI/updater integration:** decide exactly which administrative entry points are allowed and intercepted.
15. **Accessibility/i18n:** admin UI, CLI translations and errors should be comprehensible; test accessibility.
16. **Supply chain & reproducibility:** artifact signatures, lockfiles, SBOM, provenance and dependency patch cadence.
17. **Performance baseline:** establish reference MySQL WordPress benchmark and parity targets before using performance claims in marketing.

## Pending ADRs and default recommendation

| ADR | Decision | Recommended provisional answer |
|---|---|---|
| 001 | WordPress change strategy | managed version-specific patchset, not unbounded fork |
| 002 | Native UUID-v7 policy | hard requirement; nullable refs; zero never parsed as UUID; written rationale (why not dual IDs) required |
| 003 | SQL parser | reuse WordPress SQLite Database Integration MySQL parser/AST with a PostgreSQL emitter unless the R-004 spike rules it out |
| 004 | Plugin support | reviewed, signed manifests and disposable activation tests |
| 005 | Local dev | DDEV + Compose, no forced Docker production runtime |
| 006 | Version policy | WP 7.1, PHP 8.4, PG 18 first; CI-gated expansions |
| 007 | Project brand | Pressgres working name, legal clearance pending |
| 008 | Foreign keys | gradual enforcement after compatibility tests |
| 009 | Legacy migration | restricted, core-only pilot, explicit source ID crosswalk |
| 010 | Object cache backend | vetted drop-in instead of custom caching engine; Redis vs Valkey licensing decided here |
| 011 | DDL staging model | schema planner + migrator role only; web runtime never executes DDL |

## Questions to resolve before M1

- Is managed WordPress with patchset acceptable legally, operationally and strategically?
- Who is the first user persona: agency, host, enterprise platform, or individual developer?
- Which two plugins are the initial compatibility targets?
- Is a fresh WordPress site sufficient for initial release, or must MySQL import ship at 1.0?
- What is the production deployment environment and who controls DB TLS and secrets?
- Which GPL/license strategy and maintenance funding model will sustain WordPress updates?
