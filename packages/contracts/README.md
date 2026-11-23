# Pressgres contracts

`pressgres/contracts` is a PHP 8.4 Composer path package. Run `composer install` at the repository root to use the `Pressgres\Contracts` namespace. Root [development checks](../../docs/09-engineering-standards.md#local-php-checks) exercise the package through Composer's autoloader.

- `DatabaseDriverInterface` accepts a PostgreSQL statement and separate bindings. `SqlCompatibilityEngine` takes legacy SQL, bindings and catalog metadata. Only a successful translation can be sent to the driver.
- `SchemaMigrator` plans staged migrations from desired and observed metadata. `InstallerStep` defines planning, application, verification and best-effort compensation around a recorded plan and checkpoints.
- `PluginAnalyzer` reports static findings for a specific artifact. [ADR-0004](../../docs/adr/0004-plugin-support-model.md) governs approval and activation.
- `IdentityCodec` and its `UuidCodec` implementation accept canonical lowercase, hyphenated UUIDv7 text with an RFC variant. Decoding rejects all other values with `InvalidUuid`. Encoding, equality and JSON preserve the full string. Callers handle nullable references at the field boundary. [ADR-0002](../../docs/adr/0002-native-uuidv7-policy.md) governs identity and legacy sentinels.

`ExitCode` defines the [CLI statuses](../../docs/03-installer-cli.md#cli-commands-and-deterministic-exit-codes). `ErrorCode` maps stable string codes to failure statuses. The CLI can serialize a `Diagnostic` for `--format=json` using the current operation's correlation ID. Pass safe messages, locations and redacted context. Chained exceptions stay out of diagnostic JSON. Invalid input maps to status 2. When an invalid UUID is detected during verification, the verifier can report status 8 and retain the parsing exception as its cause.
