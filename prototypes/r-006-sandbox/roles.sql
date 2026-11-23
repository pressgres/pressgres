\getenv runtime_password R006_RUNTIME_BOOTSTRAP_PASSWORD

CREATE ROLE sandbox_migrator NOLOGIN;
CREATE ROLE sandbox_runtime LOGIN PASSWORD :'runtime_password'
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;
REVOKE ALL ON DATABASE sandbox FROM PUBLIC;
GRANT CONNECT ON DATABASE sandbox TO sandbox_runtime;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
ALTER SCHEMA public OWNER TO sandbox_migrator;
GRANT USAGE ON SCHEMA public TO sandbox_runtime;
ALTER ROLE sandbox_runtime SET statement_timeout = '2s';
ALTER ROLE sandbox_runtime SET lock_timeout = '1s';

SET ROLE sandbox_migrator;
