# 11 — Competitive analysis, benefits, drawbacks, risks

## Alternatives considered

| Approach | Benefits | Drawbacks | When to choose |
|---|---|---|---|
| Stock WordPress + MySQL/MariaDB | Highest plugin support, lowest maintenance, mature ecosystem | no PG standardization, bigint IDs | default for most commercial WordPress sites |
| PG4WP-style `db.php` | Reuses normal WP core, simpler entry point | plugin SQL and native UUID core issues remain | PostgreSQL experiment without UUID-only mandate |
| SQLite Database Integration | Officially incubated SQL parser/emulation approach, light deploy | SQLite is not PG; different scale/ops tradeoffs | small/self-contained sites |
| Fork WP to native PG | Full control of core behavior | permanent fork/upgrade cost; ecosystem split | specialist platform with committed maintainers |
| **Pressgres managed patchset** | version-pinned UUID-only + PG + verified plugin pipeline | high complexity, narrow plugin coverage, release lag | teams needing strict PG and UUID-first governance |
| Headless CMS/framework built for PG | native PG/UUID with modern APIs, cleaner domain model | lose WordPress plugin/editor familiarity | greenfield site without WP dependence |

## Where this idea is better

- One operational SQL platform across apps already standardized on PostgreSQL.
- Native UUIDv7 IDs are genuinely typed in storage and API, avoiding `bigint` identity coupling where supported.
- Compatibility decisions are surfaced **before** plugin installation rather than discovered as production errors.
- Version-pinned installation, audits and recoverability improve reproducibility for regulated teams.
- Domain-aware SQL adapters allow gradual coverage improvements and a useful public plugin compatibility registry.

## Where it is not better

- For users wanting typical WordPress and a large plugin marketplace, stock WordPress + MariaDB is substantially lower-risk and easier to host.
- Native UUID may cost more than it yields if no cross-system ID requirements exist; `bigint` is compact and efficient.
- Patching WordPress core adds a permanent merge/release burden and potentially breaks upstream tooling and editor APIs.
- Universal SQL conversion is impossible for arbitrary plugin PHP logic, schema design and external integrations.
- PostgreSQL is not automatically faster, safer or cheaper; architecture, permission model and operations dominate.
- Building a new CMS on PG may be cheaper than adapting every assumption in WordPress at scale.

## Risk register

| ID | Risk | Severity | Mitigation / decision gate |
|---|---|---|---|
| R1 | core ID truncation and REST incompatibility | critical | UUID audit and full E2E before M2 |
| R2 | plugin integer-ID assumptions | critical | deny by default, reviewed adapters |
| R3 | incorrect SQL semantic conversion | critical | AST + differential tests, fail closed |
| R4 | unpredictable core upgrade rebase | high | patchset manifest + pinned versions |
| R5 | corrupt serialized/opaque plugin data | critical | typed mappers, migration blockers |
| R6 | unsafe plugin activation/execution | critical | isolated sandbox + artifact approval |
| R7 | reliance on `db.php` conflicts | medium | detect existing drop-in and refuse overwrite |
| R8 | Redis cache cross-site leakage | high | key namespace/tenant isolation tests |
| R9 | lack of maintainer bandwidth | high | explicit support tiers and narrow plugin list |
| R10 | project name/trademark collision | medium | clearance and rename before public launch |
| R11 | GPL/code redistribution/licensing | high | legal review and provenance manifest |
| R12 | false promise of atomic rollback | high | backups, snapshots, recovery rehearsal |

## Go/no-go at M0

Proceed only if team accepts a managed core patchset, limited plugin catalog, explicit failure modes and meaningful ongoing release maintenance. If the business goal is simply "run common WordPress plugins reliably", choose MySQL/MariaDB instead; if the goal is only UUIDs at integration boundaries, dual IDs are materially cheaper.
