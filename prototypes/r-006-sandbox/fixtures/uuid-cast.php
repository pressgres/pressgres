<?php
/** Plugin Name: R-006 UUID Cast */
register_activation_hook( __FILE__, static function (): void {
	global $wpdb;
	$wpdb->suppress_errors();
	$post_id = $wpdb->get_var( 'SELECT ID FROM wp_posts' );
	$valid = '01a20000-0000-7000-8000-000000000006' === $post_id;
	$cast = (int) $post_id;
	$result = $wpdb->insert( $wpdb->postmeta, [
		'post_id' => $cast,
		'meta_key' => 'r006_unsafe',
		'meta_value' => 'fixture marker',
	] );
	r006_observe( 'uuid_cast', [ 'seed_matched' => $valid, 'cast' => $cast, 'rejected' => false === $result ] );
} );
