<?php
/** Shared helpers for the R-003 demo scripts (no WordPress dependency). */

const R003_UUID_RE = '/^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/';

$GLOBALS['r003_failures'] = 0;

function r003_check( $label, $ok, $detail = '' ) {
	if ( ! $ok ) {
		++$GLOBALS['r003_failures'];
	}
	printf( "%s %s%s\n", $ok ? 'PASS' : 'FAIL', $label, '' === $detail ? '' : "  [{$detail}]" );
	return $ok;
}

/** Independent PDO connection (not via the adapter) to verify what PostgreSQL stored. */
function r003_pdo() {
	static $pdo;
	if ( ! $pdo ) {
		$pdo = new PDO(
			sprintf( 'pgsql:host=%s;port=%s;dbname=%s', getenv( 'PG_HOST' ), getenv( 'PG_PORT' ), getenv( 'PG_DATABASE' ) ),
			getenv( 'PG_USER' ),
			getenv( 'PG_PASSWORD' ),
			array( PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION )
		);
	}
	return $pdo;
}

function r003_db_check_post( $id ) {
	$stmt = r003_pdo()->prepare( 'SELECT "ID"::text AS id, uuid_extract_version("ID") AS v, uuid_extract_timestamp("ID") AS ts, post_author::text AS author, post_title FROM wp_posts WHERE "ID" = ?' );
	$stmt->execute( array( $id ) );
	$row = $stmt->fetch( PDO::FETCH_ASSOC );
	r003_check( 'PostgreSQL row exists for ' . $id, (bool) $row );
	if ( $row ) {
		r003_check( 'SELECT uuid_extract_version("ID") = 7', 7 === (int) $row['v'], 'got ' . $row['v'] . ', uuid_extract_timestamp=' . $row['ts'] );
		r003_check( 'stored "ID" equals returned ID byte-for-byte', $row['id'] === $id );
		printf( "     db row: %s\n", json_encode( $row ) );
	}
	return $row;
}
