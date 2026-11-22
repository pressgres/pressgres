# Pressgres — WordPress + PostgreSQL compatibility platform

> **Working name, not trademark-cleared.** PRD package v0.1 · 2026-11-22 · **Status: proposal / not implemented**.

Pressgres is a managed WordPress runtime and installer targeting PostgreSQL, native UUIDv7 keys, Redis persistent object caching, secure defaults, and evidence-based plugin adaptation. It is **not** currently a drop-in-compatible substitute for stock WordPress; native UUID keys require a maintained core patchset.

## Read this PRD in order

1. [Product definition, goals, decisions](docs/01-product-and-scope.md)
2. [Architecture and runtime contracts](docs/02-architecture.md)
3. [Installer and CLI](docs/03-installer-cli.md)
4. [PostgreSQL, UUIDv7, examples](docs/04-data-model.md)
5. [Plugin compatibility and migrations](docs/05-plugin-compatibility.md)
6. [Security and operations](docs/06-security-operations.md)
7. [Version matrix and dependencies](docs/07-compatibility.md)
8. [Roadmap, epics, tasks and milestones](docs/08-roadmap.md)
9. [Quality, coding standards and Git](docs/09-engineering-standards.md)
10. [AI skills and autonomous-agent instructions](docs/10-ai-agents.md)
11. [Competitive case, risks and caveats](docs/11-tradeoffs-risks.md)
12. [Docker and DDEV](docs/12-local-development.md)
13. [Future product possibilities](docs/13-future.md)
14. [Open decisions and missing concerns](docs/14-open-decisions.md)
15. [Diagrams index](diagrams/README.md), [Glossary](docs/15-glossary.md), [Sources](docs/16-sources.md)
16. [Ten name candidates](docs/17-names.md)

## Proposed repository top level

```text
pressgres/
├── apps/installer-cli/         # wps CLI application
├── packages/{contracts,config,database,sql,identity,schema,compat,security,cache}/
├── wordpress/{db-dropin,object-cache-dropin,mu-plugins,admin-plugin}/
├── patches/wordpress/<version>/ # managed UUID core patches
├── adapters/<plugin>/<version>/ # signed/versioned compatibility manifests
├── migrations/{core,adapters}/
├── docker/                     # production-oriented build assets
├── .ddev/                      # developer experience, generated/validated
├── tests/{unit,integration,e2e,fixtures,regression}/
├── tools/                      # scripts, schema generation, verification
├── docs/ + diagrams/
├── AGENTS.md + CONTRIBUTING.md + SECURITY.md
└── .github/{workflows,ISSUE_TEMPLATE}/
```

**Naming:** Project working name *Pressgres*. CLI remains `wps` (WordPress Shell), separate from the public brand. Avoid assuming the name is legally or commercially available.

## Critical blockers before production claims

- WordPress core ID integer assumptions; UUID-only cannot be delivered as an ordinary `db.php` drop-in.
- Unknown plugin PHP logic cannot be made UUID-safe by SQL translation alone.
- Auto-translated migrations are not trusted until tested against disposable databases and reviewed.
- Compatibility claims must be pinned to tested WordPress + PHP + PostgreSQL + plugin versions.
- No code included in this archive is a deployable implementation; sample code and configuration are **illustrative contracts**.
