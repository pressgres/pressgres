# ADR-0006: Version policy (WordPress 7.1, PHP 8.4, PostgreSQL 18; one supported series; best-effort security updates)

- **Status:** Proposed
- **Date:** 2026-11-23
- **Deciders:** Project lead (solo maintainer)
- **Related issues:** pressgres/pressgres#9 (R-009), pressgres/pressgres#7 (R-005); R-013, R-007 (go/no-go), I-010 (CI); ADR-001, ADR-005

## Context

Pressgres ships a patched WordPress (ADR-001), so every supported upstream release is recurring engineering work. [07 — Compatibility](../07-compatibility.md) separates "upstream WordPress runs on X" from "Pressgres has tested its patchset on X". Only the second counts. The project has one maintainer, with AI agents and CI doing most of the work.

Evidence:

- **Pinned baseline used by every spike:** wordpress-develop **7.1.5** (`984163c92ef66b6186538ecf01bacb97fc097541`, DB revision 61833) with Gutenberg **`89408c2`** (`89408c2b9bd944575dfa9039bc6870da1c8f56cb`), PHP **8.4.27** and PostgreSQL **18.6** ([R-013](../research/R-013-patchset-size-and-rebase-cost.md), [R-006](../research/R-006-threat-model-and-sandbox.md), [R-009](../research/R-009-core-phpunit-baseline.md)). PostgreSQL 18 is the floor because it has native `uuidv7()`, which ADR-002 relies on.
- **Cost of one series ([R-013](../research/R-013-patchset-size-and-rebase-cost.md#engineer-time-and-r9)):** expected patch of 1,925 existing lines across 284 files. Per release: 5 / 11 / 20 engineer-days for a feature release and 1 / 2 / 4.5 for a security release (low / expected / high). Annual: **59 engineer-days, or about 74 with a 25% reserve (about 0.34 FTE)**, for **one** series. Confidence in the hours is low until rehearsed. Additional series need separate budgets.
- R-013's go/no-go input says to proceed with a managed pilot if three cross-trained maintainers are available. **"If the team can provide only one maintainer or cannot demonstrate the gated security path, defer production support."** That condition describes the project today.
- **ADR-001** (from [R-005 §1.4](../research/R-005-patch-mechanism-and-licensing.md#14-security-releases-and-a-proposed-sla-compatible-workflow)) proposed security targets of **24 h** (patches clean or refreshed) and **72 h** (conflict). It explicitly left the final numbers to this ADR. R-005 noted those targets assume maintainers in several time zones. Upstream security fixes land on release day, and the 6.9.2 cycle needed a follow-up release about 8 hours later.
- **[R-009](../research/R-009-core-phpunit-baseline.md):** the upstream core PHPUnit suite runs on MySQL 8.4.13 at 30,868 / 30,900 passing (99.90%). On PostgreSQL the R-003 prototype scores **0%** as delivered (the bootstrap aborts on DDL), 2.07% with a harness wrapper, and **77.47% comparable** once one state-leaking class is excluded (66.4% excluding DB-agnostic directories). R-009 recommends **gating on a ratchet, not a percentage**: a committed expected-pass list where any regression fails CI.

## Decision

**First target: WordPress 7.1 (7.1.5 with Gutenberg `89408c2` as the baseline), PHP 8.4 and PostgreSQL 18, on Linux. Pressgres supports exactly one WordPress release series at a time. Security updates are best effort, with targets but no guaranteed SLA.**

1. **Initial matrix.** WordPress 7.1.x (exact patch release pinned per Pressgres release), PHP 8.4.x, PostgreSQL 18.x, Linux x86_64. Each Pressgres release manifest pins the exact wordpress-develop tag, Gutenberg SHA, patchset hashes, PHP and PostgreSQL versions it was tested with ([07](../07-compatibility.md#exact-version-strategy)). The installer refuses anything else. PostgreSQL 17 and older are rejected because they lack native `uuidv7()`. The object cache server version follows ADR-010.
2. **One series.** When upstream ships a new WordPress feature release (e.g. 7.2), it is `experimental` until its patchset passes all gates. Once a Pressgres release based on it ships, the previous series gets **no further updates**, and users must move forward. No parallel maintenance of older series.
3. **Expansion through CI gates only.** PHP 8.5, PostgreSQL 19 and Linux arm64 become supported only when the full gate set below passes on them. Until then they are listed as candidates. Nothing is added because upstream supports it.
4. **Release gates.** Every Pressgres release requires:
   - strict patch application and reproduced patched-tree digest (ADR-001);
   - the UUID regression suite and disposable PostgreSQL fixtures;
   - the **core PHPUnit ratchet** from R-009: a committed expected-pass list, where any test that stops passing fails the release. Additional failure conditions: the bootstrap does not reach PHPUnit, or the JUnit test count drops by more than 1%. The comparable pass rate against a MySQL control is published per release as a trend, not as a pass/fail threshold.
5. **Security updates: targets, not commitments.** This supersedes the 24 h / 72 h figures in ADR-001 §7.
   - Detection is automated: CI runs `rebase-check` on every upstream tag within about an hour and notifies the maintainer.
   - Target: a patched release within **72 h** when every patch is clean or refreshed, and **7 days** on conflict, using the ADR-001 hotfix path where it helps. These are **targets**. With one maintainer they can be missed (illness, travel, overlapping releases), and the project says so publicly.
   - When a target is missed, the security advisory says so and tells operators the risk and the options (e.g. take the site offline, apply mitigations, wait).
   - Regular point releases: target 14 days. Feature releases: experimental until gated, no target.
6. **Support statement.** Until the go/no-go conditions in the open items are met, Pressgres releases are labeled **preview / not for production**, consistent with R-013's recommendation and AGENTS rule 4. The support policy page states: one maintainer, one series, best effort, no SLA, no warranty (GPL).

## Consequences

- **Positive:** the commitment fits roughly 74 engineer-days a year for a single series, with automation covering detection, classification and gating. A narrow matrix keeps CI cost and claims honest. The ratchet catches regressions that a percentage threshold would hide (R-009's PG-B case, where one leaked global turned 21,413 tests red).
- **Negative:** operators get no guaranteed security response, which rules out many production users until the project has more maintainers or funding. Forcing upgrades with no older-series maintenance is strict. A feature release can leave users on an unpatched old series until the new one passes gates (about 11 engineer-days of work expected per R-013).
- **Neutral:** the compatibility matrix has one supported row per (wordpress-develop tag, Gutenberg SHA, PHP minor, PostgreSQL major, arch). Everything else is `experimental` or rejected.
- **Migration impact:** moving to a new series means a Pressgres upgrade with the matching schema migrations (ADR-011). Downgrades are not supported.

## Alternatives considered

- **Keep ADR-001's 24 h / 72 h as an SLA:** needs on-call cover in several time zones. R-013 ties any SLA to three maintainers and two rehearsals. Rejected for a solo project. Kept as aspirational figures for a future team.
- **Support two series (current plus previous):** roughly doubles recurring cost beyond the 74-day estimate for one series. Rejected.
- **Track WordPress trunk or nightly:** churn is too high for a patchset. R-013 found feature releases change 135–167 of the 240 named files. Rejected.
- **Broader initial matrix (PHP 8.3 or 8.5, PostgreSQL 17):** PostgreSQL 17 lacks native `uuidv7()`. Additional PHP minors multiply CI without user evidence. Rejected for now. 8.5 is a CI candidate.
- **Percentage pass-rate threshold as the gate:** hides regressions traded for fixes (R-009). Rejected in favor of the ratchet.

## Open items / revisit triggers

- **Go/no-go for production labeling (R-007):** rehearse one feature transition (7.0.4 → 7.1.0) and one security transition (7.1.4 → 7.1.5) end to end and record real elapsed time, as R-013 recommends. Add a backup maintainer or external reviewer, or keep the preview label.
- **Measured rebase cost:** R-013's hours are modeled, not measured. Update the targets in section 5 after the rehearsals.
- **Core auto-update blocking:** stopping WordPress's own updater from replacing patched core is unverified (R-005 open question 9; [14](../14-open-decisions.md) item 14).
- **Official pass-rate definition:** whether the ratchet runs with a patched `tests/phpunit/includes/` or a harness-only wrapper (R-009 open question).
- **Revisit** when a second maintainer or funding arrives (consider an SLA and a second series), or if a single upstream year exceeds the high estimate (148 days with reserve).
