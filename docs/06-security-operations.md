# 06 — Security, backup, operations and threat model

## Security architecture

- Least privilege: `wps_migrator` owns/changes schema only at deploy time; `wps_runtime` accesses only required tables/functions and cannot CREATE/ALTER/DROP schema.
- Transport: PostgreSQL production connections require `sslmode=verify-full`, pinned trusted CA and hostname; Redis authenticated+TLS for remote connection, private network only.
- Web runtime does **not** store migration credentials, WordPress source or plugin installer secrets.
- Site config outside public webroot, env/secret manager; generate high-entropy WordPress keys and salts, rotate by runbook.
- Immutable application release, read-only core and PHP directories where possible; writable uploads only; prevent PHP execution in uploads.
- `DISALLOW_FILE_EDIT` and `DISALLOW_FILE_MODS` in production; deployment pipeline owns plugin/theme updates.
- Strict plugin review/compatibility approval, dependency vulnerability scan and cryptographic artifact hashes.
- HTTP HTTPS/HSTS when safely configured, secure cookies, restrictive filesystem umask, safe admin bootstrap, CSRF/capability checks, no secret logging.
- XML-RPC disable by policy unless integration exception documented. MFA offered via vetted plugin later; not required to implement custom auth in MVP.

## Threat model: STRIDE summary

| Threat | Boundary | Control | Verification |
|---|---|---|---|
| Malicious plugin PHP | plugin -> runtime | approved packages, isolate scan, disable dashboard installs | malicious fixture rejected |
| SQL injection | app -> SQL engine | parameterized binds, preserve query semantics | injection corpus |
| Privilege escalation | app -> PG | runtime role DML only | deny DDL integration test |
| Secret leakage | CLI/logs -> support | redaction and secret references | output snapshot tests |
| Cache poisoning | app -> Redis | namespaces, no Redis exposure, serialize safely | tenant isolation tests |
| Supply chain tampering | upstream downloads | checksum, signatures if available, lockfile | tampered artifact fail |
| Migration data loss | production schema | snapshot, approval, verified restore | restore rehearsal |
| SSRF/exfiltration in sandbox | plugin -> internet | restricted egress/no prod secrets | sandbox adversarial tests |

## Release artifact verification

The [release library](../packages/release/README.md) verifies detached Ed25519 signatures against a separately provisioned trust root. Its versioned lockfile binds the exact source and runtime pins, patch-series digests and artifact digests. The library streams hashes of privately staged files and verifies extracted trees against pinned digests. Signature and path safety failures map to exit code 5. Invalid lockfiles, size mismatches and digest mismatches map to exit code 8. Installer integration and signing real releases are follow-up work.

## Runtime security details

- Audit schema changes, plugin activation and upgrades; distinguish actor and correlation ID.
- Log SQL fingerprint and timing, never raw credentials/PII. Encrypt logs at rest; retention configurable.
- Use database timeout budgets and circuit-breaker logic; fail gracefully if Redis down with request-local cache where safe.
- For cookie/session caching, test global cache groups and object invalidation explicitly; no cross-site key collisions.
- WordPress capability checks remain authoritative. UUIDs are **not** an authorization system.
- Define a vulnerability disclosure process, supported-version policy, patch SLAs, SBOM and signed release artifacts before production.

## Backup/DR contract

- Periodic PG physical/logical backups with PITR strategy chosen by operator; uploaded media and external object storage backup consistent with DB snapshot.
- Record manifest of DB point, WordPress release, patchset, adapters, configuration and media/object snapshots.
- Test restore onto isolated environment before 1.0 and regularly afterward; record RPO/RTO objectives once actual infrastructure is known.
- Encryption at rest, off-site retention, least-privileged backup roles, restore credentials managed independently.
- On failed migration: stop writes, preserve logs, restore known checkpoint or implement validated forward fix; no implicit undo of external plugin effects.

## Observability

Export structured logs, OpenTelemetry-compatible spans, PG slow query data, Redis cache hit/miss/error, adapter failures, migration durations and plugin verdict counts. Health endpoints are authenticated/private and redact versions/connection strings. Define error budgets only after benchmarks on real workloads.
