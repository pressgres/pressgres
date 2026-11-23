# Architecture decision records

One file per decision: `NNNN-short-title.md`, copied from [0000-template.md](0000-template.md). Numbering follows the canonical list in [14 — Open decisions](../14-open-decisions.md#pending-adrs-and-default-recommendation).

| ADR | Title | Status | Evidence |
|---|---|---|---|
| [0001](0001-wordpress-change-strategy.md) | WordPress change strategy (managed patchset) | Accepted | R-005 #7 |
| [0002](0002-native-uuidv7-policy.md) | Native UUIDv7 policy (UUID-only) | Accepted | R-011 #12 |
| [0003](0003-sql-parser.md) | SQL parser | Accepted | R-004 #6 |
| [0004](0004-plugin-support-model.md) | Plugin support model | Accepted | R-006 #8, R-014 #15 |
| [0005](0005-local-development.md) | Local development | Accepted | — |
| [0006](0006-version-policy.md) | Version policy (one series, best-effort security) | Accepted | R-009 #9, R-013 #10 |
| [0007](0007-project-brand-and-licensing.md) | Project brand and licensing | Accepted | R-015 #16 |
| [0008](0008-foreign-keys.md) | Foreign key enforcement | Accepted | R-002 #4 |
| [0009](0009-legacy-migration.md) | Legacy migration scope | Accepted | — |
| [0010](0010-object-cache-backend.md) | Object cache backend (Valkey default) | Accepted | R-010 #14 |
| [0011](0011-ddl-staging-model.md) | DDL staging model | Accepted | R-006 #8 |
| [0012](0012-cli-result-envelope.md) | Versioned CLI result envelope | Proposed | I-009 #21 |

M0 ADRs 0001–0011 were accepted by the project lead on 2026-11-23 and are written for a solo maintainer (see ADR-0006). ADR-0007's name remains a working name until trademark clearance (R-015, #16). The M0 go/no-go outcome is in [R-007](../research/R-007-m0-go-no-go.md).

Status values: Proposed, Accepted, Superseded by ADR-NNN, Rejected. ADRs touching identity, schema, security or the core patchset need CODEOWNER review.
