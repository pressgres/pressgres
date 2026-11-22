<?php
/**
 * R-003 prototype wp-config.php. THROWAWAY. All values come from the
 * environment set in docker-compose.yml; salts are fixed, public test values.
 */
define( 'DB_NAME', getenv( 'PG_DATABASE' ) ?: 'pressgres' );
define( 'DB_USER', getenv( 'PG_USER' ) ?: 'pressgres' );
define( 'DB_PASSWORD', getenv( 'PG_PASSWORD' ) ?: '' );
define( 'DB_HOST', ( getenv( 'PG_HOST' ) ?: 'db' ) . ':' . ( getenv( 'PG_PORT' ) ?: '5432' ) );
define( 'DB_CHARSET', 'utf8mb4' );
define( 'DB_COLLATE', '' );

foreach ( array( 'AUTH_KEY', 'SECURE_AUTH_KEY', 'LOGGED_IN_KEY', 'NONCE_KEY', 'AUTH_SALT', 'SECURE_AUTH_SALT', 'LOGGED_IN_SALT', 'NONCE_SALT' ) as $pressgres_salt ) {
	define( $pressgres_salt, 'r003-prototype-not-secret-' . $pressgres_salt );
}

$table_prefix = 'wp_';

define( 'WP_HOME', getenv( 'WP_HOME' ) ?: 'http://localhost:58080' );
define( 'WP_SITEURL', WP_HOME );
define( 'WP_ENVIRONMENT_TYPE', 'local' ); // Application passwords over plain HTTP.
define( 'WP_DEBUG', true );
define( 'WP_DEBUG_DISPLAY', false );
define( 'WP_DEBUG_LOG', '/r003/build/logs/wp-debug.log' );
define( 'DISABLE_WP_CRON', true );
define( 'AUTOMATIC_UPDATER_DISABLED', true );
define( 'WP_HTTP_BLOCK_EXTERNAL', true );
define( 'PRESSGRES_PHASE', getenv( 'PRESSGRES_PHASE' ) ?: 'unknown' );

if ( ! defined( 'ABSPATH' ) ) {
	define( 'ABSPATH', __DIR__ . '/' );
}
require_once ABSPATH . 'wp-settings.php';
