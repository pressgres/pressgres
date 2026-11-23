<?php
/**
 * Summarises the adapter's JSON-lines query log.
 * Usage: php query-log-summary.php <query-log.jsonl> [csv-out]
 * Fingerprint = original SQL with string/number/UUID literals replaced by ?.
 */
$file = $argv[1] ?? '/r003/build/logs/query-log.jsonl';
$csv  = $argv[2] ?? dirname( $file ) . '/query-fingerprints.csv';

function r003_fingerprint( $sql ) {
	// Unrolled-loop pattern: avoids PCRE backtrack-limit failures on large literals.
	$sql = preg_replace( "/'[^']*+(?:''[^']*+)*+'/", '?', (string) $sql );
	$sql = preg_replace( '/\b\d+(\.\d+)?\b/', '?', $sql );
	$sql = preg_replace( '/\?(\s*,\s*\?)+/', '?+', $sql );
	return trim( preg_replace( '/\s+/', ' ', $sql ) );
}

$rows = array();
foreach ( file( $file, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES ) as $line ) {
	$rows[] = json_decode( $line, true );
}

$by_phase = array();
$fp       = array();
foreach ( $rows as $r ) {
	$phase = $r['phase'];
	$by_phase[ $phase ]['total'] = ( $by_phase[ $phase ]['total'] ?? 0 ) + 1;
	$by_phase[ $phase ][ $r['status'] ] = ( $by_phase[ $phase ][ $r['status'] ] ?? 0 ) + 1;
	if ( 'adapter' === $r['source'] ) {
		continue;
	}
	$key = $r['source'] . ' | ' . r003_fingerprint( $r['original'] );
	if ( ! isset( $fp[ $key ] ) ) {
		$fp[ $key ] = array( 'source' => $r['source'], 'fingerprint' => r003_fingerprint( $r['original'] ), 'phases' => array(), 'count' => 0, 'rules' => array(), 'status' => array(), 'error' => '' );
	}
	$fp[ $key ]['count']++;
	$fp[ $key ]['phases'][ $phase ] = true;
	foreach ( $r['rules'] ?? array() as $rule ) {
		$fp[ $key ]['rules'][ $rule ] = true;
	}
	$fp[ $key ]['status'][ $r['status'] ] = true;
	if ( ! empty( $r['error'] ) && '' === $fp[ $key ]['error'] ) {
		$fp[ $key ]['error'] = $r['error'];
	}
}

echo "== query log summary ({$file}) ==\n";
printf( "%-12s %6s %6s %6s %12s\n", 'phase', 'total', 'ok', 'error', 'unsupported' );
foreach ( $by_phase as $phase => $c ) {
	printf( "%-12s %6d %6d %6d %12d\n", $phase, $c['total'], $c['ok'] ?? 0, $c['error'] ?? 0, $c['unsupported'] ?? 0 );
}

$sql_rules = array( 'backtick-to-double-quote', 'quote-mixed-case-column', 'limit-offset-comma', 'strip-sql-calc-found-rows', 'options-on-duplicate-key-to-on-conflict', 'found-rows-emulated' );
$per_phase = array();
foreach ( $fp as $f ) {
	foreach ( array_keys( $f['phases'] ) as $phase ) {
		$per_phase[ $phase ]['distinct'] = ( $per_phase[ $phase ]['distinct'] ?? 0 ) + 1;
		if ( array_intersect( $sql_rules, array_keys( $f['rules'] ) ) ) {
			$per_phase[ $phase ]['rewritten'] = ( $per_phase[ $phase ]['rewritten'] ?? 0 ) + 1;
		}
		if ( 'query' !== $f['source'] ) {
			$per_phase[ $phase ]['crud_helper'] = ( $per_phase[ $phase ]['crud_helper'] ?? 0 ) + 1;
		}
		if ( isset( $f['status']['error'] ) || isset( $f['status']['unsupported'] ) ) {
			$per_phase[ $phase ]['failing'] = ( $per_phase[ $phase ]['failing'] ?? 0 ) + 1;
		}
	}
}
echo "\nDistinct statement fingerprints (excluding adapter-internal catalog queries):\n";
printf( "%-12s %9s %22s %26s %8s\n", 'phase', 'distinct', 'raw SQL rewritten', 'insert/update/delete()', 'failing' );
foreach ( $per_phase as $phase => $c ) {
	printf( "%-12s %9d %22d %26d %8d\n", $phase, $c['distinct'], $c['rewritten'] ?? 0, $c['crud_helper'] ?? 0, $c['failing'] ?? 0 );
}
$happy = array_filter( $fp, fn( $f ) => isset( $f['phases']['php-api'] ) || isset( $f['phases']['rest'] ) );
printf( "happy path (php-api + rest, de-duplicated): %d distinct fingerprints, %d with a raw-SQL rewrite rule, %d via insert/update/delete()\n",
	count( $happy ),
	count( array_filter( $happy, fn( $f ) => (bool) array_intersect( $sql_rules, array_keys( $f['rules'] ) ) ) ),
	count( array_filter( $happy, fn( $f ) => 'query' !== $f['source'] ) )
);
printf( "all phases: %d distinct fingerprints\n", count( $fp ) );

$requests = array();
foreach ( $rows as $r ) {
	if ( ! empty( $r['request'] ) && 'adapter' !== $r['source'] ) {
		$requests[ $r['request'] ] = ( $requests[ $r['request'] ] ?? 0 ) + 1;
	}
}
if ( $requests ) {
	echo "\nStatements per REST request (web service):\n";
	foreach ( $requests as $req => $n ) {
		printf( "  %4d  %s\n", $n, $req );
	}
}

$rule_counts = array();
foreach ( $fp as $f ) {
	foreach ( array_keys( $f['rules'] ) as $rule ) {
		$rule_counts[ $rule ] = ( $rule_counts[ $rule ] ?? 0 ) + 1;
	}
}
ksort( $rule_counts );
echo "\nRules applied (number of distinct fingerprints):\n";
foreach ( $rule_counts as $rule => $n ) {
	printf( "  %-42s %d\n", $rule, $n );
}

$fh = fopen( $csv, 'w' );
fputcsv( $fh, array( 'source', 'phases', 'count', 'status', 'rules', 'fingerprint', 'first_error' ), ',', '"', '' );
foreach ( $fp as $f ) {
	fputcsv( $fh, array( $f['source'], implode( ' ', array_keys( $f['phases'] ) ), $f['count'], implode( ' ', array_keys( $f['status'] ) ), implode( ' ', array_keys( $f['rules'] ) ), $f['fingerprint'], $f['error'] ), ',', '"', '' );
}
fclose( $fh );
echo "\nfingerprint CSV: {$csv}\n";

$bad = array_filter( $fp, fn( $f ) => isset( $f['status']['error'] ) || isset( $f['status']['unsupported'] ) );
if ( $bad ) {
	echo "\nFailing fingerprints:\n";
	foreach ( $bad as $f ) {
		printf( "  [%s] %s\n      -> %s\n", implode( ',', array_keys( $f['phases'] ) ), $f['fingerprint'], $f['error'] );
	}
}
