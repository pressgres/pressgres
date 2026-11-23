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
| `wps init` | generate validated config | M1 implemented |
| `wps config validate` | validate YAML and secret references | M1 implemented |
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

## Tested configuration commands

From the repository root, generate and validate a configuration in a fresh output directory.

```bash
output_dir="$(mktemp -d)"
vendor/bin/wps init --profile postgres-native-uuid --output "$output_dir/pressgres.yaml" --dry-run
vendor/bin/wps init --profile postgres-native-uuid --output "$output_dir/pressgres.yaml"
vendor/bin/wps config validate --config "$output_dir/pressgres.yaml" --format=json
```

```text
Dry run complete. No files written.
Wrote configuration and .env.example.
```

```json
{
    "schema": "pressgres.cli/v1",
    "command": "config validate",
    "status": "ok",
    "exit_code": 0,
    "data": {
        "schema_version": "1.0"
    },
    "diagnostics": [],
    "correlation_id": null
}
```

`--output` defaults to `pressgres.yaml`. Its parent directory must exist. `init` writes the YAML with mode `0600` and writes a credential-free `.env.example` with mode `0644` alongside it. Either existing file causes exit 2 unless you pass `--force`. The command refuses symlinks and other non-regular destinations. It stages both files before publishing each atomically. The two publications are separate filesystem operations, so an abrupt interruption between them can leave one output. `--dry-run` checks the profile, templates and destination conflicts without writing files.

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

The installer resolves defaults < YAML < environment-supplied secret references < explicit non-secret CLI overrides. `wps config validate` checks the YAML layer against the [v1.0 schema](../apps/installer-cli/schemas/pressgres-v1.json). Set `schema_version: '1.0'`. Omitted settings are eligible for defaults during later configuration resolution. The [sample YAML](../examples/config/pressgres.yaml) matches the generated profile and includes the preview WordPress pin, native UUIDv7 and Valkey. Validation accepts a local YAML file up to 64 KiB and rejects aliases and custom tags.

The database runtime and migrator passwords and the Valkey password accept these forms.

- `env:NAME` uses an environment variable whose name matches `[A-Za-z_][A-Za-z0-9_]*`.
- `file:/absolute/path` uses an absolute local file path with a filename and without control characters. Quote the reference in YAML when the path contains spaces.

Keep the migrator's role and secret reference separate from the runtime's. Supply the migrator credential only to installer processes. `.env.example` lists variables with empty values, and both config commands treat references as syntax without reading their targets.

Exit 2 covers invalid YAML, unknown keys and other schema errors. Plaintext in password fields, invalid password references and a shared database password reference cause exit 5. Security failures take priority when both kinds of diagnostic are present. In JSON mode, `diagnostics[].context.path` carries an RFC 6901 JSON pointer. Unknown keys use the pointer to their containing mapping so the command can redact the key name as well as its value. The empty pointer denotes the document root.

## Installer anti-goals

Do not mutate existing site without explicit `--migration-plan`; do not uninstall existing `db.php`/`object-cache.php` silently; do not download PHP from arbitrary plugin URLs; do not auto-promote untested WordPress versions.
