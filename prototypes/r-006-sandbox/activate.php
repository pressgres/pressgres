<?php

function r006_observe( string $kind, array $details ): void {
	file_put_contents( '/scratch/cache/events.jsonl', json_encode( [ 'kind' => $kind ] + $details, JSON_THROW_ON_ERROR | JSON_INVALID_UTF8_SUBSTITUTE ) . "\n", FILE_APPEND );
}

require '/wordpress/wp-load.php';
require_once ABSPATH . 'wp-admin/includes/plugin.php';

$result = activate_plugin( $argv[1] . '.php' );
$active = is_plugin_active( $argv[1] . '.php' );
r006_observe( 'activation', [
	'active' => $active,
	'error'  => is_wp_error( $result ) ? $result->get_error_code() : null,
] );
exit( ! is_wp_error( $result ) && $active ? 0 : 1 );
