# Architecture decision records

One file per decision: `NNNN-short-title.md`, copied from [0000-template.md](0000-template.md). Numbering follows the canonical list in [14 — Open decisions](../14-open-decisions.md#pending-adrs-and-default-recommendation).

| ADR | Title | Status | Evidence |
|---|---|---|---|
| [0001](0001-wordpress-change-strategy.md) | WordPress change strategy (managed patchset) | Proposed | R-005 #7 |
| [0002](0002-native-uuidv7-policy.md) | Native UUIDv7 policy (UUID-only) | Proposed | R-011 #12 |
| [0003](0003-sql-parser.md) | SQL parser | Proposed | R-004 #6 |
| [0004](0004-plugin-support-model.md) | Plugin support model | Proposed | R-006 #8, R-014 #15 |
| [0005](0005-local-development.md) | Local development | Proposed | — |
| [0006](0006-version-policy.md) | Version policy (one series, best-effort security) | Proposed | R-009 #9, R-013 #10 |
| [0007](0007-project-brand-and-licensing.md) | Project brand and licensing | Proposed | R-015 #16 |
| [0008](0008-foreign-keys.md) | Foreign key enforcement | Proposed | R-002 #4 |
| [0009](0009-legacy-migration.md) | Legacy migration scope | Proposed | — |
| [0010](0010-object-cache-backend.md) | Object cache backend (Valkey default) | Proposed | R-010 #14 |
| [0011](0011-ddl-staging-model.md) | DDL staging model | Proposed | R-006 #8 |

All ADRs are drafted for a solo maintainer (see ADR-0006). Acceptance and the M0 go/no-go are tracked in R-007 (#18).

Status values: Proposed, Accepted, Superseded by ADR-NNN, Rejected. ADRs touching identity, schema, security or the core patchset need CODEOWNER review.
