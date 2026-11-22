# 13 — Post-1.0 feature horizon (not committed scope)

Rank by user research and architecture compatibility. Each requires a separate PRD, threat model, integration tests and explicit maintenance budget.

## Auth modernization

- Passkeys/WebAuthn with account recovery, phishing resistance and deployment origin/RP ID management.
- MFA with TOTP or security keys; recovery codes protected and audited.
- SSO via OIDC/SAML, identity mapping to UUID users, JIT provisioning and role boundaries.
- Session device inventory, audit events, secure token rotation and rate limiting.
- Default to interoperable, vetted integrations before building bespoke auth; avoid replacing WordPress capability model wholesale.

## Admin experience

- Accessible admin information architecture, responsive layout, plugin compatibility/recovery dashboard, clearer capability roles, migration visibility.
- A modern design system but keep WordPress accessibility and extensibility hooks; do not break plugin admin screens.
- Optional headless dashboard, API-first design and staged rollout toggles.

## Content management

- Typed content schemas and validation, editorial workflow, revision diff, scheduled approvals, audit history and content portability.
- Content query API, entity reference fields with UUID semantics, safe structured metadata, asset pipeline and storage adapters.
- Optional search integration (e.g. OpenSearch/Meilisearch) after relevance and sync requirements established.

## Platform

- Multi-tenancy/multisite research (separate schemas or isolated DBs; cache isolation proof required).
- External object storage, queue/async jobs, stronger cron scheduling, observability dashboard.
- Alternate database drivers only after PG implementation stabilized.
- Migration tooling for selected popular plugins, curated compatibility registry and signed adapter store.

## Prioritization rubric

Evaluate adoption demand, security gain, compatibility risk, burden on upstream merges, implementation effort and recurring maintenance. No future idea should compromise core data correctness or release discipline.
