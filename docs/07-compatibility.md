# 07 — Supported versions and installer compatibility policy

**Snapshot as of 2026-11-22; verify before implementation/release.** There are two separate meanings of support: **upstream WordPress can run on a version** and **Pressgres has tested its managed UUID patchset on that version**. The second is a much narrower matrix.

| Component | Initial supported target | Other versions | Installer behavior |
|---|---|---|---|
| WordPress | **7.1**, exact pinned patch release/build and checksum | Next releases experimental until patchset revalidated | hard fail if no matching signed patch manifest |
| PHP | **8.4.x**, supported upstream patch level | 8.5.x CI-candidate; 8.3 and older not supported by Pressgres MVP | check CLI and FPM versions/extensions |
| PostgreSQL | **18.x** | 19.x candidate after tested; 17 and earlier reject for native `uuidv7()` default | require `uuidv7()` + extract version returns 7 |
| Redis / Valkey | **Valkey 9.2.x** default per ADR-0010, subject to CI validation of the object-cache integration | Standalone Redis 8.12.x candidate after CI validation | verify INFO, TLS, auth and cache ops |
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

The [CLI release manifest](../apps/installer-cli/release/manifest.json) reports the preview baseline of WordPress 7.1.5 with a pinned Gutenberg commit, PostgreSQL 18 as the floor, and Valkey 9.2.0 as the default under [ADR-0010](adr/0010-object-cache-backend.md). The CLI tests verify that these pins are reported in both formats. Managed runtime compatibility remains subject to the release gates.

## CI matrix

The matrix has two tiers (I-011, [ADR-0006](adr/0006-version-policy.md)). **Required** cells block merges. **Exploratory** cells run the same checks with `continue-on-error`, so they never block. A green exploratory cell is a signal, not support: a version moves from candidate to supported only when the full ADR-0006 gate set passes on it.

| Workflow | Cell | Tier | Images (digest-pinned) | Checks |
|---|---|---|---|---|
| `php.yml` | `checks` | required | `php:8.4.27-cli-bookworm` | Composer validate, install, platform reqs, audit, cs, analyse, test |
| `php.yml` | `checks (exploratory, PHP 8.5)` | exploratory | `php:8.5.13-cli-bookworm` | same as required |
| `local-stack.yml` | `Compose smoke (PHP 8.4, PostgreSQL 18, Valkey 9.2)` | required | `postgres:18.7-alpine3.24`, `valkey/valkey:9.2.0-alpine3.24`, PHP 8.4.28 FPM | `docker/smoke.sh` |
| `local-stack.yml` | `Compose smoke (exploratory, PostgreSQL 19)` | exploratory | `postgres:19.0-alpine3.24` via `PG_IMAGE`, rest as required | `docker/smoke.sh` |

Each workflow ends with a summary job that writes a table of every cell, its tier and its outcome to the run's job summary. The required cells keep their original job names, so existing status checks still match.

To run the exploratory server locally, set `PG_IMAGE` (unset means the `compose.yaml` default): `PG_IMAGE=postgres:19.0-alpine3.24@sha256:8b0ff4cdf221f0c53d7fcda681d3b461be725c492cd881c5ec9c0ad25023f188 docker/smoke.sh`. As of 2026-11-23 the PHP 8.5.13 Composer checks and the PostgreSQL 19.0 smoke both pass locally. PHP 8.5 and PostgreSQL 19 remain candidates.

Planned scope beyond the current matrix:

- Contracts checks cover canonical UUIDv7 text handling and CLI error mapping. Runtime support still depends on the integration and release gates below.
- Required: WP 7.1 pinned x PHP 8.4 x PG 18 x supported Redis release on x86_64; repeat on arm64 before claiming arm64.
- Exploratory: the next WP line in non-release jobs, alongside PHP 8.5 and PG 19.
- Unit: native SQL/UUID, adapter compiler, format semantics, config schema.
- Integration: real PG roles, TLS, Redis, DB drop-in, wpdb compatibility, schema migration.
- E2E: site install, users/posts/taxonomy/comments/media, Gutenberg, REST, plugin lifecycle, upgrade and backup restore.
- Negative: unsupported version, bad TLS, stale patch, invalid UUID, unsafe plugin, Redis outage, migration interrupt.
- Core PHPUnit (I-010, `.github/workflows/core-phpunit.yml`): the upstream `wordpress-develop` 7.1.5 suite runs on PostgreSQL 18 on every relevant PR and on `main`. Per [ADR-0006](adr/0006-version-policy.md), the **gate is the ratchet**: a committed expected-pass list (`tools/core-phpunit/baseline/expected-pass.txt`) where any test that stops passing fails CI, plus failure if the bootstrap does not reach PHPUnit or the JUnit test count drops by more than 1 %. The **pass rate**, and the comparable pass rate against a MySQL control, is a **published trend**, never a pass/fail threshold. Until the managed patchset exists (M2), the PostgreSQL target is the R-003 prototype in R-009 configuration PG-C, so the numbers measure distance from the target, not support. Details: [tools/core-phpunit/README.md](../tools/core-phpunit/README.md#ci-i-010).

## Authoritative resources

- WordPress version 7.1 hosting compatibility: <https://make.wordpress.org/hosting/handbook/compatibility/version/7-1/>
- WordPress PHP compatibility: <https://make.wordpress.org/core/handbook/references/php-compatibility-and-wordpress-versions/>
- WordPress server requirements: <https://wordpress.org/about/requirements/>
- PostgreSQL 18 UUID: <https://www.postgresql.org/docs/18/datatype-uuid.html>
- DDEV services: <https://docs.ddev.com/en/stable/users/extend/additional-services/>
