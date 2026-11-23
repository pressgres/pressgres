# R-006 plugin activation sandbox

This offline proof of concept runs seven checked-in plugins as untrusted code inside disposable Docker workers. It uses synthetic data and no production integrations. [Threat model](../../docs/security/threat-model.md), [results and limitations](../../docs/research/R-006-threat-model-and-sandbox.md).

## Prerequisites

- Docker Engine with isolated bridge gateway support (28+), Linux containers and the default seccomp profile enabled. The driver verifies isolation settings and fails if they are unavailable.
- Python 3, Git and `patch` with `--fuzz` support.
- Local images tagged `postgres:18.6-alpine` and `pressgres-r003-php:8.4.27`. Provision both from a trusted cache or image export before running. The latter is the image produced by [the R-003 Dockerfile](../r-003/docker/php/Dockerfile), with `pdo_pgsql`. The runner uses `--pull never`, performs no image build and reports the image IDs used.
- The read-only WordPress Git checkout at `reference/wordpress-develop-7.1.5` alongside the worktrees directory. Set `WP_DEVELOP_REF=/path/to/checkout` to use a different location. The expected commit is `984163c92ef66b6186538ecf01bacb97fc097541`.

## Run

From this directory:

```bash
./run.sh all
./run.sh down
```

`all` prints expected and observed outcomes and exits nonzero for mismatched evidence or provisioning/cleanup failures. It generates `build/results.json` with Docker policy, process policy, exit status, SQL, scratch files and fixture connection events. A run uses uniquely labeled Docker resources, removes them on exit, and replaces the previous local results. `down` removes any remaining labeled R-006 containers and networks, including interrupted runs, and keeps the local results. Use `down` after active runs have stopped.

## What the verdict means

`PASS` means the fixture produced the expected outcome. For four adversarial cases that reach the end of activation (HTTP, core write, DDL, UUID cast), the unsafe operation is blocked and WordPress still records the plugin as active in the disposable DB. The environment fixture confirms the worker sees its own disposable credential and marker. The harness verdict is separate from WordPress's activation return value. Production policy would block promotion of an unsafe plugin even if WordPress reports a successful activation.

The PostgreSQL schema and options are applied by the separate bootstrap path with a no-login schema owner. The plugin worker only gets the runtime password. Planned plugin migrations would run in a separate, reviewed migrator job. The fixture path never elevates the worker. [Plugin migration contract](../../docs/05-plugin-compatibility.md#plugin-schema-migration-algorithm).

The two isolated internal networks hold the worker and PostgreSQL on one side and a local HTTP canary on the other. A control client on the canary network confirms that the same endpoint is live. The fixture sends a raw PHP HTTP request from the worker network and reports the failure. All traffic stays within test infrastructure.

Results contain raw prototype SQL, which can contain literals even though the adapter omits bound values. Use only the synthetic checked-in fixtures. Logs and event files share a trust domain with plugin PHP and are incomplete evidence for arbitrary external code. The sandbox does not implement full plugin lifecycle or production approval. [Observation schema and isolation limits](../../docs/research/R-006-threat-model-and-sandbox.md).
