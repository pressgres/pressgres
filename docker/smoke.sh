#!/usr/bin/env bash
# Pressgres local-stack smoke test (I-006, ADR-0005).
#
# Starts the root compose.yaml stack under its own project name with throwaway
# secrets, runs docker/smoke/check.php inside the php service, and always tears
# the stack down again (containers, network and volumes).
#
#   docker/smoke.sh                  # build, check, tear down
#   KEEP_STACK=1 docker/smoke.sh     # leave the stack running for debugging
#   PG_IMAGE=postgres:19.0-alpine3.24@sha256:... docker/smoke.sh
#                                    # exploratory server image (CI matrix, I-011)
#
# A local .env is ignored; your dev stack (project pressgres-dev) is untouched.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

project="${SMOKE_PROJECT:-pressgres-smoke}"
env_file="$(mktemp "${TMPDIR:-/tmp}/pressgres-smoke-env.XXXXXX")"

secret() { od -An -N24 -tx1 /dev/urandom | tr -d ' \n'; }

cat >"$env_file" <<EOF
COMPOSE_PROJECT_NAME=$project
PG_SUPERUSER=postgres
PG_SUPERUSER_PASSWORD=$(secret)
PG_DATABASE=pressgres
WPS_MIGRATOR_PASSWORD=$(secret)
WPS_RUNTIME_PASSWORD=$(secret)
VALKEY_PASSWORD=$(secret)
PG_HOST_PORT=
VALKEY_HOST_PORT=
MAILPIT_UI_PORT=
EOF
chmod 600 "$env_file"

compose() { docker compose --project-name "$project" --env-file "$env_file" "$@"; }

teardown() {
  status=$?
  if [[ $status -ne 0 ]]; then
    echo "--- service logs (failure) ---" >&2
    compose logs --no-color --tail 50 >&2 || true
  fi
  if [[ "${KEEP_STACK:-0}" == "1" ]]; then
    echo "KEEP_STACK=1: leaving project $project running (env file: $env_file)" >&2
  else
    compose down -v --remove-orphans >/dev/null 2>&1 || true
    rm -f "$env_file"
  fi
  exit "$status"
}
trap teardown EXIT

echo "== versions"
docker version --format 'docker {{.Server.Version}}'
docker compose version

if [[ -n "${PG_IMAGE:-}" ]]; then
  echo "== PG_IMAGE override (exploratory, not a supported version): $PG_IMAGE"
fi

echo "== build and start ($project)"
compose up -d --build --wait --wait-timeout 180

compose exec -T postgres postgres --version
compose exec -T valkey valkey-server --version
compose exec -T php php -v | head -n 1

echo "== checks"
migrator_password="$(grep '^WPS_MIGRATOR_PASSWORD=' "$env_file" | cut -d= -f2-)"
compose exec -T \
  -e PG_MIGRATOR_USER=wps_migrator \
  -e PG_MIGRATOR_PASSWORD="$migrator_password" \
  php php /srv/pressgres/docker/smoke/check.php

echo "== smoke OK"
