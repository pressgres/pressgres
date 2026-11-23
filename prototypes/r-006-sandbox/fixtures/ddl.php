<?php
/** Plugin Name: R-006 DDL */
register_activation_hook( __FILE__, static function (): void {
	global $wpdb;
	$wpdb->suppress_errors();
	$create = $wpdb->query( 'CREATE TABLE r006_ddl_probe (id uuid)' );
	$drop = $wpdb->query( 'DROP TABLE wp_posts' );
	r006_observe( 'ddl', [ 'create_denied' => false === $create, 'drop_denied' => false === $drop ] );
} );
