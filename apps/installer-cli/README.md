# Pressgres installer CLI

From the repository root, install the locked dependencies with `composer install` and run either entry point.

```bash
apps/installer-cli/bin/wps version
vendor/bin/wps version --format=json --no-interaction
```

The package uses a small PHP dispatcher for one read-only command and two global options. This keeps the runtime dependency limited to the shared Pressgres contracts while the command set is small.

The [CLI result schema](schemas/cli-v1.json) covers every command and usage failure. JSON mode writes one result to stdout for any application exit code. Human mode writes success to stdout and diagnostics to stderr. `--format=human` is the default. Put global options before or after the command. `version` never prompts and accepts `--no-interaction`.

`version` pairs the application version constant and the running PHP binary's version with the pins in the [release manifest](release/manifest.json). The manifest describes the preview baseline. Release tooling can supply lowercase SHA-256 digests there when artifacts are available. Missing hashes appear as `null` in JSON and `unavailable` in human output.

Run `composer cs`, `composer analyse` and `composer test` from the repository root.
