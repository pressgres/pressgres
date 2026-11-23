<?php
/** Plugin Name: R-006 Core Write */
register_activation_hook( __FILE__, static function (): void {
	$path = ABSPATH . 'wp-includes/r006-write.txt';
	$result = @file_put_contents( $path, 'fixture marker' );
	r006_observe( 'file_write', [
		'path'    => $path,
		'written' => false !== $result,
		'error'   => false === $result ? ( error_get_last()['message'] ?? null ) : null,
	] );
} );
