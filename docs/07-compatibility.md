# 07 — Supported versions and installer compatibility policy

**Snapshot as of 2026-11-22; verify before implementation/release.** There are two separate meanings of support: **upstream WordPress can run on a version** and **Pressgres has tested its managed UUID patchset on that version**. The second is a much narrower matrix.

| Component | Initial supported target | Other versions | Installer behavior |
|---|---|---|---|
| WordPress | **7.1**, exact pinned patch release/build and checksum | Next releases experimental until patchset revalidated | hard fail if no matching signed patch manifest |
| PHP | **8.4.x**, supported upstream patch level | 8.5.x CI-candidate; 8.3 and older not supported by Pressgres MVP | check CLI and FPM versions/extensions |
| PostgreSQL | **18.x** | 19.x candidate after tested; 17 and earlier reject for native `uuidv7()` default | require `uuidv7()` + extract version returns 7 |
| Redis / Valkey | **Redis 7.4.x/8.x or Valkey 8.x** after CI validation of selected object-cache integration; licensing choice pending ADR-010 (Redis 7.4+ RSAL/SSPL, 8.x adds AGPL; Valkey BSD) | version policy frozen in release lockfile | verify INFO, TLS, auth and cache ops |
| Composer | **2.x** exact supported minor in CI | newer as validated | reject unsupported platform |
| WP-CLI | **2.x** exact tested release in lockfile | other versions subject to integration tests | diagnostic warning/block as appropriate |
| OS/arch | Linux x86_64, arm64 (CI gated) | Windows/macOS via DDEV locally | container/environment checks |
| DDEV | `experimental` profile in `.ddev/` (PostgreSQL 18, Valkey service), written for DDEV v1.25.6 but not yet run | list a DDEV release only after `ddev pressgres-smoke` passes on it | dev convenience; not production baseline |
| Browsers | recent evergreen Chromium/Firefox/Safari | managed WordPress editor must be tested | E2E gate |

Development stack pins (I-006, not a release support claim): the Compose stack in [12](12-local-development.md#docker-compose-stack-canonical-tested) uses PHP 8.4.28 (FPM, PhpRedis 6.3.0), `postgres:18.7-alpine3.24` and `valkey/valkey:9.2.0-alpine3.24`, each pinned by digest. Its smoke test (`docker/smoke.sh`) passes locally and runs in CI. The Redis / Valkey row above stays provisional until the ADR-0010 drop-in acceptance tests pass.

Note: WordPress 7.1 released Aug 19, 2026 according to official hosting compatibility guide. Upstream WordPress minimum PHP 7.4 does **not** imply Pressgres supports 7.4. Official WordPress documentation lists PHP 8.5 compatibility for recent WordPress versions, but Pressgres will admit it only when its own regression tests pass. PostgreSQL 18 is selected specifically for native `uuidv7()`.

## Mandatory extensions

- `pdo_pgsql`, `openssl`, `json`, `mbstring`, `curl`, `dom`, `xml`, `zip`, `intl`, `fileinfo`, `sodium`; `redis` PHP extension matching vetted cache drop-in.
- `pgsql` optional unless driver/tools depend on it; `opcache` strongly recommended; `imagick` optional but media capability checked.
- Verify PHP CLI + PHP-FPM both satisfy requirements, memory/time limits, `allow_url_fopen` policy, missing extensions and common WordPress functions.

## Exact-version strategy

Installer downloads only release-manifest entries containing upstream WordPress archive hash, compatible patch series hash, Composer lock hash, tested PHP/PostgreSQL/Redis versions, and migration schema version. Unsupported combinations never downgrade to legacy integer IDs without operator choice and different profile. Candidate matrices stay explicitly `experimental`.

## CI matrix

- Contracts checks cover PHP 8.4.27, canonical UUIDv7 text handling and CLI error mapping. Runtime support still depends on the integration and release gates below.
- Required: WP 7.1 pinned x PHP 8.4 x PG 18 x supported Redis release on x86_64; repeat on arm64 before claiming arm64.
- Exploratory: PHP 8.5, PG 19 and next WP line in non-release jobs.
- Unit: native SQL/UUID, adapter compiler, format semantics, config schema.
- Integration: real PG roles, TLS, Redis, DB drop-in, wpdb compatibility, schema migration.
- E2E: site install, users/posts/taxonomy/comments/media, Gutenberg, REST, plugin lifecycle, upgrade and backup restore.
- Negative: unsupported version, bad TLS, stale patch, invalid UUID, unsafe plugin, Redis outage, migration interrupt.

## Authoritative resources

- WordPress version 7.1 hosting compatibility: <https://make.wordpress.org/hosting/handbook/compatibility/version/7-1/>
- WordPress PHP compatibility: <https://make.wordpress.org/core/handbook/references/php-compatibility-and-wordpress-versions/>
- WordPress server requirements: <https://wordpress.org/about/requirements/>
- PostgreSQL 18 UUID: <https://www.postgresql.org/docs/18/datatype-uuid.html>
- DDEV services: <https://docs.ddev.com/en/stable/users/extend/additional-services/>
