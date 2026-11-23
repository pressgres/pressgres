<?php
/**
 * R-003 demo 1: create + read a post through WordPress PHP APIs.
 */
require __DIR__ . '/lib.php';
require '/r003/build/wordpress/wp-load.php';

$state = json_decode( file_get_contents( '/r003/build/state.json' ), true );

echo "== WordPress PHP API: wp_insert_post() / get_post() ==\n";
wp_set_current_user( $state['admin_id'] );
r003_check( 'wp_set_current_user(uuid) -> get_current_user_id()', get_current_user_id() === $state['admin_id'], var_export( get_current_user_id(), true ) );

$id = wp_insert_post(
	array(
		'post_title'   => 'Hello from PHP (R-003)',
		'post_content' => '<!-- wp:paragraph --><p>Created by wp_insert_post().</p><!-- /wp:paragraph -->',
		'post_status'  => 'publish',
		'post_author'  => $state['admin_id'],
	),
	true
);
if ( is_wp_error( $id ) ) {
	r003_check( 'wp_insert_post()', false, $id->get_error_code() . ': ' . $id->get_error_message() );
	exit( 1 );
}
r003_check( 'wp_insert_post() returned a string', is_string( $id ), var_export( $id, true ) );
r003_check( 'returned ID is a canonical UUIDv7 (36 chars)', is_string( $id ) && 1 === preg_match( R003_UUID_RE, $id ), 'len=' . strlen( (string) $id ) );
r003_check( '$wpdb->insert_id after insert is not an int', ! is_int( $GLOBALS['wpdb']->insert_id ), var_export( $GLOBALS['wpdb']->insert_id, true ) );

clean_post_cache( $id );
$post = get_post( $id );
r003_check( 'get_post(uuid) returned WP_Post', $post instanceof WP_Post );
if ( $post instanceof WP_Post ) {
	r003_check( 'get_post()->ID === returned UUID (untruncated)', $post->ID === $id, var_export( $post->ID, true ) );
	r003_check( 'get_post()->post_author === admin UUID', $post->post_author === $state['admin_id'], var_export( $post->post_author, true ) );
	r003_check( 'get_post()->post_parent is legacy 0/empty sentinel', in_array( $post->post_parent, array( 0, '0', '', null ), true ), var_export( $post->post_parent, true ) );
	r003_check( 'post_title round-trips', 'Hello from PHP (R-003)' === $post->post_title );
	$cats = wp_get_post_categories( $id );
	r003_check( 'default category assigned (UUID term_id)', array( $state['category_id'] ) === $cats, json_encode( $cats ) );
}
r003_db_check_post( $id );

file_put_contents( '/r003/build/php-post-id.txt', (string) $id );
printf( "\nphp demo: %d failure(s)\n", $GLOBALS['r003_failures'] );
exit( $GLOBALS['r003_failures'] ? 1 : 0 );
