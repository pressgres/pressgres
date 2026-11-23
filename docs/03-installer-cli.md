# 03 — Installer PRD and `wps` CLI

## User journeys

1. `wps init --profile postgres-native-uuid` generates a safe, commented YAML and `.env.example`.
2. `wps doctor --config pressgres.yaml` checks supported versions, PHP extensions, PostgreSQL UUIDv7 function, Redis, TLS, permissions and core patch availability.
3. `wps plan install --config ... --output plan.json` produces a non-mutating, deterministic plan; exit nonzero for blockers.
4. `wps install --config ...` creates install lock, backup checkpoint where relevant, staged artifacts, roles/schema, drop-ins, WordPress config, UUID-aware site and admin.
5. `wps verify --all` runs functional assertions and reports all required pass/fail status.
6. `wps plugin scan <zip-or-slug>`; `wps plugin plan <slug>`; `wps plugin install <slug> --approved-manifest <hash>`; `wps plugin activate <slug>` gated.
7. `wps migrate plan --source=<profile>` and `wps migrate apply --plan=<signed-plan>`; `wps migrate verify`.
8. `wps upgrade plan --wordpress=<verified-version>`, `wps upgrade apply`, `wps rollback --checkpoint=<id>` if restoration path valid.

## CLI commands and deterministic exit codes

| Command | Intent | Maturity |
|---|---|---|
| `wps version` | versions/hashes | M1 implemented |
| `wps init` | generate validated config | M1 |
| `wps doctor` | environment preflight | M1 |
| `wps plan install` | non-mutating plan | M1 |
| `wps install` | provision & initialize | M2 |
| `wps verify` | runtime and identity integrity | M2 |
| `wps plugin scan/check` | inspect ZIP, identify hazards | M3 |
| `wps plugin plan/install/activate` | gated deployment | M4 |
| `wps migrate plan/apply/verify` | supported migration workflow | M4 |
| `wps backup/restore/restore-test` | operator safety | M4 |
| `wps upgrade plan/apply` | tested upgrades | M5 |
| `wps rollback --checkpoint=<id>` | restore a recorded checkpoint when a valid restoration path exists | M5 |
| `wps support bundle --redact` | debugging | M5 |

Exit codes: 0 successful; 1 unexpected internal error (bug; always includes correlation ID); 2 invalid usage/config; 3 unsupported version; 4 unreachable dependency; 5 security failure; 6 incompatible plugin/SQL; 7 migration failure; 8 verification failure; 9 partial application requires recovery; 10 lock contention. Structured JSON output with `--format=json`; `--no-interaction`; `--dry-run` on mutating operations.

## Tested `wps version` output

After `composer install` in the repository root, run `vendor/bin/wps version`. The test suite snapshots both formats using the running PHP version. The examples below were captured with PHP 8.4.27.

```text
Pressgres 0.1.0
PHP 8.4.27
WordPress 7.1.5 (wordpress-develop: 984163c92ef66b6186538ecf01bacb97fc097541)
Gutenberg 89408c2b9bd944575dfa9039bc6870da1c8f56cb
PostgreSQL 18 (minimum major)
Valkey 9.2.0 (default)
Artifact hashes
  wordpress_archive_sha256: unavailable
  patchset_sha256: unavailable
  gutenberg_archive_sha256: unavailable
  composer_lock_sha256: unavailable
```

Run `vendor/bin/wps version --format=json --no-interaction` for the [`pressgres.cli/v1` result envelope](../apps/installer-cli/schemas/cli-v1.json).

```json
{
    "schema": "pressgres.cli/v1",
    "command": "version",
    "status": "ok",
    "exit_code": 0,
    "data": {
        "pressgres_version": "0.1.0",
        "php_version": "8.4.27",
        "wordpress_version": "7.1.5",
        "wordpress_develop_commit": "984163c92ef66b6186538ecf01bacb97fc097541",
        "gutenberg_commit": "89408c2b9bd944575dfa9039bc6870da1c8f56cb",
        "postgresql_minimum_major": 18,
        "valkey_default_version": "9.2.0",
        "artifact_hashes": {
            "wordpress_archive_sha256": null,
            "patchset_sha256": null,
            "gutenberg_archive_sha256": null,
            "composer_lock_sha256": null
        }
    },
    "diagnostics": [],
    "correlation_id": null
}
```

JSON mode writes one envelope to stdout, including on usage and internal errors. `command` is `null` when the dispatcher cannot identify a command. For failures the envelope includes a diagnostic and a matching correlation ID. Human mode sends errors to stderr. The checked-in manifest records preview pins and uses `null` for unavailable release hashes.

## Preflight version and capability checks

- PHP binary and FPM runtime must agree; check 8.4.x and required extensions: `pdo_pgsql`, `pgsql` if used, `redis`, `json`, `mbstring`, `curl`, `openssl`, `dom`, `xml`, `zip`, `intl`, `fileinfo`, `sodium` (project policy, not all upstream WordPress requirements).
- WordPress source must exactly match a tested release and patch manifest.
- PostgreSQL `server_version_num >= 180000`; `SELECT uuid_extract_version(uuidv7()) = 7`.
- DB TLS `verify-full` and trusted CA for remote production, with correct hostname and no plaintext downgrade.
- Redis authenticated, namespaced and TLS in production; verify supported Redis protocol/features and failure fallback.
- Writable temporary staging directory; no writes required to live core by PHP web process in production.
- Validate planned DB migration role and runtime role have intentionally separate grants.
- Check disk, memory, migrations lock, backups, object-store permission if configured, admin email and site URL.

## Install transaction and resume semantics

State file contains step ID/version/checksum, `PENDING|RUNNING|DONE|FAILED`, artifacts and timestamps. Write atomically with restrictive permissions. Acquire an advisory lock; do not assume transactional DDL protects filesystem operations. Immutable release directories + atomic symlink deployment preferred. Verify backups **before** applying destructive changes. Record compensating actions but recognize plugin side effects cannot reliably be rolled back.

## Installation phases

`validate -> plan -> acquire lock -> fetch/verify core -> apply UUID patches -> provision roles -> schema migrate -> drop-ins -> wp-config -> bootstrap admin -> healthcheck -> seal manifest -> release`.

Only installer process receives migration credentials. Do not include them in permanent web/FPM env. Provision first admin via a single-use prompt or secret reference, never CLI history arguments. Never expose setup after install; remove installer capability or lock it with re-authentication.

## Configuration resolution

Merge defaults < checked-in YAML < environment secret references < explicit CLI overrides (non-secret only). Reject unknown keys and inconsistent flags. Never print resolved secrets. Sign/lock effective non-secret config and artifact hashes for audits. Sample: [config](../examples/config/pressgres.yaml).

## Installer anti-goals

Do not mutate existing site without explicit `--migration-plan`; do not uninstall existing `db.php`/`object-cache.php` silently; do not download PHP from arbitrary plugin URLs; do not auto-promote untested WordPress versions.
