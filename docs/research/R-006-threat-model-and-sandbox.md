# R-006 · Threat model and plugin sandbox

**Issue:** #8 · **Status:** research spike · **Date:** 2026-11-23

## Scope and acceptance

This spike adds the [threat model](../security/threat-model.md), [Mermaid data flows](../../diagrams/threat-model.mmd), [Docker sandbox](../../prototypes/r-006-sandbox/README.md) and evidence under [data](data). The production assumptions are PHP-FPM, PostgreSQL roles per workload, UUIDv7-only identities and reviewed plugin promotion. The proof of concept uses CLI activation on WordPress develop 7.1.5 at `984163c92ef66b6186538ecf01bacb97fc097541`, PHP 8.4.27 with PDO PostgreSQL and PostgreSQL 18.6. It applies the R-003 core patch to a disposable copy and reuses its schema, seed options and database drop-in by path. The Gutenberg pin is `89408c2` in the checkout. The test leaves editor build, cache, importer, production install and upgrade outside its execution path. [PRD target versions](../07-compatibility.md), `wordpress-develop-7.1.5/src/wp-includes/version.php:19–26`, `wordpress-develop-7.1.5/package.json:9–12`.

Acceptance requires a persisted activation and writable upload for the benign fixture, positive and negative observations for HTTP, preserved core and schema, absence of restricted credentials, rejection of an integer UUID bind and forced termination of a loop. Provisioning, observation loss, unexpected activity and cleanup errors fail the run. Each fixture gets a fresh PostgreSQL container and writable scratch. The production activation and role contracts still require designated review. [Agent gates](../10-ai-agents.md), [PoC runner](../../prototypes/r-006-sandbox/sandbox.py).

## Sandbox design and controls

| Control | Enforcement and evidence |
| --- | --- |
| Pinned inputs | Require local exact-tagged PHP/PG images with `--pull never` and check PHP version/extension, PostgreSQL version and UUIDv7 generation. Record local image IDs. Check the WordPress SHA and clean source status, copy the reference and apply R-003 with zero fuzz. Release artifact authenticity and digest enforcement belong to the R-005 design. |
| Separate migration authority | Trusted setup runs the R-003 schema and seed SQL as a no-login schema owner. Runtime is a separate non-owner login with database CONNECT, schema USAGE and table DML. PUBLIC loses database and schema grants. The worker never gets the admin password or a route to the migration role. Direct PostgreSQL `CREATE`, `ALTER`, `DROP` and `CREATE TEMP` checks run under the effective runtime role inside rollback transactions from the trusted DB container. |
| Network | Two Docker internal IPv4 bridges use isolated gateway mode, with IPv6 disabled and no published ports. The PHP worker and disposable PostgreSQL share one bridge. A separate worker on the control bridge reaches the HTTP canary, and the activation fixture tries the same numeric endpoint with PHP streams. The observer checks the worker has no default IPv4 route. DNS is configured with container loopback as the upstream, and DB/canary targets use numeric addresses. |
| Filesystem | The container root, WordPress and mounted runner/fixture files are read-only. A 16 MiB tmpfs (`nosuid,nodev,noexec`) holds application-writable uploads, cache, transient output and logs. The staged WordPress upload path links to the scratch upload directory. IPC mode is `none`. The benign fixture resolves the WordPress upload path, and the write fixture targets `wp-includes`. A host check verifies that the marker did not reach staged core. |
| Process | UID/GID 65534, all capabilities dropped, `no-new-privileges` and seccomp filter mode enforced and checked. Docker policy sets 0.5 CPU, 256 MiB RAM with no additional swap and 32 PIDs. PHP has a 64 MiB memory limit. A four-second watchdog kills the PHP process, with a 14-second Docker wait deadline as a backstop. Container cleanup happens even on a failed check. |
| Credentials | Per-fixture generated admin and runtime passwords. Admin password stays with the disposable DB bootstrap. The worker receives a disposable runtime credential and synthetic env marker. The fixture checks named restricted env keys and the conventional secret mount, with no secret values emitted. A separate host-only marker verifies that the runner's environment does not flow into the worker by default. |
| Observations | Worker output gives fixture events, scratch file listings and JSONL query entries from the R-003 adapter. The driver collects container exit/OOM status, Docker settings, kernel policy, and independent SQL state from the DB. The HTTP event records target and success/error. Scratch and Docker log sizes are bounded, and the driver fails on an incomplete observation stream. |

Control inputs and verification are in [runner](../../prototypes/r-006-sandbox/sandbox.py), [role bootstrap](../../prototypes/r-006-sandbox/roles.sql), [worker observer](../../prototypes/r-006-sandbox/observe.sh), [R-003 schema](../../prototypes/r-003/sql/01-schema.sql) and [adapter logging](../../prototypes/r-003/wordpress/db.php#L650). WordPress includes the plugin and fires its callback before persisting activation. `wordpress-develop-7.1.5/src/wp-admin/includes/plugin.php:677–720`, `wordpress-develop-7.1.5/src/wp-admin/includes/plugin.php:2382–2389`. Its upload path resolves through `wp_get_upload_dir()` and the default content-directory path. `wordpress-develop-7.1.5/src/wp-includes/functions.php:2355–2357`, `2467–2496`.

The separate schema bootstrap follows the operational lesson from R-009. Its unmodified adapter run failed at the upstream install bootstrap. The wrapper variant with pre-created schema and one leaking test class excluded reached 77.47% comparable among control-passing test IDs. R-006 uses the R-003 adapter without the R-009 PHPUnit wrapper. [R-009 baseline](R-009-core-phpunit-baseline.md#postgresql-runs), `wordpress-develop-7.1.5/tests/phpunit/includes/install.php:57–80`.

## Evidence from UUID-related source review

R-003 observed `wp_insert_user()` return integer `1` without its patch and the adapter reject the resulting non-UUID user metadata bind. R-003 also observed truncated author URLs. The ownership comparisons in `map_meta_cap()` remain a source-based authorization concern. A strict comparison between a UUID user string and a cast author integer would fail the owner branch. Cross-object access becomes possible if downstream logic conflates the collapsed values, drops the ownership predicate, or uses a wrong lookup domain. This spike verifies the lossy cast and rejected bind only. [R-003 captured baseline and remaining issues](R-003-uuid-prototype.md#baseline-without-the-core-patch-verified), `wordpress-develop-7.1.5/src/wp-includes/user.php:2575`, `wordpress-develop-7.1.5/src/wp-includes/capabilities.php:149`, `:252`, `:374`.

I manually reviewed all **41** candidate lines from a targeted search of the user, capability and posts REST paths. **29** cast an identity operand, while **12** cover pagination, counts, menu order, user level, cookie expiry or multisite site/blog IDs beyond single-site scope. Treating every candidate as a UUID identity cast would yield **12/41 (29.3%) false positives** in these files. Confidence is high for the contextual classification and low for extrapolating across WordPress or plugins. Hits are source occurrences, and runtime reachability or a security impact requires a separate test. [Per-line review](data/R-006-uuid-cast-review.csv).

## Captured output

The offline run used Docker Engine 29.8.2 and exited 0 for `./run.sh all` and `./run.sh down`. The run printed the following outcomes. The [captured results](data/R-006-sandbox-results.json) retain events, exit codes, DB checks and query counts. The runner's full SQL log and policy for every fixture are in local `prototypes/r-006-sandbox/build/results.json`.

| Fixture | Expected behavior | Observed | Verdict |
| --- | --- | --- | --- |
| Benign | Allow activation, option and upload | Persisted option and upload marker, exit 0 | PASS |
| Egress | Block HTTP to a live target off the worker bridge | Control reached target. Worker got `Network unreachable`, exit 0 | PASS |
| Core write | Deny a write under `wp-includes` | `Read-only file system` with no marker, exit 0 | PASS |
| DDL | Deny adapter and direct runtime DDL | 2 adapter rejections and 4 PostgreSQL `42501` denials, exit 0 | PASS |
| Secret read | Reveal only disposable values to the fixture | Runtime password and fixture marker present. Restricted env and mount absent, exit 0 | PASS |
| UUID cast | Flag UUID-unsafe write | Cast to `1`, adapter rejected it, zero metadata rows, exit 0 | PASS |
| Infinite loop | Stop activation at the deadline | Hook entered and was killed with exit 137. Active list stayed empty | PASS |

`PASS` evaluates the expected fixture behavior. WordPress stores the first six plugins as active on their respective disposable DBs, even when the attempted operation was denied. In production the gate would use the findings to block promotion. The adapter emitted 511 query records across WordPress startup and activation, including three rejections. The four direct database probes appear separately in the DB observations.

## Limitations and isolation options

- **Docker** is inexpensive to reuse for these seven known fixtures. Workers share the surrounding Linux kernel and access a disposable DB using the permissions of WordPress. An internal bridge and a no-default-route check plus the canary establish the observed separation for this topology. DNS, IPv6 and alternative routing need their own negative tests on each deployment profile. Docker-provided device and system mounts are separate from application scratch.
- **gVisor** interposes a userspace kernel between container processes and the host kernel. It can preserve an OCI-style runner on a supported Linux host, with additional runtime setup, patching, performance and syscall compatibility tests. Its networking and volume policies still need explicit verification. [gVisor architecture](https://gvisor.dev/docs/architecture_guide/intro/).
- **Firecracker** runs a small guest VM behind a virtual machine boundary. It adds KVM-capable infrastructure, guest kernel and root image maintenance, networking setup and a lifecycle to provision and clean up each guest. For a solo maintainer, a managed disposable VM runner can trade infrastructure work for recurring runner cost and platform evaluation. Neither alternative was run and no cost or overhead estimate was measured. [Firecracker design](https://github.com/firecracker-microvm/firecracker/blob/main/docs/design.md).
- **Observation coverage** is for these known fixtures. SQL entries show calls the R-003 adapter handles, while file listings show files still present at the end and connection events are fixture reports. Direct PDO, deleted files, side-channel activity, log tampering and host kernel escapes are outside this evidence. Production use needs external observations, for example firewall events and redacted PostgreSQL metadata, on infrastructure separated from release and production credentials.
- **Lifecycle and limits** cover CLI activation only. FPM, HTTPS, filesystem PHP execution over HTTP, Redis, migration replay and plugin upgrade/uninstall are untested. CPU, memory and PID settings were inspected. Only the wall-clock limit was exercised to failure. The worker can read its own runtime credential and can use its runtime DML access. The Docker fixture run does not establish compatibility or safety of third-party plugins.

## Summary of findings

- **8 boundaries, 48 STRIDE scenarios and 10 ranked risks**, each threat row with a proposed verification and roadmap owner. Release signing, privilege separation, UUID authorization and plugin promotion are early gates. [Threat model](../security/threat-model.md#stride-by-boundary).
- **7/7 fixture verdicts passed** on Docker with synthetic data. PostgreSQL independently denied **4** DDL operations under the runtime role. The egress HTTP control succeeded before the worker's request failed. The loop exited **137** with no recorded activation. [Captured results](data/R-006-sandbox-results.json).
- **29 of 41** reviewed source hits cast an identity operand. Authorization consequences remain inferred until the non-admin ownership and wrong-entity regression tests run. [Manual review](data/R-006-uuid-cast-review.csv).

## Implications for the UUID patchset

| Category | Patch strategy |
| --- | --- |
| Core return values, identifiers, owner comparisons and sentinels | In the versioned WordPress series, preserve full canonical UUID strings from write through lookup and capability comparison. Patch actor/owner matching, remove coercion fallbacks and normalize missing values by field at the typed boundary. Add same-prefix, wrong-entity and non-admin permission tests (U-001, U-003, U-004). |
| REST and editor contracts | Patch WordPress routes, validation and JSON schemas in the WordPress series. Patch editor ID handling at Gutenberg source and rebuild the bundles under the separate R-005 series. Verify routes, errors, authorization and private UUID exposure with a pinned regression corpus (U-002, U-005). |
| DB adapter, schema and cache | Keep UUID binds and generated IDs typed end to end, use an AST allowlist and reject unresolvable types/predicates. Enforce privilege outside adapter code. Namespace cache keys by site and entity and include the complete UUID. Cover equal identifiers in unrelated domains (D-002, Q-001, S-001, C-001). |
| Plugins and releases | Reject unknown casts and unreviewed DDL. Use exact-digest plugin gates and reviewed schema migrations on the separate path. Review, test and verify the WordPress/Gutenberg series and release artifact as distinct inputs (U-005, P-001–P-005, O-005). |

## Open questions

- Which source paths still lose ownership or change a query's target under distinct, same-prefix UUIDs? Which require production blockers after R-009-style integration coverage?
- What measured timing difference remains between private and missing objects, and which public surfaces expose mint time by design?
- Which Linux runner and isolation profile provide practical external-plugin testing for a solo maintainer? How will it prove DNS/IPv6 policy, externally collect tamper-resistant evidence and test memory/PID exhaustion?
- Which runtime grants can be narrowed further without breaking required WordPress flows? Which privileges and short-lived credentials will a supported backup profile need?
- What are acceptable support and release turnaround targets when the maintainer is unavailable or a change requires an independent reviewer?

## Method and reproduction

Run from the worktree root with the local prerequisites in the [sandbox README](../../prototypes/r-006-sandbox/README.md).

```bash
(cd prototypes/r-006-sandbox && ./run.sh all && ./run.sh down)
(cd ../../reference && rg --no-heading --color never -n '\(int\)\s*\$' \
  wordpress-develop-7.1.5/src/wp-includes/capabilities.php \
  wordpress-develop-7.1.5/src/wp-includes/rest-api/endpoints/class-wp-rest-posts-controller.php \
  wordpress-develop-7.1.5/src/wp-includes/user.php)
awk -F, 'NR > 1 {counts[$2]++} END {for (key in counts) print key, counts[key]}' \
  docs/research/data/R-006-uuid-cast-review.csv
```

The search emits one candidate row per matching line, with no random subset. The hand-audited CSV records whether any match on that line is an in-scope identity cast. The false-positive rate is the `no` count divided by all review rows. The threat count is the number of STRIDE table rows across B1–B8, with one row per category per boundary. Docker verdict counts group the `fixtures[].verdict` values in `build/results.json`. The captured JSON is an extract of that run, retaining structured events and database checks and counting the raw SQL entries by `status`.

Local verification also ran `bash -n prototypes/r-006-sandbox/run.sh`, `sh -n prototypes/r-006-sandbox/observe.sh`, PHP syntax checks over the PoC PHP files, Mermaid 11.17.2 parsing and SVG rendering in an offline Chromium container, and `markdownlint-cli2` on the three new Markdown documents with the repository config. No reference checkout or R-003 files were edited.
