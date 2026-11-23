# ADR-0005: Local development (DDEV and Docker Compose, no forced Docker production runtime)

- **Status:** Accepted (2026-11-23)
- **Date:** 2026-11-23
- **Deciders:** Project lead (solo maintainer)
- **Related issues:** R-003 (pressgres/pressgres#5), R-006 (pressgres/pressgres#8), R-009 (pressgres/pressgres#9); ADR-006, ADR-010

## Context

Contributors, CI and AI agents need a reproducible stack: PHP 8.4, PostgreSQL 18 with `uuidv7()`, the managed WordPress patchset, an object cache and disposable fixture databases. Production targets vary (VMs, Kubernetes, managed PostgreSQL), and the project should not dictate them ([12 — Local development](../12-local-development.md#recommendation)).

What exists today:

- Every spike so far has used **Docker Compose**: the [R-003 prototype](../../prototypes/r-003/docker-compose.yml), the [R-009 PHPUnit fixtures](../../tools/core-phpunit/compose.yaml) (pinned `postgres:18.6-alpine` and `mysql:8.4.13`) and the [R-006 sandbox](../../prototypes/r-006-sandbox/README.md). Each Compose project has a fixed name and loopback-bound ports so parallel stacks do not collide. That matters when several agents run spikes at the same time.
- **DDEV** is the common local tool in the WordPress agency world, which is one candidate first persona (R-008). [12](../12-local-development.md) cites DDEV docs saying PostgreSQL is a supported database service, but the exact DDEV version, `database.type` syntax for PostgreSQL 18 and cache add-on naming are **not verified**. The commands in that document are explicitly illustrative.
- The [threat model](../security/threat-model.md) and [12](../12-local-development.md#ocicontainer-image-guidance) both state that Docker Desktop and DDEV are **not security boundaries** for hostile plugin code (see ADR-004).

## Decision

**Docker Compose is the canonical, CI-tested development and fixture stack. DDEV is a supported convenience profile on top of the same pinned images and versions. Neither is a required production runtime.**

1. **Compose is the source of truth.** `docker/compose/` defines the reference stack: PHP 8.4 runtime, PostgreSQL 18 pinned by tag and digest, the object cache service, and a test runner with an isolated fixture database. CI runs the [12 smoke test](../12-local-development.md#ci-smoke-test) on this stack, and compatibility claims come from CI, not from developer machines.
2. **DDEV profile.** `.ddev/` provides the same versions for people who already use DDEV. It uses DDEV's own PostgreSQL service where it can rather than a second hidden one, and generates a Pressgres bootstrap instead of relying on stock `ddev config --project-type=wordpress` (which may assume MySQL). A DDEV release is listed as supported only after a CI job (or a scripted check run before each Pressgres release) passes on it. Until then it is `experimental`.
3. **Production stays open.** Pressgres ships an installable release artifact and, later, OCI images that follow [12](../12-local-development.md#ocicontainer-image-guidance): multi-stage builds, non-root users, a read-only root, and no baked secrets. Operators may run on VMs, Kubernetes or managed services. Nothing in the runtime requires Docker.
4. **Cache server choice is out of scope.** The dev stack includes whichever object cache backend ADR-010 picks (Valkey is the likely candidate, but this ADR does not decide it). Until then, the service name and drop-in stay abstract (`cache`).
5. **Agent-friendly defaults.** Each stack has a fixed Compose project name, loopback-only ports, `--pull never` for pinned images in hermetic runs, and one command to start and one to tear down. These are the conventions R-003, R-006 and R-009 already follow.

## Consequences

- **Positive:** one stack definition serves CI, agents and humans, and it matches what the spikes already use. DDEV users get a familiar entry point without the project depending on DDEV. Production operators are not forced into containers.
- **Negative:** two dev profiles to keep in sync. The DDEV profile can lag behind and is the first to drop if maintenance cost is too high. Developers on macOS or Windows still need a Docker-compatible engine.
- **Neutral:** [07 — Compatibility](../07-compatibility.md) keeps DDEV as "dev convenience; not production baseline". Linux x86_64 and arm64 remain the CI-gated production platforms (ADR-006).
- **Security:** neither profile is used to run untrusted plugin code. That goes to the isolation tiers in ADR-004.

## Alternatives considered

- **DDEV only:** good developer experience, but adds a dependency on DDEV's release cadence and PostgreSQL support for CI and agents, and is heavier for headless runners. Rejected as the canonical stack.
- **Compose only:** simplest to maintain, but ignores the tooling much of the WordPress community uses. Kept as canonical, with DDEV layered on top.
- **Docker as the mandatory production runtime:** limits operators, especially those on managed PostgreSQL and VMs, and suggests isolation guarantees Docker does not give. Rejected.
- **Native host installs (Homebrew or apt PHP and PostgreSQL):** not reproducible across machines and agents. Allowed for individuals but not supported.

## Open items / revisit triggers

- Verify and pin the DDEV version and PostgreSQL 18 configuration syntax in M1. This ADR does not claim DDEV supports PostgreSQL 18 today.
- Object cache service and drop-in: ADR-010.
- Revisit the DDEV profile if it fails CI for more than one Pressgres release in a row, or if user discovery (R-008) shows the first persona does not use DDEV.
