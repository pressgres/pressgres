<?php
/**
 * R-003 demo 2: create + read a post through the REST API
 * (POST/GET /wp/v2/posts) on the `web` service, authenticated with an
 * application password (HTTP Basic). Runs WITHOUT loading WordPress.
 */
require __DIR__ . '/lib.php';

$state = json_decode( file_get_contents( '/r003/build/state.json' ), true );
$base  = getenv( 'R003_REST_BASE' ) ?: 'http://web:8080/';
$auth  = 'Authorization: Basic ' . base64_encode( $state['admin_login'] . ':' . $state['app_password'] );

function r003_http( $method, $url, $auth, $body = null ) {
	$headers = array( $auth, 'Accept: application/json' );
	if ( null !== $body ) {
		$headers[] = 'Content-Type: application/json';
	}
	$ctx = stream_context_create(
		array(
			'http' => array(
				'method'        => $method,
				'header'        => implode( "\r\n", $headers ),
				'content'       => null === $body ? '' : json_encode( $body ),
				'ignore_errors' => true,
				'timeout'       => 30,
			),
		)
	);
	$raw    = file_get_contents( $url, false, $ctx );
	$status = 0;
	foreach ( $http_response_header ?? array() as $h ) {
		if ( preg_match( '#^HTTP/\S+\s+(\d+)#', $h, $m ) ) {
			$status = (int) $m[1];
		}
	}
	return array( $status, $raw, json_decode( (string) $raw, true ) );
}

echo "== REST API: POST/GET /wp/v2/posts (application password) ==\n";

list( $status, $raw, $me ) = r003_http( 'GET', $base . '?rest_route=/wp/v2/users/me&context=edit', $auth );
r003_check( 'GET /wp/v2/users/me -> 200', 200 === $status, "HTTP {$status}" );
r003_check( 'users/me id === admin UUID', is_array( $me ) && ( $me['id'] ?? null ) === $state['admin_id'], substr( (string) $raw, 0, 300 ) );

list( $status, $raw, $created ) = r003_http(
	'POST',
	$base . '?rest_route=/wp/v2/posts',
	$auth,
	array(
		'title'   => 'Hello from REST (R-003)',
		'content' => '<!-- wp:paragraph --><p>Created via POST /wp/v2/posts.</p><!-- /wp:paragraph -->',
		'status'  => 'publish',
	)
);
r003_check( 'POST /wp/v2/posts -> 201', 201 === $status, "HTTP {$status}" );
$id = is_array( $created ) ? ( $created['id'] ?? null ) : null;
r003_check( 'response id is a JSON string', is_string( $id ), var_export( $id, true ) . ' ' . ( is_string( $id ) ? '' : substr( (string) $raw, 0, 400 ) ) );
r003_check( 'response id is canonical UUIDv7 (36 chars, untruncated)', is_string( $id ) && 1 === preg_match( R003_UUID_RE, $id ), 'len=' . strlen( (string) $id ) );
r003_check( 'response author === admin UUID', is_array( $created ) && ( $created['author'] ?? null ) === $state['admin_id'], var_export( $created['author'] ?? null, true ) );
r003_check( 'raw JSON contains the quoted UUID', is_string( $id ) && str_contains( (string) $raw, '"id":"' . $id . '"' ) );
if ( ! is_string( $id ) ) {
	exit( 1 );
}

list( $status, $raw, $fetched ) = r003_http( 'GET', $base . '?rest_route=/wp/v2/posts/' . $id, $auth );
r003_check( 'GET /wp/v2/posts/<uuid> -> 200', 200 === $status, "HTTP {$status} " . ( 200 === $status ? '' : substr( (string) $raw, 0, 400 ) ) );
r003_check( 'GET id === POST id (untruncated)', is_array( $fetched ) && ( $fetched['id'] ?? null ) === $id, var_export( $fetched['id'] ?? null, true ) );
r003_check( 'GET title.rendered round-trips', is_array( $fetched ) && 'Hello from REST (R-003)' === ( $fetched['title']['rendered'] ?? null ) );
$self_href = is_array( $fetched ) ? ( $fetched['_links']['self'][0]['href'] ?? '' ) : '';
r003_check( '_links.self ends with the full UUID', str_ends_with( $self_href, '/wp/v2/posts/' . $id ), $self_href );
r003_check( 'GET categories === [default category UUID]', is_array( $fetched ) && array( $state['category_id'] ) === ( $fetched['categories'] ?? null ), json_encode( $fetched['categories'] ?? null ) );

$php_id = trim( (string) @file_get_contents( '/r003/build/php-post-id.txt' ) );
if ( $php_id ) {
	list( $status, $raw, $other ) = r003_http( 'GET', $base . '?rest_route=/wp/v2/posts/' . $php_id, $auth );
	r003_check( 'GET /wp/v2/posts/<uuid of PHP-created post> -> 200 + same id', 200 === $status && ( $other['id'] ?? null ) === $php_id, "HTTP {$status}" );
}

r003_db_check_post( $id );

printf( "     REST response excerpt: %s\n", json_encode( array_intersect_key( $fetched, array_flip( array( 'id', 'author', 'status', 'type', 'categories', 'link' ) ) ), JSON_UNESCAPED_SLASHES ) );
printf( "\nrest demo: %d failure(s)\n", $GLOBALS['r003_failures'] );
exit( $GLOBALS['r003_failures'] ? 1 : 0 );
