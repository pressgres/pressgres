#!/usr/bin/env bash
# R-003 prototype driver. Usage: ./run.sh [all|prepare|up|setup|demo|summary|down]
# `all` = down -> prepare -> up -> setup -> demo -> summary (keeps the stack up;
# run `./run.sh down` afterwards).
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"

WP_SRC="${WP_SRC:-$HERE/../../../../reference/wordpress-develop-7.1.5/src}"
BUILD="$HERE/build"
PATCH_DIR="$HERE/patches"
COMPOSE=(docker compose -p pressgres-r003 -f "$HERE/docker-compose.yml")

prepare() {
  [[ -f "$WP_SRC/wp-includes/version.php" ]] || { echo "WordPress src not found at $WP_SRC (set WP_SRC)"; exit 1; }
  grep -q "wp_version = '7.1.5" "$WP_SRC/wp-includes/version.php" || { echo "expected WordPress 7.1.5 in $WP_SRC"; exit 1; }
  rm -rf "$BUILD/wordpress"
  mkdir -p "$BUILD/logs"
  rm -f "$BUILD"/logs/*.jsonl "$BUILD"/logs/*.log "$BUILD/state.json" "$BUILD/php-post-id.txt"
  cp -R "$WP_SRC" "$BUILD/wordpress"
  # wordpress-develop's src/index.php only nags about unbuilt JS/CSS; the
  # build normally replaces it with _index.php. Do the same (not a core patch).
  cp "$BUILD/wordpress/_index.php" "$BUILD/wordpress/index.php"
  if [[ "${R003_NO_PATCH:-0}" == "1" ]]; then
    echo "R003_NO_PATCH=1: NOT applying core patches (baseline run)"
  fi
  for p in "$PATCH_DIR"/*.patch; do
    [[ "${R003_NO_PATCH:-0}" == "1" ]] && break
    [[ -s "$p" ]] || continue
    echo "applying $(basename "$p")"
    patch -p1 --forward --no-backup-if-mismatch -d "$BUILD/wordpress" < "$p"
  done
  cp "$HERE/wordpress/db.php" "$BUILD/wordpress/wp-content/db.php"
  cp "$HERE/wordpress/wp-config.php" "$BUILD/wordpress/wp-config.php"
  echo "prepared $BUILD/wordpress"
}

up() {
  "${COMPOSE[@]}" build
  "${COMPOSE[@]}" up -d --wait db web
  "${COMPOSE[@]}" exec -T db psql -U pressgres -d pressgres -Atc "SELECT version(), uuid_extract_version(uuidv7())"
}

php_run() { "${COMPOSE[@]}" run --rm -T -e PRESSGRES_PHASE="$1" php "${@:2}"; }

setup() { php_run setup scripts/setup.php || { echo "setup failed (see build/logs/wp-debug.log)"; return 1; }; }

demo() {
  local rc=0
  php_run php-api scripts/demo-php.php || rc=1
  php_run rest-client scripts/demo-rest.php || rc=1
  return $rc
}

summary() { php_run summary scripts/query-log-summary.php /r003/build/logs/query-log.jsonl; }

down() { "${COMPOSE[@]}" --profile tools down -v --remove-orphans; }

# Developer loop: regenerate patches/ from edits made directly in build/wordpress.
mkpatch() {
  if [[ ! -d "$BUILD/wordpress-pristine" ]]; then
    cp -R "$WP_SRC" "$BUILD/wordpress-pristine"
    cp "$BUILD/wordpress-pristine/_index.php" "$BUILD/wordpress-pristine/index.php"
  fi
  (cd "$BUILD" && diff -ruN -x wp-config.php -x db.php -x '*.orig' wordpress-pristine wordpress \
     | perl -pe 's#^((?:---|\+\+\+) \S+)\t.*#$1#;' | grep -v '^diff -ruN') \
     > "$PATCH_DIR/wordpress-7.1.5-r003-uuid.patch" || true
  grep -c '^+++ ' "$PATCH_DIR/wordpress-7.1.5-r003-uuid.patch" | xargs echo "files in patch:"
}

case "${1:-all}" in
  prepare) prepare ;;
  up) up ;;
  setup) setup ;;
  demo) demo ;;
  summary) summary ;;
  down) down ;;
  mkpatch) mkpatch ;;
  iterate)  # fresh DB, keep build/wordpress as edited
    down; mkdir -p "$BUILD/logs"; rm -f "$BUILD"/logs/*.jsonl "$BUILD"/logs/*.log; up; setup
    rc=0; demo || rc=$?; summary; exit $rc ;;
  all)
    down; prepare; up
    rc=0; setup || rc=$?
    [[ $rc -eq 0 ]] && { demo || rc=$?; }
    summary
    exit $rc
    ;;
  *) echo "usage: $0 [all|prepare|up|setup|demo|summary|down]"; exit 2 ;;
esac
