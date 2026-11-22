# 12 — Docker, DDEV and deployment

## Recommendation

**Yes: support both Docker and DDEV.** Docker Compose is the portable CI/developer integration fixture, DDEV is a first-class developer convenience profile. Neither should dictate production infrastructure; deployable OCI images with immutable tags and Helm/managed-service reference guide can come later.

DDEV already supports PostgreSQL as a database service in its architecture; avoid adding a second hidden Postgres service if a DDEV-configured database can be used. Add Redis through DDEV add-on/custom Compose integration; verify against an explicit DDEV release. Docs: https://docs.ddev.com/en/stable/users/usage/architecture/ and https://docs.ddev.com/en/stable/users/extend/additional-services/.

## Development services

```text
DDEV web/PHP 8.4 + managed WordPress checkout
DDEV DB server (PostgreSQL 18 configured)
Redis service (dedicated, namespaced, optionally local TLS policy)
Optional Mailpit, admin DB browser, telemetry collector
Test-runner service with isolated PG fixture DB
```

## Expected developer commands (to build)

```bash
ddev config --project-type=wordpress --docroot=public
# Configure supported PostgreSQL 18 database type in DDEV settings.
ddev start
ddev exec composer install
# From web container:
ddev exec wps doctor
ddev exec wps install --config .pressgres/dev.yaml
```

**Important:** These commands are **illustrative**, not tested; the exact DDEV `database.type` syntax, PHP compatibility and Redis add-on naming must be resolved in M1 and pinned in docs. Default DDEV WordPress templates may expect MySQL, so generate dedicated Pressgres bootstraps rather than trusting stock `ddev config` to be sufficient.

## OCI/container image guidance

- Separate build and runtime images, multi-stage builds, non-root where possible, pinned digests, read-only filesystem except designated writable dirs, immutable WordPress release artifacts.
- Don't bake passwords, salts or installation credentials into images.
- One migration/installer job with elevated DB permissions, short-lived token; PHP-FPM runtime uses constrained DB role.
- PostgreSQL/Redis use managed services in production when available. Avoid bundling DB inside the PHP image.
- Provide deployment examples for Kubernetes and simple VMs only after stable installer. Docker Desktop and DDEV are not security boundaries for hostile plugin execution.

## CI smoke test

Build PHP 8.4 runtime, launch PG18 + Redis, verify `uuidv7()`, apply exact WordPress patchset, run `wps install`, create/read post via WP CLI and REST, run cache invalidation, record logs and versions. CI is source of compatibility claims.
