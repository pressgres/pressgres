#!/usr/bin/env bash
# R-009 harness: run the wordpress-develop 7.1.5 PHPUnit suite against
# MySQL (control) or PostgreSQL (Pressgres prototype) in disposable containers.
#
# Usage:
#   run.sh build                         Build the pinned runner image.
#   run.sh prepare                       Fresh copy of the reference tree into the wpdev volume.
#   run.sh test <mysql|pgsql> <label> [phpunit args...]
#                                        Start the DB, run PHPUnit, write results/<label>/.
#   run.sh shell                         Interactive shell in the runner.
#   run.sh down                          Stop everything and delete volumes.
#
# Environment:
#   WP_DEVELOP_REF   path to wordpress-develop-7.1.5 (default: ../../../../reference/wordpress-develop-7.1.5)
#   PG_PROTOTYPE_DIR directory containing the Pressgres db.php prototype (pgsql only)
#   R009_PG_SHIM     1 (default: wrap prototype with config/r009-db-wrapper.php) | 0
#   R009_PG_SCHEMA   prototype (default: pre-create prototype sql/01-schema.sql) | none
#   PRESSGRES_QUERY_LOG  query log path inside the runner (default results/<label>/pressgres-query-log.jsonl)
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

: "${WP_DEVELOP_REF:=$(cd "$HERE/../../../.." && pwd)/reference/wordpress-develop-7.1.5}"
export WP_DEVELOP_REF
: "${PG_PROTOTYPE_DIR:=$HERE/config/empty}"
export PG_PROTOTYPE_DIR
mkdir -p "$HERE/config/empty" "$HERE/results"

compose() { docker compose -f "$HERE/compose.yaml" "$@"; }
RUN_OPTS=()
runner() { compose --profile runner run --rm -T ${RUN_OPTS[@]+"${RUN_OPTS[@]}"} runner "$@"; }

cmd="${1:-}"; shift || true

case "$cmd" in
  build)
    compose --profile runner build runner
    ;;

  prepare)
    [ -f "$WP_DEVELOP_REF/phpunit.xml.dist" ] || { echo "WP_DEVELOP_REF does not look like wordpress-develop: $WP_DEVELOP_REF" >&2; exit 1; }
    runner bash -ceu '
      rsync -a --no-owner --no-group --delete --exclude node_modules --exclude vendor --exclude .git /reference/ /srv/wordpress-develop/
      cp /harness/wp-tests-config.php /srv/wordpress-develop/wp-tests-config.php
      mkdir -p /srv/wordpress-develop/tests/phpunit/build/logs
      echo "prepared: $(find /srv/wordpress-develop/tests/phpunit/tests -name "*.php" | wc -l) test files"
    '
    ;;

  test)
    driver="${1:?driver mysql|pgsql}"; label="${2:?label}"; shift 2
    case "$driver" in
      mysql) svc=mysql ;;
      pgsql) svc=postgres ;;
      *) echo "unknown driver $driver" >&2; exit 2 ;;
    esac
    compose up -d --wait "$svc"
    out="$HERE/results/$label"; rm -rf "$out"; mkdir -p "$out"
    # Record versions for the report.
    {
      echo "label=$label"
      echo "driver=$driver"
      echo "started_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
      echo "phpunit_args=$*"
      [ "$driver" = pgsql ] && echo "pg_shim=${R009_PG_SHIM:-1} pg_schema=${R009_PG_SCHEMA:-prototype} prototype_dir=$PG_PROTOTYPE_DIR"
      if [ "$driver" = mysql ]; then
        echo "db_version=$(compose exec -T mysql mysql -uroot -proot -N -e 'SELECT VERSION()' 2>/dev/null)"
      else
        echo "db_version=$(compose exec -T postgres psql -U wptests -d wordpress_tests -Atc 'SHOW server_version')"
      fi
    } > "$out/meta.env"
    start=$(date +%s)
    set +e
    RUN_OPTS=(-e R009_DB_DRIVER="$driver" -e R009_LABEL="$label" -e R009_PG_SCHEMA="${R009_PG_SCHEMA:-prototype}"
      -e R009_PG_SHIM="${R009_PG_SHIM:-1}" -e R009_SHIM_LOG="/results/$label/r009-shim.log"
      -e PRESSGRES_PHASE=phpunit
      -e PRESSGRES_QUERY_LOG="${PRESSGRES_QUERY_LOG:-/results/$label/pressgres-query-log.jsonl}")
    runner bash -c '
      set -u
      cd /srv/wordpress-develop
      if [ "$R009_DB_DRIVER" = pgsql ]; then
        rm -f /srv/wordpress-develop/src/wp-content/db.php
        if [ -x /harness/pg-wire.sh ]; then /harness/pg-wire.sh; elif [ -f /prototype/db.php ]; then cp /prototype/db.php /srv/wordpress-develop/src/wp-content/db.php; fi
      else
        rm -f /srv/wordpress-develop/src/wp-content/db.php
      fi
      php -v | head -1 > /results/$R009_LABEL/php-version.txt
      phpunit --version >> /results/$R009_LABEL/php-version.txt
      phpunit -c phpunit.xml.dist --log-junit /results/$R009_LABEL/junit.xml --colors=never "$@" \
        > /results/$R009_LABEL/phpunit.log 2>&1
      echo $? > /results/$R009_LABEL/exit-code
    ' bash "$@"
    set -e
    end=$(date +%s)
    echo "duration_seconds=$((end - start))" >> "$out/meta.env"
    echo "exit_code=$(cat "$out/exit-code" 2>/dev/null || echo none)" >> "$out/meta.env"
    tail -n 15 "$out/phpunit.log" || true
    if [ -f "$out/junit.xml" ]; then python3 "$HERE/summarize.py" "$out/junit.xml" --label "$label" | head -n 5; fi
    ;;

  shell)
    compose --profile runner run --rm runner bash
    ;;

  down)
    compose --profile runner down -v --remove-orphans
    ;;

  *)
    sed -n '2,18p' "$0"; exit 2 ;;
esac
