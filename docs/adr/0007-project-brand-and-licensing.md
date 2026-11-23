# ADR-0007: Project brand and licensing (Pressgres working name, GPL-2.0-or-later)

- **Status:** Proposed. **Blocker for Accepted:** trademark and registry clearance, R-015 / pressgres/pressgres#16.
- **Date:** 2026-11-23
- **Deciders:** Project lead (solo maintainer); legal review pending
- **Related issues:** pressgres/pressgres#16 (R-015), pressgres/pressgres#7 (R-005); ADR-001, ADR-003

## Context

Pressgres distributes a modified WordPress, WordPress drop-ins and plugins, and reuses GPL code (the MySQL parser, ADR-003). It needs a license compatible with all of that and a name that does not infringe the WordPress trademark.

Evidence:

- **License.** WordPress is GPLv2-or-later, and derivatives inherit the GPL ([R-005 §3.1](../research/R-005-patch-mechanism-and-licensing.md#3-gpl-and-redistribution-obligations-research-not-legal-advice), citing <https://wordpress.org/about/license/>). The repository [LICENSE](../../LICENSE) is already the GPL v2 text, and the [README](../../README.md#license) declares **GPL-2.0-or-later**. Both are merged. R-005 §3.2 lists the distribution obligations: intact notices, dated modification notices (§2(a)), and complete corresponding source including build scripts (§3). ADR-001 implements them.
- **GPL-2.0-only inputs.** [R-004](../research/R-004-sqlite-parser-evaluation.md#license-and-provenance) found Oracle GPL-2.0-only notices in the Workbench-derived grammar. The original notices for the standalone parser's MySQL Server inputs are unverified. A distribution that combines them is effectively under GPLv2 terms.
- **Trademark** ([R-005 §3.4](../research/R-005-patch-mechanism-and-licensing.md#34-trademark-constraints-on-naming-a-modified-distribution), WordPress Foundation trademark policy, <https://wordpressfoundation.org/trademark-policy/>, page undated, read by R-005 on 2026-11-22): non-licensed projects "cannot use them as part of a product, project, service, domain name, or company name". "WordPress" may never be part of a domain name. The policy also asks people not to use "WP" in any way that confuses people. Nominative use that explains a service is allowed.
- R-005 rates the candidate **"WPPostgres"** from [17 — Names](../17-names.md) as **high risk** and says the CLI name `wps` ("WordPress Shell") should be checked too. 17 states that domain, GitHub org, registry and trademark availability for all ten candidates were **not checked**.

## Decision

**Keep "Pressgres" as the working name and GPL-2.0-or-later as the project license. Never call the product "WordPress". Do not accept this ADR until the R-015 clearance checks listed below are complete.**

1. **License.** Pressgres code, patches (`License: GPL-2.0-or-later` header, ADR-001) and contributions are GPL-2.0-or-later. Third-party components keep their own notices and are never relicensed in place. Release notices state that the combined distribution may be governed by GPLv2-only terms where GPL-2.0-only components (the ADR-003 parser inputs) are included. Contributions use a DCO sign-off (proposed in R-005) to record provenance.
2. **Naming rules.**
   - The product is "Pressgres". Never "WordPress", "WordPress for PostgreSQL", "WP-anything" or similar.
   - Describe it nominatively, e.g. "Pressgres, a PostgreSQL distribution based on WordPress® 7.1.5 (modified)", with a statement that Pressgres is not affiliated with or endorsed by the WordPress Foundation or Automattic.
   - No "wordpress" in any domain. No "WP" in product, package or domain names where it could imply affiliation. "WPPostgres", "WPgres" and "WPGateway" are dropped.
   - CLI name: `wps` is **provisional** pending the R-015 check. Fallback: `pressgres` or `pgr`, not decided here.
3. **Admin branding.** Whether the patched admin keeps WordPress logos is left to legal review (R-005 open question 4). Until then, Pressgres-specific screens and the installer use Pressgres branding only and do not use the WordPress logo.
4. **No public launch assets** (logo, marketing domain, registry packages under the final name) before clearance.

## Consequences

- **Positive:** the license matches WordPress and every GPL input found so far, so redistribution is possible. The naming rules avoid the clearest trademark conflicts R-005 identified.
- **Negative:** the name may still have to change after clearance, with churn in the repo, org and package names. Without "WP" in the name, people searching for WordPress-related tools find the project less easily. GPLv2-only inputs mean the "or later" option cannot be exercised for the combined work.
- **Neutral:** these ADRs and the PRD keep using "Pressgres" as a working name.

## Alternatives considered

- **Permissive license (MIT or Apache-2.0):** incompatible with distributing modified GPL WordPress and derivative drop-ins. Apache-2.0 is also incompatible with GPLv2. Rejected.
- **GPL-3.0 or AGPL:** incompatible with GPL-2.0-only inputs (ADR-003). AGPL would add network-use obligations no upstream requires. Rejected.
- **"WPPostgres" or other WP-prefixed names:** most searchable, but R-005 rates it high risk under the Foundation's policy. Rejected.
- **Seek a trademark license from Automattic or the Foundation:** costly and uncertain, and unnecessary if nominative use suffices. Not pursued unless counsel says otherwise.

## Open items / revisit triggers

R-015 (pressgres/pressgres#16) must complete **all** of the following before this ADR can move to Accepted. **None of these checks has been done yet.**

- **Trademark searches** for "Pressgres" (and the CLI name `wps`) in the relevant classes (software, SaaS):
  - USPTO (TSDR / trademark search)
  - EUIPO (eSearch plus / TMview)
  - WIPO Global Brand Database
- **PostgreSQL mark:** check whether "Pressgres" raises a confusing-similarity concern under the PostgreSQL community trademark policy. Not reviewed by any spike.
- **Domains:** availability and ownership of `pressgres.org`, `pressgres.com`, `pressgres.dev` (and any other chosen TLD), with no "wordpress" in any domain.
- **Registries:** name availability or ownership on npm (`pressgres` and any scope), Packagist (`pressgres/*` vendor), and Docker Hub / GHCR image namespaces.
- **GitHub:** the project already uses the `pressgres` organization (this repository). Confirm there are no confusingly similar orgs or prior projects with the same name. Not checked.
- **Legal review** (counsel): R-005 open questions 1–6 (sufficiency of modification notices, source-offer form, Pressgres-only components and `wps` aggregation, "based on WordPress" wording and admin logos, Gutenberg relicensing, patent and attribution notices), plus the GPL-2.0-only parser notices from ADR-003.
- **Revisit** if any check finds a conflict. Pick a new name from [17](../17-names.md) that avoids "WP" and rerun the checks.
