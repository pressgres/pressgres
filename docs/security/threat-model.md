# Pressgres threat model

**Status:** Proposed controls for R-006. The production model assumes a managed WordPress 7.1 patchset, PHP 8.4, PostgreSQL 18 and UUIDv7-only identities. Exact production versions, object cache backend and release policy remain open. The sandbox tests the pinned research stack separately. [Version policy](../07-compatibility.md), [R-006 evidence](../research/R-006-threat-model-and-sandbox.md).

## System context and data flows

[Mermaid data-flow diagram](../../diagrams/threat-model.mmd). The diagram assigns roles to processes and marks trust boundaries. Edges describe intended production flows, with B5 showing a separate disposable test system.

| Boundary | Crossing and security-sensitive assets |
| --- | --- |
| B1 Client → WordPress | Administrators and REST clients cross HTTPS ingress into PHP-FPM. Assets include sessions, application passwords, capabilities, private content and full UUIDs identifying posts, users, comments, terms and media. |
| B2 Installer → production data | `wps` resolves a separately scoped migrator secret during a reviewed install, import or upgrade. It applies an exact plan and seals a release. Assets include schema ownership, migration checksums and the restricted, entity-typed legacy ID crosswalk. |
| B3 Runtime → PostgreSQL | PHP-FPM and approved plugins share the runtime login and its required data grants. PostgreSQL enforces the migrator, runtime and backup privilege split. Assets include content, user records, auth state and the schema. |
| B4 Runtime → cache and filesystem | PHP-FPM reads and updates private cache entries, reads sealed core and plugin artifacts, and writes media to a separate upload store. Assets include cached authorization data, cache credentials and uploaded files. |
| B5 Plugin artifact → sandbox | The exact plugin bytes cross from quarantine into disposable activation. The worker sees synthetic data and disposable credentials. Observations cross back into trusted review as untrusted input. Sandbox approval binds the tested digest and version tuple before staging. |
| B6 Upstream and CI → signed release | WordPress, Gutenberg, dependency and image inputs feed unprivileged builds and the R-005 patch series. A protected release job signs the reviewed artifact digest. Assets include patch order, lockfiles, provenance, SBOM and signing authority. |
| B7 Production → backup and diagnostics | The backup worker reads PostgreSQL and a matching media snapshot. Restricted operators can restore a verified set and export redacted diagnostics. Assets include retained DB/media copies, encryption keys, restore credentials and audit history. |
| B8 Agent → execution and approval | AI agents and bots propose changes, inspect untrusted artifacts and run disposable tests. Protected workflow permissions and the maintainer govern promotion. Assets include branch protections, CI tokens, migration/activation authority and review evidence. |

Boundary assumptions come from [installer phases and credential flow](../03-installer-cli.md), [UUID schema and crosswalk](../04-data-model.md), [plugin lifecycle](../05-plugin-compatibility.md), [security/DR](../06-security-operations.md) and [agent authority](../10-ai-agents.md). Source anchors for the WordPress and Gutenberg edges are `wordpress-develop-7.1.5/src/wp-admin/includes/plugin.php:647–720` (activation), `wordpress-develop-7.1.5/src/wp-includes/load.php:833–852` (cache drop-in), `wordpress-develop-7.1.5/src/wp-includes/functions.php:2467–2496` (upload path) and `wordpress-develop-7.1.5/package.json:9–12` (Gutenberg pin). Backup and restore are separate authorities. The backup role is product intent, with exact grants depending on the chosen physical or logical backup profile.

## STRIDE by boundary

S is spoofing, T tampering, R repudiation, I information disclosure, D denial of service and E elevation of privilege. Likelihood (L) assumes the proposed PRD controls are incomplete. **H** is routinely reachable or likely during ordinary operations, **M** needs a plausible precondition and **L** needs unusual access or failure. Impact (I) is **C** for systemic compromise or unrecoverable loss, **H** for site-level compromise or major outage, and **M** for bounded leakage or disruption. Ratings are qualitative engineering judgments with medium confidence. Each row is a threat scenario and a proposed acceptance test. Story IDs are from the [roadmap](../08-roadmap.md).

### B1 · Client to WordPress

Core evidence anchors are `wordpress-develop-7.1.5/src/wp-includes/rest-api/endpoints/class-wp-rest-posts-controller.php:560–564`, `1396–1397`, `1447–1460` and `2056`, plus `wordpress-develop-7.1.5/src/wp-includes/capabilities.php:149`, `252` and `374`. R-003 observed unpatched `wp_insert_user()` return `1` after casting a UUID, and recorded rejection of the resulting metadata bind. The author-ownership effects are source-based inferences. `wordpress-develop-7.1.5/src/wp-includes/user.php:2575`. [R-003](../research/R-003-uuid-prototype.md#baseline-without-the-core-patch-verified).

| Type | Threat | L | I | PRD control | Gap | Proposed control | Verification | Story |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S | Stolen admin session or REST application password impersonates a user | M | H | HTTPS, secure cookies | Credential handling, revocation coverage | Test secure cookies, expiry and application-password revocation | Reuse revoked credentials through ingress and require denial | I-008 |
| T | User UUID supplied as a post/attachment UUID, or a parent UUID from the wrong domain | H | H | Typed UUID schemas and capability checks | UUID syntax alone does not identify the entity domain | Resolve expected entity and subtype at each boundary before any write | Seed the same UUID in two entity tables and use wrong table/subtype IDs | U-002, U-003 |
| R | Admin or client denies changing an object | M | M | Audit actor and correlation ID for sensitive changes | REST and admin mutation coverage unspecified | Audit security-sensitive requests with actor, typed target and outcome | Correlate a mutation and rejected retry across logs | D-004 |
| I | UUIDv7 timestamp exposes approximate mint time, and response differences expose private existence or ordering | H | M | Authoritative authorization | No timing/error-shape or public-surface policy | Authorize first, use consistent private-object errors, rate-limit probing and review which UUIDs are public | Compare missing and private ID responses and their latency distributions. Inventory publicly exposed IDs | U-002, O-003 |
| D | Expensive filters or repeated requests exhaust PHP workers or PostgreSQL | H | H | DB timeouts and circuit breakers | Per-route budgets and ingress rate limits unspecified | Bound page size, request rate and total query time | Flood bounded test routes and verify unrelated requests remain serviceable | O-003, O-007 |
| E | Silent integer casts merge identities or alter owner/capability decisions | H | H | UUID-only IDs and WordPress capabilities | Partial casts, sentinels and loose fallbacks | Carry exact strings through REST, authorization and storage and reject wrong types | Two authors/posts with the same integer prefix must get distinct read/edit/delete decisions | U-001, U-003, U-004 |

### B2 · Installer to production data

| Type | Threat | L | I | PRD control | Gap | Proposed control | Verification | Story |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S | Installer connects to a spoofed database or resumes against the wrong site | M | C | TLS verify-full, schema drift checks | Plan lacks strong target binding | Bind approval to verified host, DB identity and schema/checkpoint | Reject wrong CA, name and a valid but different target | S-002, M-001 |
| T | Corrupted crosswalk links a user/post reference to the wrong object | M | C | Typed crosswalk, migration verification | Crosswalk integrity and restart semantics | Per-entity mappings with uniqueness, checksums and reconciled references | Feed duplicate or type-swapped legacy keys and resume a partially applied fixture | X-002 |
| R | Operator denies approving destructive plan | M | H | Signed plans, event audit | Plan-to-execution attribution unspecified | Store approved digest, actor and checkpoint before write | Change one plan byte or omit approval and require pre-write rejection | M-001 |
| I | Crosswalk or migrator credential leaks via state/config/logs | M | C | Secret references and redaction | Retention and crosswalk access policy open | Separate encrypted mapping storage, restrict reads and prune after reconciliation window | Fixture crosswalk and secret markers absent from CLI output and runtime mounts | X-002, S-003 |
| D | Interrupted migration holds locks or leaves unusable state | M | H | Advisory lock, resumable state, checkpoints | Crash windows across DB and filesystem | Test stage checksums, lock timeout, atomic state update and verified recovery | Interrupt before and after commit and resume without duplicate mutation | I-005, O-001 |
| E | Runtime or agent acquires deploy-time role via credential reuse | M | C | Migrator/runtime separation | No demonstrated role membership and secret scope invariants | Short-lived deploy credentials and explicit role grant audit | Runtime attempts `SET ROLE`, DDL and credential access | S-001 |

### B3 · Runtime to PostgreSQL

| Type | Threat | L | I | PRD control | Gap | Proposed control | Verification | Story |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S | Proxy, DNS or CA misrouting impersonates PostgreSQL | M | H | TLS verify-full | PHP client configuration mismatch across entry points | Test PDO transport and refuse downgraded or wrong-host TLS | Invalid CA, wrong SAN and plaintext negatives | S-002 |
| T | SQL injection or unsupported rewrite changes predicate or update scope | H | C | Parameterized binds, typed AST and approved transforms | Prototype supports a narrow token rewrite set | Fail closed on unresolved semantics, bind values and test affected row sets | Differential corpus includes injection, wrong entity and dropped predicate cases | Q-001, Q-004 |
| R | Direct PDO query evades adapter audit | M | H | Adapter fingerprints and attribution | In-process logs can be bypassed | Reject unapproved direct DB APIs and independently record privileged DB actions | Fixture direct PDO is detected or attributed and assert log redaction | P-001, D-004 |
| I | Approved plugin reads site data or an SQL diagnostic exposes PII | H | H | Required grants and fingerprint logging | Same process and DB role share app access, and raw SQL can contain literals | Minimize grants, gate artifacts and redact independent diagnostics | Negative grant and sentinel log tests on synthetic rows | S-001, S-003 |
| D | Lock contention or expensive SQL exhausts connections | M | H | Timeouts and circuit breakers | Role and query budget enforcement unspecified | Set session/role budgets, read-only health check and bounded pool | Hold a lock and verify timeout, recovery and healthy traffic | D-001, O-003 |
| E | Runtime creates temp objects, alters schema or uses unsafe privileged functions | M | C | Runtime cannot run schema DDL | Ownership, TEMP, membership and function ACL may restore access | Revoke PUBLIC grants, use non-owner runtime, inventory elevated functions and schemas | Direct runtime CREATE, ALTER, DROP, TEMP, role-switch and function negatives | S-001 |

### B4 · Runtime to cache and uploads

| Type | Threat | L | I | PRD control | Gap | Proposed control | Verification | Story |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S | Wrong service spoofed as Redis/Valkey | M | H | Private authenticated TLS | Verifiable host binding and expiry handling | Pin service identity and fail closed or use safe request-local fallback | Present an invalid certificate and verify no credentials cross | S-002, C-002 |
| T | Cache poisoning via identical keys across entity kinds or sites | M | H | Namespaced cache | Namespace, invalidation and serialization rules need coverage | Key by site, group, entity type and whole UUID and validate cached shape | Seed equal UUIDs in distinct objects/sites, invalidate one and verify isolation | C-001, U-004 |
| R | Media changes lack attributable history | M | M | Correlated audit | Upload mutation events unspecified | Log actor and media UUID for sensitive mutations | Upload and delete in fixture, correlate both events | O-007 |
| I | Private media or cached authorization objects cross site boundaries | M | H | Private cache, secure runtime | Global cache groups and media access policy untested | Scope ACLs and test cache key groups and private media serving | Two principals attempt cache and upload access across sites | C-001, O-007 |
| D | Cache outage or uploads fill storage | H | H | Request-local cache fallback | Disk/eviction quotas and degraded load | Cap upload size and storage, exercise safe fallback under load | Full volume and Redis outage preserve login and error budgets | C-002, O-003 |
| E | Executable uploaded file reaches PHP handler | M | C | Read-only core, writable uploads and PHP execution blocked there | Web-server routing and alternate extensions differ | Serve media from a separate non-executing path with explicit routing | Upload a marker script and verify it never executes | S-004, O-007 |

### B5 · Plugin artifact to sandbox

Activation includes the plugin PHP file and fires its hook before recording it as active. `wordpress-develop-7.1.5/src/wp-admin/includes/plugin.php:677–720`, `wordpress-develop-7.1.5/src/wp-admin/includes/plugin.php:2382–2389`.

| Type | Threat | L | I | PRD control | Gap | Proposed control | Verification | Story |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S | Plugin slug/version impersonates a previously approved package | H | H | Artifact verification and manifest hash | No end-to-end digest binding specified at activation | Record origin, exact bytes, and runtime tuple, then recheck inside staging | Swap ZIP contents with unchanged metadata and require denial | P-002, P-004 |
| T | Activation writes core files or corrupts synthetic DB rows | H | H | Sandbox and sealed releases | In-process scanner cannot prevent effects | Read-only core, tmpfs scratch, independent integrity checks and separate reviewed migrations | Core write and unsafe metadata fixtures, then inspect state outside worker | P-003, S-004 |
| R | Plugin suppresses or manufactures sandbox evidence | M | H | Evidence reports | Same-process traces are mutable and incomplete | Independently collect exit, DB evidence and network events and block incomplete reports | Fixture exits early or tampers with in-process logs and is not promoted | P-003 |
| I | Activation egress or environment reads leak data | H | C | Egress restriction and no production credentials | Runtime credentials still visible to code in its process | Use synthetic data, explicit env allowlist and isolated network with positive/negative tests | Raw HTTP fixture, secret markers and DB runtime login check | P-003, S-003 |
| D | Activation loops, consumes memory or creates process fan-out | H | H | Disposable sandbox | Per-container resource budgets and cleanup need proof | CPU, memory, PID and wall deadlines and reap worker before reuse | Infinite loop, memory exhaustion and process-limit fixtures | P-003 |
| E | Plugin calls DDL at activation or escapes shared-kernel worker | M | C | Gated plugin migrations, small runtime role | Docker alone shares the kernel, leaving the host and DB in need of independent isolation | Separate migrator, deny runtime DDL, run arbitrary external artifacts in stronger isolation | Direct PG runtime denial and isolated-worker policy checks | P-003, S-001 |

### B6 · External dependencies and CI to signed release

WordPress selects the Gutenberg OCI build by SHA and verifies blob metadata relative to the fetched manifest. Pin the expected manifest independently. `wordpress-develop-7.1.5/package.json:9–12`, `wordpress-develop-7.1.5/tools/gutenberg/download.js:113–183`, `gutenberg-89408c2/.github/workflows/build-plugin-zip.yml:300–363`. [R-005 patch and lock verification](../research/R-005-patch-mechanism-and-licensing.md#2-proof-of-concept-toolspatchset).

| Type | Threat | L | I | PRD control | Gap | Proposed control | Verification | Story |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S | Moved upstream WordPress/Gutenberg tag or substituted OCI artifact | M | C | Pinned versions and hashes | Tag selection and digest trust root need independent approval | Lock upstream refs, artifact digests and trusted source and fail closed | Move tag or substitute OCI blob and test refusal | I-004, U-005 |
| T | Patch order, Composer/npm dependencies or Docker image changed after review | H | C | Artifact hashes, reproducible release | Transitive scripts/base images and reviewed bytes can drift | Verify patch pre/post-images, lock dependencies and image digests, and isolate build scripts from signer | Tamper with each input class and require CI rejection | U-005, O-005 |
| R | CI produces a release with no traceable builder or inputs | M | H | Signed release and SBOM | Digest-to-workflow evidence unspecified | Publish provenance tied to job, tests, input digests and signer identity | Verify attestation and reject missing or mismatched provenance | O-005 |
| I | Untrusted build script steals signing or package tokens | M | C | Human signs release, restricted secrets | Build and sign workflow trust separation needs enforcement | Build with read-only token and reserve a protected short-lived signing identity for release | Untrusted build job cannot read or mint signing credentials | I-007, O-005 |
| D | Broken or vulnerable upstream release stalls security updates | H | H | Patch workflow and release policy | Solo maintainer availability and rebase conflicts | Automate rebase checks and severity triage and rehearse frozen release/rollback | Exercise clean and conflicted update paths and last-good recovery | U-005, O-001, O-006 |
| E | Pull request job gains signing/deploy permissions or can replace verified bytes | M | C | Review gates and signed releases | Enforced exact-digest promotion unspecified | Use a protected release environment, verify test provenance and publish the same digest | Untrusted PR cannot invoke signer, and post-test mutation invalidates release | I-007, O-005 |

### B7 · Production to backup and diagnostics

| Type | Threat | L | I | PRD control | Gap | Proposed control | Verification | Story |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S | Backup or restore job targets an impostor site/storage endpoint | M | C | Separate backup/restore credentials | Target and snapshot identity binding unspecified | Bind manifest to site, media set and restore target and verify TLS and identity | Reject mismatched manifest before restore writes | B-001 |
| T | Backup modified or DB and media snapshots disagree | M | C | Consistent manifest and isolated restore tests | Integrity and off-site immutability enforcement | Signed manifest with hashes and retention lock, then test referential consistency | Alter backup segment or remove referenced media and fail restore test | O-002 |
| R | Restore or support export leaves no durable trail | M | H | Audit correlations | Separate retention and access logs open | Record actor, target/snapshot IDs and outcomes in write-restricted audit | Verify failed/successful restore events and restricted access | O-002, O-008 |
| I | Support bundle or backup contains private data, crosswalk or passwords | H | C | Redaction, off-site encryption | Raw adapter logs and serialized data can evade field rules | Default to fingerprint-only SQL, redact by allowlist, limit retention and encrypt | Scan support fixture for seeded credentials and PII | S-003, O-008 |
| D | Backups unusable or unavailable during an incident | M | C | Periodic backups and restore rehearsal | Actual RPO/RTO and isolation depend on deployment | Schedule restore validation and alert on stale/rejected backups | Restore latest set in isolation and measure data loss window and time | B-001, O-002 |
| E | Backup credential can mutate production or remove all copies | M | C | Least-privileged backup role | Physical vs logical privilege model open | Separate read/replication rights, append-only backup target and restore authority | Attempt write, role escalation and retention deletion with backup identity | B-001, S-001 |

### B8 · Agent to execution and approval

| Type | Threat | L | I | PRD control | Gap | Proposed control | Verification | Story |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S | Agent output or CI status impersonates human approval | M | C | Human/codeowner review | Approval may be recorded only in mutable text | Gate via authenticated protected workflow tied to digest | Bot approval or stale review cannot promote | I-007 |
| T | Prompt injection in ZIP, logs or issues steers edits to manifest or migrations | H | H | Bounded agent roles and reviewed changes | Artifact-derived text reaches agent context | Treat content as data, scope tools to disposable workspace, require protected review | Seed fake instructions inside plugin metadata and verify no policy or plan change | I-007, P-002 |
| R | Automation mutates state without actor or tool attribution | M | H | Auditable changes | No operational event contract for automated actions | Record bot identity, plan digest, tool and approval, with secrets removed | Correlate rejected and accepted dry runs | I-007, D-004 |
| I | Tool invocation or diagnostics puts secrets into agent context | M | C | No autonomous access to production secrets | Environment and artifact segregation need enforcement | Separate worker identities, no production token mounts, redact tool inputs/outputs | Canary secret search in tool transcripts and bundle artifacts | S-003, O-008 |
| D | Repeated automation consumes runners or races a deployment | M | H | Advisory locks and bounded responsibilities | CI concurrency and retries unspecified | Concurrency groups, short budgets and idempotent no-op on stale plan | Parallel requests make one deployment decision and retries terminate | I-005, O-003 |
| E | Agent autonomously activates unknown plugin, migrates live data or signs release | M | C | Prohibited actions and review gates | Policy prose alone cannot enforce tool permissions | Disjoint roles and protected promotion, with bots limited to disposable execution | Tool/CI policy rejects activation, signing and live writes without protected approval | I-007, P-004, O-005 |

## Top 10 risks

The order prioritizes systemic authority and data loss, then directly reachable integrity or disclosure risks. Ties are qualitative judgments for a one-person team.

| Rank | Risk | Boundary | First acceptance gate |
| --- | --- | --- | --- |
| 1 | Compromised build/release or signer publishes substituted code | B6 | Exact-digest release and independent protected signing (I-004, U-005, O-005) |
| 2 | Untrusted activation reaches real data or credentials | B5, B3 | Isolated run and approval bound to tested bytes (P-003, P-004) |
| 3 | Silent UUID cast or entity confusion changes object authorization | B1, B4 | Non-admin owner and cross-entity negatives (U-001–U-004) |
| 4 | Runtime or agent gets migrator privileges | B2, B3, B8 | Scoped roles and protected approval (S-001, I-007) |
| 5 | Bad migration corrupts typed references or loses data | B2, B7 | Crosswalk reconciliation and tested restore (X-002, B-001) |
| 6 | SQL rewrite silently drops a filter or changes a write target | B3 | AST allowlist and affected-row differential corpus (Q-001, Q-004) |
| 7 | Sandbox escape or egress reaches host resources | B5 | Stronger disposable worker for external artifacts (P-003) |
| 8 | Backups or diagnostics disclose private data and keys | B7, B8 | Redaction, private retention and seeded secret tests (S-003, O-008) |
| 9 | Upstream patch conflicts delay an urgent security release | B6 | Automated detection and tested rollback (U-005, O-001, O-006) |
| 10 | Timestamp and response differences expose private object metadata | B1 | Private-object denial and enumeration tests (U-002, O-003) |

## Minimum viable security for a solo maintainer

- **Automate each change.** One CI workflow should verify upstream and dependency pins, strict patch application, actor permissions, the UUID authorization corpus, sandbox negatives and that the promoted digest equals the tested digest. Run broader WordPress PHPUnit on release candidates and track the comparable result using [R-009](../research/R-009-core-phpunit-baseline.md).
- **Automate deployment preflight.** Require DB role/ownership and TLS checks, immutable artifacts, hardened uploads, a signed plan and a verified restore checkpoint before migrations. Restrict CLI, FPM, backup and signer credentials to their own entry points. Make diagnostics fingerprint-based by default. [Security PRD](../06-security-operations.md).
- **Schedule maintenance.** Run backup validation and isolated restore on a schedule. Alert on failed/stale results, dependency advisories, unsupported releases and rebase conflicts. Keep the tested plugin catalog small and match approvals to exact versions. [Roadmap](../08-roadmap.md).
- **Keep the human decisions explicit.** The maintainer reviews privilege/schema changes, new plugin/adapters, failed restore drills, rebase conflicts, incident decisions and the exact digest before release. Accounts or environments should enforce separation from bot authority even with one maintainer. Independent second-person review needs an external reviewer. Leave the affected release or migration gated where the repository requires that approval and nobody can supply it. [Agent review rules](../10-ai-agents.md), [R-005 update workflow](../research/R-005-patch-mechanism-and-licensing.md#14-security-releases-and-a-proposed-sla-compatible-workflow).
