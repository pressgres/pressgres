<?php
/** Plugin Name: R-006 Egress */
register_activation_hook( __FILE__, static function (): void {
	// Raw PHP HTTP deliberately bypasses the WordPress HTTP policy.
	$url = 'http://' . getenv( 'R006_CANARY_IP' ) . ':8080/';
	$context = stream_context_create( [ 'http' => [ 'timeout' => 1, 'follow_location' => 0 ] ] );
	$result = @file_get_contents( $url, false, $context );
	r006_observe( 'connection', [
		'url'       => $url,
		'connected' => false !== $result,
		'error'     => false === $result ? ( error_get_last()['message'] ?? null ) : null,
	] );
} );
