# 12 — Docker, DDEV and deployment

## Recommendation

**Yes: support both Docker and DDEV.** Docker Compose is the portable CI/developer integration fixture, DDEV is a first-class developer convenience profile. Neither should dictate production infrastructure; deployable OCI images with immutable tags and Helm/managed-service reference guide can come later.

DDEV already supports PostgreSQL as a database service in its architecture; avoid adding a second hidden Postgres service if a DDEV-configured database can be used. The object cache (Valkey, ADR-0010) is added through a custom DDEV Compose service; verify against an explicit DDEV release. Docs: <https://docs.ddev.com/en/stable/users/usage/architecture/> and <https://docs.ddev.com/en/stable/users/extend/additional-services/>.

## Development services

```text
php       PHP 8.4 FPM + CLI (docker/php/Dockerfile), runtime DB role only
postgres  PostgreSQL 18 with wps_owner / wps_migrator / wps_runtime roles (ADR-0011)
valkey    Valkey 9.2 object cache, password required, no persistence (ADR-0010)
mailpit   optional, Compose profile "mail"
```

Planned later: managed WordPress checkout, test-runner service with an isolated fixture database, telemetry collector.

## Docker Compose stack (canonical, tested)

The root [`compose.yaml`](../compose.yaml) is the canonical stack from ADR-0005. It lives at the repository root, not under `docker/compose/` as ADR-0005 sketched, so that plain `docker compose` works from a checkout. Supporting files are under [`docker/`](../docker/).

| Service | Image (pinned by tag and multi-arch digest in `compose.yaml`) |
| --- | --- |
| `php` | built from `php:8.4.28-fpm-trixie` + `composer:2.11.2`; adds `pdo_pgsql`, `pgsql`, `intl`, `zip`, `opcache`, PhpRedis 6.3.0 (PECL) |
| `postgres` | `postgres:18.7-alpine3.24` |
| `valkey` | `valkey/valkey:9.2.0-alpine3.24` |
| `mailpit` | `axllent/mailpit:v1.34.0` (profile `mail`) |

Tested commands (Docker 29.8.2, Compose v2, macOS arm64 / OrbStack, 2026-11-23):

```bash
cp .env.example .env            # replace every change-me value, e.g. with `openssl rand -hex 24`
docker compose up -d --build --wait
docker compose --profile mail up -d --wait   # optional Mailpit UI on 127.0.0.1:58026
docker compose exec php php -m
docker compose down -v          # removes containers, network and the pgdata volume
docker/smoke.sh                 # self-contained smoke test, see below
```

Conventions:

- **No committed secrets.** Compose refuses to start until `PG_SUPERUSER_PASSWORD`, `WPS_MIGRATOR_PASSWORD`, `WPS_RUNTIME_PASSWORD` and `VALKEY_PASSWORD` are set in `.env` (git-ignored). [`.env.example`](../.env.example) holds placeholders only.
- **Roles (ADR-0011).** [`docker/postgres/initdb/10-pressgres-roles.sh`](../docker/postgres/initdb/10-pressgres-roles.sh) runs on the first start of an empty volume. `wps_owner` (NOLOGIN) owns schema `public`. `wps_migrator` can `SET ROLE wps_owner` to apply migrations. `wps_runtime` has `CONNECT`, schema `USAGE` and DML via default privileges, with no `CREATE` and no `TEMPORARY`. Password changes in `.env` take effect only after `docker compose down -v`.
- **Runtime credentials only in PHP.** The `php` service gets `PG_RUNTIME_USER`/`PG_RUNTIME_PASSWORD` and `VALKEY_*`. Migrator credentials are passed per command (`docker compose exec -e ...`), never set in the service environment.
- **Agent-friendly.** Fixed project name (`pressgres-dev`, overridable with `COMPOSE_PROJECT_NAME`), loopback-only host ports (PostgreSQL 55436, Valkey 56380, Mailpit 58026; empty value means an ephemeral port), healthchecks on every service (PHP-FPM via its FastCGI ping), one named volume (`pgdata`). Loopback TCP to PostgreSQL requires a password (`--auth-host=scram-sha-256`).

### Smoke test

[`docker/smoke.sh`](../docker/smoke.sh) builds and starts the stack as project `pressgres-smoke` with random throwaway secrets and ephemeral ports (a local `.env` and a running `pressgres-dev` stack are not touched). It runs [`docker/smoke/check.php`](../docker/smoke/check.php) in the `php` container and always runs `docker compose down -v` at the end (`KEEP_STACK=1` keeps it for debugging). CI runs it in [`local-stack.yml`](../.github/workflows/local-stack.yml) on pull requests that touch the stack files.

Checks, all passing in the local run on 2026-11-23:

- PHP 8.4.28 with `pdo_pgsql`, `pgsql`, `redis` (6.3.0), `json`, `mbstring`, `curl`, `openssl`, `dom`, `xml`, `zip`, `intl`, `fileinfo`, `sodium`, OPcache loaded ([03 preflight](03-installer-cli.md#preflight-version-and-capability-checks)).
- As `wps_runtime` over the network: `server_version_num` = 180007 (>= 180000), `uuid_extract_version(uuidv7())` = 7.
- `wps_runtime` `CREATE TABLE`, `CREATE TEMPORARY TABLE`, `ALTER TABLE`, `DROP TABLE` and `TRUNCATE` all fail with SQLSTATE `42501`.
- `wps_migrator` creates a table as `wps_owner`. `wps_runtime` can insert into it and select by ID, and gets back the full UUIDv7 string.
- PhpRedis to Valkey: an unauthenticated client gets `NOAUTH`. After `AUTH`, `INFO server` reports `valkey_version` 9.2.0 and a UUID-keyed value round-trips.

Not covered yet: WordPress install, `wps doctor`, the object-cache drop-in, TLS to PostgreSQL or Valkey, outage recovery, and arm64/x86_64 parity in CI (CI runs on `ubuntu-latest` x86_64 only).

## DDEV profile (experimental, untested)

[`.ddev/`](../.ddev/) is an **experimental** profile per ADR-0005. It was written against the DDEV v1.25.6 documentation (released 2026-11-20). **DDEV was not installed on the authoring machine, so `ddev start` has not been run.** Do not list DDEV as supported until `ddev pressgres-smoke` passes on a pinned DDEV release.

```bash
ddev pressgres-secrets   # writes gitignored .ddev/.env.web.local, .env.valkey.local, .env.pressgres-roles.local
ddev start
ddev pressgres-roles     # creates wps_* roles in DDEV's PostgreSQL via the Compose init script
ddev pressgres-smoke     # runs docker/smoke/check.php in the web container
```

What the profile does:

- `type: php` (not `wordpress`) and `disable_settings_management: true`, so DDEV does not generate a MySQL-style `wp-config.php`.
- `php_version: "8.4"`, `database: {type: postgres, version: "18"}` (DDEV v1.25.6 docs list Postgres 9–18), `ddev_version_constraint: ">= v1.25.6"`.
- `docker-compose.valkey.yaml` adds a `valkey` service with the same pinned image as Compose, instead of the `ddev/ddev-redis` add-on (v3.0.0 defaults to the floating tag `valkey/valkey:9`).
- Secrets go in `.ddev/.env.*.local` files, which DDEV v1.25.4+ gitignores. The migrator password is in `.env.pressgres-roles.local`, which does not match any service name, so DDEV never injects it into a container.

Unverified points (to resolve before calling DDEV supported):

1. `ddev start` succeeds with this `config.yaml` (including the `public` docroot not existing yet) and actually runs PostgreSQL 18. Which 18.x patch release DDEV ships is not pinned by this profile.
2. The DDEV PostgreSQL superuser and database are both `db`, and the db container is named `ddev-<sitename>-db` with `psql` available. `pressgres-roles` assumes this. A partial check ran the script against a stand-in `postgres:18.7` container started with `POSTGRES_USER=db`, not DDEV's image.
3. The DDEV PHP 8.4 web image ships `pdo_pgsql`, `pgsql`, `redis` (PhpRedis), `intl`, `zip`, `sodium` and OPcache. If not, add `webimage_extra_packages` (for example `php8.4-redis`).
4. `.ddev/.env.valkey.local` reaches both the Valkey container environment and compose interpolation, and `valkey` resolves from the web container.
5. Custom host commands run from `.ddev/commands/host/` with `DDEV_APPROOT` and `DDEV_SITENAME` set, and the web container mounts the project at `/var/www/html`.

## OCI/container image guidance

- Separate build and runtime images, multi-stage builds, non-root where possible, pinned digests, read-only filesystem except designated writable dirs, immutable WordPress release artifacts.
- Don't bake passwords, salts or installation credentials into images.
- One migration/installer job with elevated DB permissions, short-lived token; PHP-FPM runtime uses constrained DB role.
- PostgreSQL/Redis use managed services in production when available. Avoid bundling DB inside the PHP image.
- Provide deployment examples for Kubernetes and simple VMs only after stable installer. Docker Desktop and DDEV are not security boundaries for hostile plugin execution.

## CI smoke test

Target: build PHP 8.4 runtime, launch PG18 + Valkey, verify `uuidv7()`, apply exact WordPress patchset, run `wps install`, create/read post via WP CLI and REST, run cache invalidation, record logs and versions. CI is source of compatibility claims.

Implemented so far (I-006): the first three steps plus role and cache checks, via `docker/smoke.sh` in [`local-stack.yml`](../.github/workflows/local-stack.yml). The WordPress patchset, `wps install`, WP-CLI/REST and cache invalidation steps come with later M1/M2 tasks.
