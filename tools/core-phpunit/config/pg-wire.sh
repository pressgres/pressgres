#!/usr/bin/env bash
# Wires a Pressgres db.php prototype into the wordpress-develop tree for a
# PostgreSQL run. Runs inside the runner container (see run.sh test pgsql).
#
# R009_PG_SCHEMA=prototype (default): reset the database and pre-create the
#   prototype's schema (prototype sql/01-schema.sql) with the test prefix
#   `wptests_` substituted for `wp_`, because the prototype adapter does not
#   execute DDL and the test installer (tests/phpunit/includes/install.php)
#   creates tables through dbDelta().
# R009_PG_SHIM=1 (default): wrap the prototype with config/r009-db-wrapper.php;
#   0: install the prototype db.php verbatim.
# R009_PG_SCHEMA=none: reset the database only; the suite's own installer must
#   create everything (measures the stock bootstrap path).
set -euo pipefail

WP=/srv/wordpress-develop
PROTO=/prototype
MODE="${R009_PG_SCHEMA:-prototype}"
export PGPASSWORD="${R009_DB_PASSWORD:-wptests}"
PSQL=(psql -h "${R009_DB_HOST:-postgres}" -U "${R009_DB_USER:-wptests}" -d "${R009_DB_NAME:-wordpress_tests}" -v ON_ERROR_STOP=1 -q)

# Locate the drop-in.
src=""
for c in "$PROTO/db.php" "$PROTO/wordpress/db.php" "$PROTO/wp-content/db.php"; do
  [ -f "$c" ] && { src="$c"; break; }
done
[ -n "$src" ] || { echo "pg-wire: no db.php found under $PROTO" >&2; exit 1; }
if [ "${R009_PG_SHIM:-1}" = 1 ]; then
  # Harness wrapper (config/r009-db-wrapper.php) loads the unmodified prototype.
  cp "$src" "$WP/src/wp-content/pressgres-prototype-db.php"
  cp /harness/r009-db-wrapper.php "$WP/src/wp-content/db.php"
  echo "pg-wire: installed $src (sha256 $(sha256sum "$src" | cut -c1-16)) behind r009-db-wrapper.php"
else
  rm -f "$WP/src/wp-content/pressgres-prototype-db.php"
  cp "$src" "$WP/src/wp-content/db.php"
  echo "pg-wire: installed $src (sha256 $(sha256sum "$src" | cut -c1-16)) as db.php (no harness shim)"
fi

# Prototype core patches, if any (applied to the disposable copy only).
if [ -d "$PROTO/patches" ]; then
  for p in "$PROTO"/patches/*.patch; do
    [ -s "$p" ] || continue
    echo "pg-wire: applying $(basename "$p")"
    patch -p1 --forward --no-backup-if-mismatch -d "$WP/src" < "$p" || echo "pg-wire: patch $(basename "$p") did not apply cleanly"
  done
fi

"${PSQL[@]}" -c 'DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;'
"${PSQL[@]}" -Atc "SELECT 'pg-wire: ' || version() || ' uuidv7 version=' || uuid_extract_version(uuidv7())"

if [ "$MODE" = prototype ] && [ -f "$PROTO/sql/01-schema.sql" ]; then
  sed -E 's/\bwp_/wptests_/g' "$PROTO/sql/01-schema.sql" | "${PSQL[@]}"
  echo "pg-wire: pre-created prototype schema: $("${PSQL[@]}" -Atc "SELECT string_agg(tablename, ' ' ORDER BY tablename) FROM pg_tables WHERE schemaname='public'")"
fi
