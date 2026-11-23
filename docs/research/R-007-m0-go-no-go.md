# R-007: M0 go/no-go decision

- **Decision:** **GO, as a solo preview pilot.** Production support is **NO-GO** until the conditions below are met.
- **Date:** 2026-11-23
- **Decider:** Project lead (solo maintainer)
- **Related issues:** pressgres/pressgres#18 (R-007), pressgres/pressgres#11 (E02), pressgres/pressgres#1 (E01)

## Question

The [roadmap](../08-roadmap.md#m0--feasibility-and-adr-sign-off-research) sets the M0 exit as: demonstrable UUID insert/get across PHP and REST without truncation, and documented patch scope. It sets a **hard stop** if no viable managed patchset strategy is found. This memo records whether Pressgres continues past M0, and on what terms.

## Exit criteria

| Criterion | Result | Evidence |
|---|---|---|
| UUID insert/get across PHP and REST without truncation | **Met** | [R-003](R-003-uuid-prototype.md): PostgreSQL 18 `uuidv7()` IDs created and read back unchanged through PHP and REST with a 13-file patch. Without the patch, `wp_insert_user()` silently returns `1`. |
| Documented patch scope | **Met** | [R-001](R-001-php-integer-id-audit.md) (3,103 identity sites, about 1,350 lines), [R-012](R-012-editor-rest-id-audit.md) (editor and REST), [R-002](R-002-schema-and-sql-paths.md) (12 tables, 94 columns), [R-013](R-013-patchset-size-and-rebase-cost.md) (1,925 lines in 284 upstream files). |
| Viable managed patchset strategy (hard stop) | **Met** | [ADR-0001](../adr/0001-wordpress-change-strategy.md) and [R-005](R-005-patch-mechanism-and-licensing.md): hash-locked strict patch series with a working `tools/patchset/` demo that rejects tampered trees and classifies rebases. |
| ADR-001..011 recorded | **Met** | All eleven ADRs accepted on 2026-11-23 ([index](../adr/README.md)). |

## Why GO

- The technical core works: native UUIDv7 survives PHP, SQL and REST in a prototype ([R-003](R-003-uuid-prototype.md)).
- The SQL layer can reuse a maintained parser instead of writing one ([ADR-0003](../adr/0003-sql-parser.md), [R-004](R-004-sqlite-parser-evaluation.md): 435/437 inputs).
- Upstream WordPress tests give a measurable progress signal: 77.47 % comparable pass rate on the unfinished prototype, gated by a ratchet ([R-009](R-009-core-phpunit-baseline.md), [ADR-0006](../adr/0006-version-policy.md)).
- The security model has a working sandbox proof of concept ([R-006](R-006-threat-model-and-sandbox.md): 7/7 fixtures) and a no-DDL runtime ([ADR-0011](../adr/0011-ddl-staging-model.md)).

## Why not production yet

[R-013](R-013-patchset-size-and-rebase-cost.md) estimates **about 74 engineer-days a year** (35–148 range, with reserve) to keep **one** WordPress series patched, and its go/no-go input reads: "If the team can provide only one maintainer or cannot demonstrate the gated security path, defer production support." Pressgres has one maintainer, and the rebase cost has not been measured. Therefore:

- Releases are labelled **preview / not for production** ([ADR-0006](../adr/0006-version-policy.md) §6).
- Exactly one supported WordPress series. Security updates have targets (72 h clean, 7 days on conflict), not an SLA.
- AI agents and CI are the workforce: automated `rebase-check` on every upstream tag, strict patch apply, UUID regression suite and the PHPUnit ratchet run without human effort. A human reviews and merges.

## Conditions to lift the preview label

All must be true, with evidence linked in the release notes:

1. **Rebase rehearsals done.** One feature transition (7.0.4 → 7.1.0) and one security transition (7.1.4 → 7.1.5), executed end to end, with measured elapsed and engineer time (R-013 recommendation).
2. **Security path demonstrated.** The security rehearsal produces a signed, gated release within the ADR-0006 target (72 h clean or 7 days on conflict).
3. **Second person.** A backup maintainer or an independent reviewer for patchset and security changes is named.
4. **Ratchet green.** The core PHPUnit ratchet ([R-009](R-009-core-phpunit-baseline.md)) runs in CI on every PR, with no unexplained regressions for the release.
5. **Name cleared.** Trademark and registry checks for "Pressgres" are done ([ADR-0007](../adr/0007-project-brand-and-licensing.md), R-015 / pressgres/pressgres#16).
6. **User evidence.** User discovery (R-008 / pressgres/pressgres#13) has confirmed a first persona, and the two plugin targets (R-014 / pressgres/pressgres#15) are chosen.

## Stop and re-evaluate triggers

The project lead stops building and revisits this decision if any of these happen:

- A rebase rehearsal exceeds R-013's **high** estimate (20 engineer-days for a feature release, 4.5 for a security release).
- The ADR-0003 licensing check finds the parser grammar cannot be redistributed under the project licence, and no replacement is available.
- User discovery finds no organisation that would run a preview (zero of the 5–10 interviewed).
- Upstream WordPress changes make the single-series patchset grow well beyond the R-013 expected size (1,925 lines) in one release.

## What runs in parallel with M1

These do not block starting M1 (installer foundation):

- R-008 user discovery and R-014 plugin targets. R-014 must finish before M3 (plugin compatibility) work starts.
- R-015 trademark clearance. It must finish before any release that uses the name publicly as a product.
- The open items listed in each ADR (for example the parser grammar notices, the gVisor-versus-VM choice, and core auto-update blocking).

## Roadmap impact

- M0 is complete except R-008, R-014 and R-015, which continue in parallel.
- M1 starts now. CI work for the PHPUnit ratchet (I-010) and the rebase rehearsals move to the front, because they decide whether the preview label can ever be lifted.
