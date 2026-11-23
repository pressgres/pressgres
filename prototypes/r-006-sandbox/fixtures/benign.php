<?php
/** Plugin Name: R-006 Benign */
register_activation_hook( __FILE__, static function (): void {
	update_option( 'r006_benign', 'activated' );
	$upload_dir = wp_get_upload_dir();
	$bytes = file_put_contents( $upload_dir['basedir'] . '/r006.txt', 'fixture upload' );
	r006_observe( 'upload', [ 'success' => 14 === $bytes ] );
} );
