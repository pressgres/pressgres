<?php
/** Plugin Name: R-006 Secret Read */
register_activation_hook( __FILE__, static function (): void {
	// Emit presence indicators only. The runtime password is disposable.
	$restricted = [ 'POSTGRES_PASSWORD', 'PG_MIGRATOR_PASSWORD', 'AWS_SECRET_ACCESS_KEY', 'R006_HOST_SECRET' ];
	r006_observe( 'secrets', [
		'runtime_visible'    => false !== getenv( 'PG_RUNTIME_PASSWORD' ) && '' !== DB_PASSWORD,
		'test_marker_visible' => false !== getenv( 'R006_TEST_MARKER' ),
		'restricted_env'     => array_values( array_filter( $restricted, static fn( $key ) => false !== getenv( $key ) ) ),
		'secret_mount'       => is_dir( '/run/secrets' ),
	] );
} );
