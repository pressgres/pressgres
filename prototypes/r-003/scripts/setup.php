<?php
/**
 * R-003 setup through WordPress PHP APIs (not raw SQL):
 * roles, admin user, default category, application password.
 * Writes build/state.json for the demo scripts.
 */
require '/r003/build/wordpress/wp-load.php';
require_once ABSPATH . 'wp-admin/includes/schema.php';

function r003_step( $label, $value ) {
	printf( "[setup] %-28s %s\n", $label, is_scalar( $value ) ? var_export( $value, true ) : json_encode( $value ) );
}

populate_roles();
r003_step( 'roles', array_keys( wp_roles()->roles ) );

$user_id = wp_insert_user(
	array(
		'user_login'   => 'admin',
		'user_pass'    => 'r003-admin-password-not-secret',
		'user_email'   => 'admin@example.invalid',
		'display_name' => 'R-003 Admin',
		'role'         => 'administrator',
	)
);
if ( is_wp_error( $user_id ) ) {
	r003_step( 'wp_insert_user FAILED', $user_id->get_error_message() );
	exit( 1 );
}
r003_step( 'admin user ID', $user_id );

$term = wp_insert_term( 'Uncategorized', 'category', array( 'slug' => 'uncategorized' ) );
if ( is_wp_error( $term ) ) {
	r003_step( 'wp_insert_term FAILED', $term->get_error_message() );
	exit( 1 );
}
update_option( 'default_category', $term['term_id'] );
r003_step( 'default_category term_id', $term['term_id'] );

list( $app_password, $item ) = WP_Application_Passwords::create_new_application_password( $user_id, array( 'name' => 'r003' ) );
r003_step( 'application password uuid', $item['uuid'] );

file_put_contents(
	'/r003/build/state.json',
	json_encode(
		array(
			'admin_id'     => $user_id,
			'admin_login'  => 'admin',
			'app_password' => $app_password,
			'category_id'  => $term['term_id'],
		),
		JSON_PRETTY_PRINT
	)
);
r003_step( 'state written', '/r003/build/state.json' );
