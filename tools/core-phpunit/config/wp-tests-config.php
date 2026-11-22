<?php
/**
 * R-009 wp-tests-config.php (harness-owned, not upstream).
 *
 * Mirrors wordpress-develop-7.1.5/wp-tests-config-sample.php with values taken
 * from the environment so the same file serves the MySQL control and the
 * PostgreSQL prototype runs. run.sh copies it to /srv/wordpress-develop/wp-tests-config.php.
 */

define( 'ABSPATH', __DIR__ . '/src/' );
define( 'WP_DEFAULT_THEME', 'default' );
define( 'WP_DEBUG', true );

$r009_driver = getenv( 'R009_DB_DRIVER' ) ?: 'mysql';

define( 'DB_NAME', getenv( 'R009_DB_NAME' ) ?: 'wordpress_tests' );
define( 'DB_USER', getenv( 'R009_DB_USER' ) ?: 'wptests' );
define( 'DB_PASSWORD', getenv( 'R009_DB_PASSWORD' ) ?: 'wptests' );
define( 'DB_HOST', getenv( 'R009_DB_HOST' ) ?: ( 'pgsql' === $r009_driver ? 'postgres' : 'mysql' ) );
define( 'DB_CHARSET', 'utf8mb4' );
define( 'DB_COLLATE', '' );

if ( 'pgsql' === $r009_driver ) {
	// Hints for Pressgres prototype drop-ins; ignored by stock wpdb.
	define( 'PRESSGRES_DB_DRIVER', 'pgsql' );
	define( 'DB_PORT', getenv( 'R009_DB_PORT' ) ?: '5432' );
}

define( 'AUTH_KEY', 'r009-auth-key' );
define( 'SECURE_AUTH_KEY', 'r009-secure-auth-key' );
define( 'LOGGED_IN_KEY', 'r009-logged-in-key' );
define( 'NONCE_KEY', 'r009-nonce-key' );
define( 'AUTH_SALT', 'r009-auth-salt' );
define( 'SECURE_AUTH_SALT', 'r009-secure-auth-salt' );
define( 'LOGGED_IN_SALT', 'r009-logged-in-salt' );
define( 'NONCE_SALT', 'r009-nonce-salt' );

$table_prefix = 'wptests_';

define( 'WP_TESTS_DOMAIN', 'example.org' );
define( 'WP_TESTS_EMAIL', 'admin@example.org' );
define( 'WP_TESTS_TITLE', 'Test Blog' );
define( 'WP_PHP_BINARY', 'php' );
define( 'WPLANG', '' );

define( 'WP_TESTS_PHPUNIT_POLYFILLS_PATH', '/srv/wp-test-tools/vendor/yoast/phpunit-polyfills' );
