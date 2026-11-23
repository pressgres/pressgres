<?php

define( 'DB_NAME', 'sandbox' );
define( 'DB_USER', 'sandbox_runtime' );
define( 'DB_PASSWORD', getenv( 'PG_RUNTIME_PASSWORD' ) );
define( 'DB_HOST', getenv( 'PG_HOST' ) . ':5432' );
define( 'DB_CHARSET', 'utf8mb4' );
define( 'DB_COLLATE', '' );
define( 'WP_HOME', 'http://r006.invalid' );
define( 'WP_SITEURL', WP_HOME );
define( 'WP_PLUGIN_DIR', '/fixture' );
define( 'WP_PLUGIN_URL', WP_HOME . '/plugins' );
define( 'WP_TEMP_DIR', '/scratch/cache/' );
define( 'DISABLE_WP_CRON', true );
define( 'DISALLOW_FILE_EDIT', true );
define( 'DISALLOW_FILE_MODS', true );
define( 'WP_HTTP_BLOCK_EXTERNAL', true );
define( 'WP_DEBUG', true );
define( 'WP_DEBUG_DISPLAY', false );
define( 'WP_DEBUG_LOG', '/scratch/cache/wp-debug.log' );

$table_prefix = 'wp_';
require ABSPATH . 'wp-settings.php';
