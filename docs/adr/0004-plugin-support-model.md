# ADR-0004: Plugin support model (reviewed, signed manifests and disposable activation tests)

- **Status:** Accepted (2026-11-23)
- **Date:** 2026-11-23
- **Deciders:** Project lead (solo maintainer)
- **Related issues:** pressgres/pressgres#8 (R-006); R-014 (initial plugin targets), R-008 (user discovery), R-001, R-012; ADR-001, ADR-002, ADR-003, ADR-011

## Context

A SQL translator cannot repair PHP that casts post IDs to integers, uses `%d` for UUIDs or relies on `AUTO_INCREMENT` in business logic ([05 — Plugin compatibility](../05-plugin-compatibility.md#fundamental-truth)). With UUID-only identity (ADR-002), most of the plugin ecosystem will not work unmodified. Plugin support therefore has to be opt-in and backed by evidence. Activating a plugin also means running its PHP: WordPress includes the plugin file and fires its activation hook before recording it as active (`wp-admin/includes/plugin.php:677–720`, cited in the [threat model](../security/threat-model.md#b5--plugin-artifact-to-sandbox)).

Evidence:

- **[R-006](../research/R-006-threat-model-and-sandbox.md)** built a Docker activation sandbox on WordPress 7.1.5, PHP 8.4.27 and PostgreSQL 18.6. All **7/7 fixtures passed**: benign activation, blocked egress, denied core write, denied DDL (2 adapter rejections and 4 PostgreSQL `42501` denials), no restricted secrets visible, a UUID-unsafe cast rejected, and an infinite loop killed (exit 137) with no recorded activation.
- R-006 also states the limits. Docker workers **share the host kernel**. Only CLI activation was tested (not FPM, upgrade or uninstall). Only the wall-clock limit was exercised to failure. In-process observations can be tampered with by the plugin. The run does **not** establish that any third-party plugin is compatible or safe.
- The [threat model](../security/threat-model.md#top-10-risks) ranks "untrusted activation reaches real data or credentials" as risk 2 and "sandbox escape or egress reaches host resources" as risk 7. Its B5 row says Docker alone leaves the host and DB needing independent isolation, and that arbitrary external artifacts should run in stronger isolation.
- R-006 compared stronger options without running them. **gVisor** puts a userspace kernel between the container and the host, keeps an OCI-style runner, and needs runtime setup plus syscall-compatibility testing. **Firecracker** runs a microVM behind a VM boundary and needs KVM hosts, a guest kernel and image maintenance. No cost or overhead was measured for either.
- In a targeted review of capability, user and posts REST code, **29 of 41** candidate lines cast an identity operand. Static scanning finds candidates but proves nothing on its own.

## Decision

**Pressgres supports a plugin only at an exact version, through a reviewed, signed adapter manifest, after disposable activation tests pass. Everything else is blocked.**

1. **Default deny.** Unknown plugins, versions and digests are `BLOCKED`. There is no production bypass. Dashboard plugin installs are disabled (`DISALLOW_FILE_MODS`), and the supported path is the controlled `wps plugin install` flow in [05](../05-plugin-compatibility.md#plugin-installation-state-machine).
2. **Manifest.** `adapters/<slug>/<version-range>/manifest.yaml` uses the schema in [05](../05-plugin-compatibility.md#adapter-manifest-versioned-reviewed-not-arbitrary-php-generation). It records the identity contract, SQL ruleset, reviewed schema migrations (ADR-011), checks and verdict. It binds the **exact artifact digest**, not just slug and version. Trusted CI signs it after maintainer review. AI agents may draft manifests and adapters. Agents never activate, approve or sign (AGENTS rule 7, threat model B8).
3. **Static scan, then disposable activation.** The static scan classifies a plugin as `UUID_SAFE`, `SQL_ADAPTABLE`, `NEEDS_ADAPTER`, `UNSUPPORTED` or `UNKNOWN`. Disposable activation then runs install, activate, CRUD, upgrade and uninstall against a throwaway PostgreSQL. It uses synthetic data, disposable credentials, a runtime role that cannot run DDL, read-only core, no egress, and CPU, memory, PID and wall-clock limits. Evidence that decides promotion (exit status, DB state, network events) is collected outside the worker. An incomplete report blocks promotion.
4. **Isolation tiers.**
   - Docker with the R-006 controls is acceptable for **Pressgres-authored fixtures and plugins already under review**, where the main risk is a bug rather than an attack.
   - **Arbitrary external artifacts** (anything not yet reviewed) must run in a stronger boundary: gVisor or a disposable VM (Firecracker or a managed VM runner) on infrastructure separate from release and production credentials. Choosing between them is an open item. Until it is chosen, external artifacts are not executed. They are only statically scanned.
5. **Re-approval on every version.** Each new plugin version goes through scan, sandbox and review again. Approval is never carried over.
6. **Catalog size.** For a solo maintainer the supported catalog stays deliberately small. The **two initial targets are not chosen**. That is R-014, which is blocked by user discovery (R-008). This ADR fixes the mechanism, not the list.

## Consequences

- **Positive:** every supported plugin has reproducible evidence and an exact digest. Users see why a plugin is blocked, with evidence, instead of an opaque score. Runtime DDL and egress are denied at several layers. The model matches AGENTS rules 3 and 7.
- **Negative:** almost no plugins work at launch, and each new plugin version costs review time. That cost limits how large the catalog can grow. Running external artifacts safely needs infrastructure that is not built yet. Even inside the sandbox the plugin can read its own disposable runtime credential and use its DML grants.
- **Compatibility matrix:** one row per (plugin slug, exact version, digest, Pressgres release). A plugin is never listed as "compatible" without a passing manifest run.
- **Migration impact:** plugin tables are created only through reviewed migrations (ADR-011). For existing sites, plugin data without a typed mapper is quarantined (ADR-009).

## Alternatives considered

- **Automatic compatibility via SQL translation only:** cannot fix PHP integer casts or `%d` binds. R-006 shows the cast collapses a UUID to `1`. Rejected.
- **AI-generated PHP shims applied at runtime:** prohibited by AGENTS rule 7. Generated code is unreviewed code. Rejected.
- **Docker as the only sandbox for everything:** cheap and proven for the seven fixtures, but it shares the kernel, so it is too weak for hostile artifacts (threat model B5-E). Kept for trusted fixtures only.
- **Allow-all with runtime monitoring:** monitoring inside the same PHP process can be bypassed (direct PDO, log tampering). Rejected.
- **Community-maintained compatibility list without tests:** no evidence, and nobody to curate it. Rejected.

## Open items / revisit triggers

- **Initial plugin targets:** R-014, blocked by R-008 user discovery. Not decided here.
- **Strong isolation runner:** pick gVisor, Firecracker or a managed disposable VM, with measured overhead and cost. R-006 did not run either alternative.
- **Untested lifecycle:** FPM activation, plugin upgrade and uninstall, memory and PID exhaustion, DNS and IPv6 policy per deployment profile, and tamper-resistant external evidence collection.
- **Revisit** if the catalog review load grows beyond what one maintainer can sustain. The answer then is to shrink the catalog or bring in a reviewer, not to relax the gates.
