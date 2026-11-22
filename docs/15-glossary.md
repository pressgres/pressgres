# 15 — Glossary

- **Drop-in**: early-load WordPress file such as `wp-content/db.php` or `object-cache.php`.
- **Managed core patchset**: version-specific, checksum-verified changes to upstream WordPress necessary for UUID-safe behavior.
- **UUIDv7**: time-ordered UUID version supported by PostgreSQL 18 native `uuidv7()`.
- **AST**: abstract syntax tree for safely transforming recognized SQL syntax.
- **Adapter**: reviewed, version-specific rules/tests for a plugin's SQL or PHP behavior.
- **Manifest**: machine-readable compatibility facts, test evidence, versions and approvals.
- **Crosswalk**: explicit mapping from source integer IDs to target UUID IDs during migration.
- **Dry run**: execution against a disposable environment, never silently against production.
- **DDL**: schema changing commands (`CREATE`, `ALTER`, `DROP`).
- **DML**: data changing/reading commands (`INSERT`, `UPDATE`, `DELETE`, `SELECT`).
- **Release lockfile**: pinned WordPress, patchset, PHP, PG, Redis and adapter artifacts/hashes.
- **Fail closed**: reject uncertain, unsupported or unsafe operations rather than guessing.
