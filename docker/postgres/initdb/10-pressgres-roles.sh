#!/bin/sh
# Pressgres development role layout (ADR-0011, docs/06-security-operations.md).
#
#   wps_owner     NOLOGIN; owns the database's public schema and every object in it.
#   wps_migrator  LOGIN; may SET ROLE wps_owner to apply migrations (deploy/install time only).
#   wps_runtime   LOGIN; CONNECT + schema USAGE + table DML via default privileges.
#                 No CREATE on the schema and no TEMPORARY on the database, so any DDL
#                 fails with SQLSTATE 42501.
#
# Runs once, on first start of an empty data volume (docker-entrypoint-initdb.d).
# Passwords come from the container environment (.env); nothing is committed.
set -eu

: "${WPS_MIGRATOR_PASSWORD:?WPS_MIGRATOR_PASSWORD must be set (see .env.example)}"
: "${WPS_RUNTIME_PASSWORD:?WPS_RUNTIME_PASSWORD must be set (see .env.example)}"

psql -v ON_ERROR_STOP=1 --no-psqlrc \
    --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
    -v db="$POSTGRES_DB" \
    -v migrator_password="$WPS_MIGRATOR_PASSWORD" \
    -v runtime_password="$WPS_RUNTIME_PASSWORD" <<'SQL'
CREATE ROLE wps_owner NOLOGIN
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;

CREATE ROLE wps_migrator LOGIN PASSWORD :'migrator_password'
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
GRANT wps_owner TO wps_migrator WITH INHERIT TRUE, SET TRUE;

CREATE ROLE wps_runtime LOGIN PASSWORD :'runtime_password'
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;
ALTER ROLE wps_runtime SET statement_timeout = '30s';
ALTER ROLE wps_runtime SET lock_timeout = '5s';

-- Database: nobody but the named roles connects; nobody gets TEMPORARY by default.
REVOKE ALL ON DATABASE :"db" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"db" TO wps_runtime, wps_migrator;
GRANT TEMPORARY ON DATABASE :"db" TO wps_migrator;

-- Schema: owned by the NOLOGIN owner; runtime only gets USAGE.
ALTER SCHEMA public OWNER TO wps_owner;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO wps_runtime;

-- Objects the owner creates later are usable (DML only) by the runtime.
ALTER DEFAULT PRIVILEGES FOR ROLE wps_owner IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO wps_runtime;
ALTER DEFAULT PRIVILEGES FOR ROLE wps_owner IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO wps_runtime;
ALTER DEFAULT PRIVILEGES FOR ROLE wps_owner IN SCHEMA public
  GRANT EXECUTE ON FUNCTIONS TO wps_runtime;
ALTER DEFAULT PRIVILEGES FOR ROLE wps_owner REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
SQL
