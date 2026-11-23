<?php
/**
 * R-009 harness wrapper around a Pressgres db.php prototype.
 *
 * TEST-HARNESS CODE ONLY. It does not translate application SQL. It neutralizes
 * the handful of statements that the wordpress-develop PHPUnit infrastructure
 * itself issues and that a SELECT/INSERT/UPDATE/DELETE-only prototype adapter
 * rejects, so that the suite can reach the tests at all:
 *
 *  - `SET autocommit = 0;`, `SET default_storage_engine = InnoDB`,
 *    `SET foreign_key_checks = N` (abstract-testcase.php:496, install.php)
 *    -> no-op.
 *  - `SHOW TABLES` (utils.php:545) -> SELECT from pg_tables.
 *  - While tests/phpunit/includes/install.php runs (WP_INSTALLING): DROP TABLE,
 *    CREATE TABLE, ALTER TABLE, DESCRIBE, SHOW ... issued by install.php and
 *    dbDelta() -> no-op, because the harness pre-creates the prototype schema
 *    (config/pg-wire.sh). Outside install, DDL reaches the prototype unchanged.
 *
 * Every neutralized statement is appended to R009_SHIM_LOG (one line each) so
 * the report can count what was hidden.
 *
 * The prototype file is loaded unmodified from pressgres-prototype-db.php and
 * constructs its own $wpdb; this wrapper replaces it with a subclass instance.
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

require __DIR__ . '/pressgres-prototype-db.php';

$r009_parent = get_class( $GLOBALS['wpdb'] );
if ( method_exists( $GLOBALS['wpdb'], 'close' ) ) {
	$GLOBALS['wpdb']->close();
}

// The prototype class name is not known statically; alias it for extension.
class_alias( $r009_parent, 'R009_Prototype_Base_wpdb' );

class R009_Harness_wpdb extends R009_Prototype_Base_wpdb {

	private function r009_shim_log( $kind, $query ) {
		$file = getenv( 'R009_SHIM_LOG' );
		if ( $file ) {
			@file_put_contents( $file, $kind . "\t" . ( defined( 'WP_INSTALLING' ) ? 'install' : 'tests' ) . "\t" . preg_replace( '/\s+/', ' ', substr( $query, 0, 160 ) ) . "\n", FILE_APPEND | LOCK_EX );
		}
	}

	private static function r009_in_test_installer() {
		$script = isset( $_SERVER['SCRIPT_FILENAME'] ) ? (string) $_SERVER['SCRIPT_FILENAME'] : '';
		return str_ends_with( $script, 'tests/phpunit/includes/install.php' );
	}

	public function query( $query ) {
		$q = ltrim( (string) $query );

		if ( preg_match( '/^SET\s+(autocommit|default_storage_engine|storage_engine|foreign_key_checks)\b/i', $q ) ) {
			$this->r009_shim_log( 'noop-set', $q );
			$this->last_query = $query;
			return true;
		}

		if ( preg_match( '/^SHOW\s+TABLES\s*;?\s*$/i', $q ) ) {
			$this->r009_shim_log( 'show-tables', $q );
			return parent::query( 'SELECT tablename FROM pg_tables WHERE schemaname = current_schema()' );
		}

		if ( defined( 'WP_INSTALLING' ) && WP_INSTALLING && self::r009_in_test_installer()
			&& preg_match( '/^(DROP\s+TABLE|CREATE\s+TABLE|ALTER\s+TABLE|DESCRIBE|SHOW)\b/i', $q ) ) {
			$this->r009_shim_log( 'install-ddl-noop', $q );
			$this->last_query  = $query;
			$this->last_result = array();
			$this->num_rows    = 0;
			return true;
		}

		return parent::query( $query );
	}
}

// phpcs:ignore WordPress.WP.GlobalVariablesOverride.Prohibited
$wpdb = new R009_Harness_wpdb( DB_USER, DB_PASSWORD, DB_NAME, DB_HOST );
