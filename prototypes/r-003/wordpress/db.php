<?php
/**
 * Pressgres R-003 prototype `$wpdb` adapter (wp-content/db.php drop-in).
 *
 * THROWAWAY RESEARCH CODE. Not the D-001/D-002 design. It is deliberately
 * narrow:
 *
 *  - PDO pgsql connection; result rows are stringified like mysqli.
 *  - insert()/update()/delete() are rebuilt with bound parameters, using the
 *    live PostgreSQL catalog to know which columns are `uuid`. insert() uses
 *    `INSERT ... RETURNING <pk>` and sets `$wpdb->insert_id` to the UUID string.
 *  - query() accepts only SELECT/INSERT/UPDATE/DELETE (+ transaction control)
 *    and applies a small, named set of token-level rewrites (listed in
 *    REWRITE_RULES). Known MySQL-only constructs are rejected (fail closed).
 *    This is NOT a SQL translator (that is Q-001).
 *  - Every statement seen is appended to a JSON-lines log
 *    (PRESSGRES_QUERY_LOG) with the original SQL, the SQL sent to PostgreSQL,
 *    rules applied, status, error and a caller summary. Parameter values are
 *    never logged.
 *
 * @package Pressgres\Prototype\R003
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/**
 * Thrown when the adapter refuses a statement (fail closed).
 */
class Pressgres_R003_Unsupported extends RuntimeException {}

/**
 * Minimal PostgreSQL-backed wpdb.
 */
class Pressgres_R003_wpdb extends wpdb {

	/** Canonical lowercase UUID string. */
	const UUID_RE = '/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/';

	/** Mixed-case WordPress columns that must be double-quoted for PostgreSQL. */
	const MIXED_CASE_COLUMNS = array( 'ID', 'comment_ID', 'comment_post_ID', 'comment_author_IP' );

	/** Words whose presence means "MySQL-only, not handled by this prototype". */
	const DENY_WORDS = array(
		'SHOW', 'DESCRIBE', 'REPLACE', 'IGNORE', 'STRAIGHT_JOIN', 'SQL_NO_CACHE',
		'REGEXP', 'RLIKE', 'GROUP_CONCAT', 'FIELD', 'IF', 'IFNULL', 'DATE_FORMAT',
		'UNIX_TIMESTAMP', 'FROM_UNIXTIME', 'LAST_INSERT_ID', 'UNSIGNED', 'SIGNED',
		'USING', 'FORCE', 'USE', 'BINARY', 'DUPLICATE',
	);

	/** @var PDO|null */
	public $pdo;

	/** @var array<string, array<string, string>> table => column => data_type */
	public $pg_columns = array();

	/** @var array<string, string> table => single-column primary key */
	public $pg_primary_keys = array();

	/** @var int|null Result of the last SQL_CALC_FOUND_ROWS emulation. */
	private $pg_found_rows = null;

	/** @var int Statement sequence number (per PHP process). */
	private $pg_seq = 0;

	/** @var string */
	private $pg_log_file;

	public function __construct( $dbuser, #[\SensitiveParameter] $dbpassword, $dbname, $dbhost ) {
		$this->pg_log_file = getenv( 'PRESSGRES_QUERY_LOG' ) ?: WP_CONTENT_DIR . '/pressgres-query-log.jsonl';
		parent::__construct( $dbuser, $dbpassword, $dbname, $dbhost );
	}

	/* ------------------------------------------------------------------ */
	/* Connection                                                          */
	/* ------------------------------------------------------------------ */

	public function db_connect( $allow_bail = true ) {
		$this->is_mysql = false;

		$host = $this->dbhost;
		$port = '5432';
		if ( str_contains( $host, ':' ) ) {
			list( $host, $port ) = explode( ':', $host, 2 );
		}

		try {
			$this->pdo = new PDO(
				"pgsql:host={$host};port={$port};dbname={$this->dbname}",
				$this->dbuser,
				$this->dbpassword,
				array(
					PDO::ATTR_ERRMODE           => PDO::ERRMODE_EXCEPTION,
					PDO::ATTR_STRINGIFY_FETCHES => true, // mysqli returns strings.
					PDO::ATTR_EMULATE_PREPARES  => false,
				)
			);
		} catch ( PDOException $e ) {
			$this->last_error = $e->getMessage();
			if ( $allow_bail ) {
				$this->bail( '<h1>Pressgres R-003: cannot connect to PostgreSQL</h1><p>' . esc_html( $e->getMessage() ) . '</p>', 'db_connect_fail' );
				dead_db();
			}
			return false;
		}

		$this->dbh           = $this->pdo;
		$this->has_connected = true;
		$this->ready         = true;

		$this->pdo->exec( "SET client_encoding TO 'UTF8'" );
		$this->load_pg_catalog();

		return true;
	}

	/** Loads column types and single-column PKs from the live catalog. */
	private function load_pg_catalog() {
		$sql = 'SELECT table_name, column_name, data_type FROM information_schema.columns WHERE table_schema = current_schema()';
		foreach ( $this->pdo->query( $sql )->fetchAll( PDO::FETCH_ASSOC ) as $row ) {
			$this->pg_columns[ $row['table_name'] ][ $row['column_name'] ] = $row['data_type'];
		}
		$this->pg_log( array( 'source' => 'adapter', 'original' => $sql, 'sent' => $sql, 'status' => 'ok' ) );

		$sql = "SELECT tc.table_name, kcu.column_name
			FROM information_schema.table_constraints tc
			JOIN information_schema.key_column_usage kcu
			  ON kcu.constraint_name = tc.constraint_name AND kcu.table_schema = tc.table_schema
			WHERE tc.constraint_type = 'PRIMARY KEY' AND tc.table_schema = current_schema()";
		$pks = array();
		foreach ( $this->pdo->query( $sql )->fetchAll( PDO::FETCH_ASSOC ) as $row ) {
			$pks[ $row['table_name'] ][] = $row['column_name'];
		}
		foreach ( $pks as $table => $cols ) {
			if ( 1 === count( $cols ) ) {
				$this->pg_primary_keys[ $table ] = $cols[0];
			}
		}
		$this->pg_log( array( 'source' => 'adapter', 'original' => preg_replace( '/\s+/', ' ', $sql ), 'sent' => preg_replace( '/\s+/', ' ', $sql ), 'status' => 'ok' ) );
	}

	public function check_connection( $allow_bail = true ) {
		return $this->pdo instanceof PDO;
	}

	public function set_charset( $dbh, $charset = null, $collate = null ) {}

	public function set_sql_mode( $modes = array() ) {}

	public function select( $db, $dbh = null ) {
		$this->ready = true;
	}

	public function close() {
		$this->pdo           = null;
		$this->dbh           = null;
		$this->has_connected = false;
		return true;
	}

	/**
	 * WordPress gates features on a MySQL version string. Report a MySQL-like
	 * version so core does not refuse to run (documented prototype shim).
	 */
	public function db_version() {
		return '8.0';
	}

	public function db_server_info() {
		return $this->pdo ? 'PostgreSQL ' . $this->pdo->getAttribute( PDO::ATTR_SERVER_VERSION ) : '';
	}

	public function get_charset_collate() {
		return '';
	}

	/* ------------------------------------------------------------------ */
	/* Escaping                                                            */
	/* ------------------------------------------------------------------ */

	/**
	 * PostgreSQL with standard_conforming_strings=on: only single quotes need
	 * doubling; backslashes are literal.
	 */
	public function _real_escape( $data ) {
		if ( ! is_scalar( $data ) ) {
			return '';
		}
		return $this->add_placeholder_escape( str_replace( "'", "''", (string) $data ) );
	}

	/* ------------------------------------------------------------------ */
	/* query()                                                             */
	/* ------------------------------------------------------------------ */

	public function query( $query ) {
		if ( ! $this->ready ) {
			return false;
		}

		/** This filter is documented in wp-includes/class-wpdb.php */
		$query = apply_filters( 'query', $query );

		if ( ! $query ) {
			$this->insert_id = 0;
			return false;
		}

		$this->flush();
		$this->func_call  = "\$db->query(\"$query\")";
		$this->last_query = $query;

		// SELECT FOUND_ROWS() after an emulated SQL_CALC_FOUND_ROWS.
		if ( preg_match( '/^\s*SELECT\s+FOUND_ROWS\(\)\s*;?\s*$/i', $query ) ) {
			$this->last_result = array( (object) array( 'FOUND_ROWS()' => (string) (int) $this->pg_found_rows ) );
			$this->num_rows    = 1;
			$this->pg_log( array( 'source' => 'query', 'original' => $query, 'sent' => null, 'rules' => array( 'found-rows-emulated' ), 'status' => 'ok' ) );
			return 1;
		}

		try {
			list( $sql, $rules, $calc_found_rows ) = $this->pg_translate( $query );
		} catch ( Pressgres_R003_Unsupported $e ) {
			return $this->pg_fail( 'query', $query, null, array(), 'unsupported', $e->getMessage() );
		}

		return $this->pg_execute( 'query', $query, $sql, array(), $rules, $calc_found_rows );
	}

	/**
	 * Token-level rewrite of the narrow set of MySQL spellings seen on the
	 * happy path. Anything outside the allow-list throws.
	 *
	 * @return array{0:string,1:string[],2:bool}
	 */
	private function pg_translate( $query ) {
		$tokens = $this->pg_tokenize( $query );
		$rules  = array();

		// Statement-type allow-list.
		$first = null;
		foreach ( $tokens as $t ) {
			if ( 'word' === $t[0] ) {
				$first = strtoupper( $t[1] );
				break;
			}
		}
		if ( ! in_array( $first, array( 'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'START', 'COMMIT', 'ROLLBACK' ), true ) ) {
			throw new Pressgres_R003_Unsupported( "statement type '{$first}' not in allow-list" );
		}

		$calc_found_rows = false;
		$out             = array();
		$n               = count( $tokens );
		$is_options_upsert = false;

		for ( $i = 0; $i < $n; $i++ ) {
			list( $type, $text ) = $tokens[ $i ];

			switch ( $type ) {
				case 'dqstring':
					throw new Pressgres_R003_Unsupported( 'double-quoted string literal (MySQL semantics) not supported' );

				case 'backtick':
					$out[]   = array( 'ident', '"' . str_replace( '"', '""', substr( $text, 1, -1 ) ) . '"' );
					$rules[] = 'backtick-to-double-quote';
					break;

				case 'string':
					if ( str_contains( $text, '\\' ) ) {
						$rules[] = 'warn-backslash-in-literal';
					}
					$out[] = array( $type, $text );
					break;

				case 'word':
					$upper = strtoupper( $text );
					if ( in_array( $text, self::MIXED_CASE_COLUMNS, true ) ) {
						$out[]   = array( 'ident', '"' . $text . '"' );
						$rules[] = 'quote-mixed-case-column';
						break;
					}
					if ( 'SQL_CALC_FOUND_ROWS' === $upper ) {
						$calc_found_rows = true;
						$rules[]         = 'strip-sql-calc-found-rows';
						// Drop the following whitespace too.
						if ( isset( $tokens[ $i + 1 ] ) && 'ws' === $tokens[ $i + 1 ][0] ) {
							++$i;
						}
						break;
					}
					if ( 'DUPLICATE' === $upper && $this->pg_is_options_upsert( $tokens, $i ) ) {
						// ON DUPLICATE KEY UPDATE -> ON CONFLICT ("option_name") DO UPDATE SET
						// (wp_options only, add_option()). VALUES(col) -> EXCLUDED.col below.
						$out[] = array( 'word', 'CONFLICT ("option_name") DO UPDATE SET' );
						$i     = $this->pg_skip_words( $tokens, $i, array( 'DUPLICATE', 'KEY', 'UPDATE' ) );
						$rules[]           = 'options-on-duplicate-key-to-on-conflict';
						$is_options_upsert = true;
						break;
					}
					if ( $is_options_upsert && 'VALUES' === $upper ) {
						// VALUES(`col`) -> EXCLUDED."col"
						$j = $this->pg_next_nonws( $tokens, $i );
						$k = $this->pg_next_nonws( $tokens, $j );
						$l = $this->pg_next_nonws( $tokens, $k );
						if ( null !== $l && '(' === $tokens[ $j ][1] && ')' === $tokens[ $l ][1] ) {
							$col   = 'backtick' === $tokens[ $k ][0] ? substr( $tokens[ $k ][1], 1, -1 ) : $tokens[ $k ][1];
							$out[] = array( 'ident', 'EXCLUDED."' . $col . '"' );
							$i     = $l;
							break;
						}
					}
					if ( 'LIMIT' === $upper ) {
						// LIMIT a, b -> LIMIT b OFFSET a
						$j = $this->pg_next_nonws( $tokens, $i );
						$k = $this->pg_next_nonws( $tokens, $j );
						$l = $this->pg_next_nonws( $tokens, $k );
						if ( null !== $l && 'number' === $tokens[ $j ][0] && ',' === $tokens[ $k ][1] && 'number' === $tokens[ $l ][0] ) {
							$out[]   = array( 'word', 'LIMIT ' . $tokens[ $l ][1] . ' OFFSET ' . $tokens[ $j ][1] );
							$rules[] = 'limit-offset-comma';
							$i       = $l;
							break;
						}
					}
					if ( in_array( $upper, self::DENY_WORDS, true ) ) {
						throw new Pressgres_R003_Unsupported( "MySQL-only keyword/function '{$text}' not handled" );
					}
					$out[] = array( $type, $text );
					break;

				default:
					$out[] = array( $type, $text );
			}
		}

		$sql = implode( '', array_column( $out, 1 ) );

		// INSERT via raw query(): append RETURNING <uuid pk> so insert_id is the UUID.
		if ( 'INSERT' === $first && ! preg_match( '/\bRETURNING\b/i', $sql ) ) {
			$table = $this->pg_insert_table( $sql );
			if ( $table && isset( $this->pg_primary_keys[ $table ] ) ) {
				$sql     = rtrim( $sql, " \t\n\r;" ) . ' RETURNING "' . $this->pg_primary_keys[ $table ] . '"';
				$rules[] = 'insert-returning-pk';
			}
		}

		return array( $sql, array_values( array_unique( $rules ) ), $calc_found_rows );
	}

	private function pg_is_options_upsert( $tokens, $i ) {
		$sql = implode( '', array_column( $tokens, 1 ) );
		return (bool) preg_match( '/^\s*INSERT\s+INTO\s+`?' . preg_quote( $this->options, '/' ) . '`?\s/i', $sql );
	}

	private function pg_skip_words( $tokens, $i, $words ) {
		foreach ( $words as $idx => $w ) {
			if ( $idx > 0 ) {
				$i = $this->pg_next_nonws( $tokens, $i );
			}
			if ( null === $i || strtoupper( $tokens[ $i ][1] ) !== $w ) {
				throw new Pressgres_R003_Unsupported( 'unexpected ON DUPLICATE KEY shape' );
			}
		}
		return $i;
	}

	private function pg_next_nonws( $tokens, $i ) {
		if ( null === $i ) {
			return null;
		}
		for ( $j = $i + 1, $n = count( $tokens ); $j < $n; $j++ ) {
			if ( 'ws' !== $tokens[ $j ][0] ) {
				return $j;
			}
		}
		return null;
	}

	private function pg_insert_table( $sql ) {
		if ( preg_match( '/^\s*INSERT\s+INTO\s+"?([A-Za-z0-9_]+)"?/i', $sql, $m ) ) {
			return $m[1];
		}
		return null;
	}

	/**
	 * Minimal SQL lexer: strings, backtick/double-quoted identifiers, words,
	 * numbers, whitespace, comments, single-char punctuation.
	 *
	 * @return array<int, array{0:string,1:string}>
	 */
	private function pg_tokenize( $sql ) {
		$tokens = array();
		$len    = strlen( $sql );
		$i      = 0;
		while ( $i < $len ) {
			$c = $sql[ $i ];
			if ( ctype_space( $c ) ) {
				$j = $i;
				while ( $j < $len && ctype_space( $sql[ $j ] ) ) {
					++$j;
				}
				$tokens[] = array( 'ws', substr( $sql, $i, $j - $i ) );
				$i        = $j;
			} elseif ( "'" === $c || '"' === $c || '`' === $c ) {
				$j = $i + 1;
				while ( $j < $len ) {
					if ( '\\' === $sql[ $j ] && '`' !== $c ) {
						$j += 2;
						continue;
					}
					if ( $sql[ $j ] === $c ) {
						if ( $j + 1 < $len && $sql[ $j + 1 ] === $c ) {
							$j += 2;
							continue;
						}
						break;
					}
					++$j;
				}
				if ( $j >= $len ) {
					throw new Pressgres_R003_Unsupported( 'unterminated quoted token' );
				}
				$type     = "'" === $c ? 'string' : ( '"' === $c ? 'dqstring' : 'backtick' );
				$tokens[] = array( $type, substr( $sql, $i, $j - $i + 1 ) );
				$i        = $j + 1;
			} elseif ( '-' === $c && '-' === ( $sql[ $i + 1 ] ?? '' ) || '#' === $c || '/' === $c && '*' === ( $sql[ $i + 1 ] ?? '' ) ) {
				throw new Pressgres_R003_Unsupported( 'SQL comments not supported' );
			} elseif ( ctype_alpha( $c ) || '_' === $c ) {
				$j = $i;
				while ( $j < $len && ( ctype_alnum( $sql[ $j ] ) || '_' === $sql[ $j ] || '$' === $sql[ $j ] ) ) {
					++$j;
				}
				$tokens[] = array( 'word', substr( $sql, $i, $j - $i ) );
				$i        = $j;
			} elseif ( ctype_digit( $c ) ) {
				$j = $i;
				while ( $j < $len && ( ctype_digit( $sql[ $j ] ) || '.' === $sql[ $j ] ) ) {
					++$j;
				}
				$tokens[] = array( 'number', substr( $sql, $i, $j - $i ) );
				$i        = $j;
			} else {
				$tokens[] = array( 'punct', $c );
				++$i;
			}
		}
		return $tokens;
	}

	/* ------------------------------------------------------------------ */
	/* insert / update / delete with bound parameters                      */
	/* ------------------------------------------------------------------ */

	public function _insert_replace_helper( $table, $data, $format = null, $type = 'INSERT' ) {
		$this->insert_id = 0;
		$type            = strtoupper( $type );
		$original        = "{$type} INTO {$table} (" . implode( ', ', array_keys( (array) $data ) ) . ') VALUES (...)';

		if ( 'INSERT' !== $type ) {
			return $this->pg_fail( strtolower( $type ), $original, null, array(), 'unsupported', 'REPLACE not supported (no PostgreSQL equivalent without a conflict target)' );
		}

		$rules = array( 'insert-bound-params' );
		try {
			$cols   = array();
			$params = array();
			foreach ( $data as $col => $value ) {
				$cols[]   = $this->pg_quote_ident( $col );
				$params[] = $this->pg_bind_value( $table, $col, $value, $rules );
			}
		} catch ( Pressgres_R003_Unsupported $e ) {
			return $this->pg_fail( 'insert', $original, null, array(), 'unsupported', $e->getMessage() );
		}

		$sql = 'INSERT INTO ' . $this->pg_quote_ident( $table ) . ' (' . implode( ', ', $cols ) . ') VALUES (' . implode( ', ', array_fill( 0, count( $params ), '?' ) ) . ')';
		if ( isset( $this->pg_primary_keys[ $table ] ) ) {
			$sql    .= ' RETURNING ' . $this->pg_quote_ident( $this->pg_primary_keys[ $table ] );
			$rules[] = 'insert-returning-pk';
		}

		$this->last_query = $sql;
		return $this->pg_execute( 'insert', $original, $sql, $params, $rules, false );
	}

	public function update( $table, $data, $where, $format = null, $where_format = null ) {
		if ( ! is_array( $data ) || ! is_array( $where ) ) {
			return false;
		}
		$original = "UPDATE {$table} SET " . implode( ', ', array_keys( $data ) ) . ' WHERE ' . implode( ' AND ', array_keys( $where ) );
		$rules    = array( 'update-bound-params' );
		try {
			$sets   = array();
			$conds  = array();
			$params = array();
			foreach ( $data as $col => $value ) {
				$sets[]   = $this->pg_quote_ident( $col ) . ' = ?';
				$params[] = $this->pg_bind_value( $table, $col, $value, $rules );
			}
			foreach ( $where as $col => $value ) {
				$bound = $this->pg_bind_value( $table, $col, $value, $rules );
				if ( null === $bound ) {
					$conds[] = $this->pg_quote_ident( $col ) . ' IS NULL';
				} else {
					$conds[]  = $this->pg_quote_ident( $col ) . ' = ?';
					$params[] = $bound;
				}
			}
		} catch ( Pressgres_R003_Unsupported $e ) {
			return $this->pg_fail( 'update', $original, null, array(), 'unsupported', $e->getMessage() );
		}
		$sql              = 'UPDATE ' . $this->pg_quote_ident( $table ) . ' SET ' . implode( ', ', $sets ) . ' WHERE ' . implode( ' AND ', $conds );
		$this->last_query = $sql;
		return $this->pg_execute( 'update', $original, $sql, $params, $rules, false );
	}

	public function delete( $table, $where, $where_format = null ) {
		if ( ! is_array( $where ) ) {
			return false;
		}
		$original = "DELETE FROM {$table} WHERE " . implode( ' AND ', array_keys( $where ) );
		$rules    = array( 'delete-bound-params' );
		try {
			$conds  = array();
			$params = array();
			foreach ( $where as $col => $value ) {
				$bound = $this->pg_bind_value( $table, $col, $value, $rules );
				if ( null === $bound ) {
					$conds[] = $this->pg_quote_ident( $col ) . ' IS NULL';
				} else {
					$conds[]  = $this->pg_quote_ident( $col ) . ' = ?';
					$params[] = $bound;
				}
			}
		} catch ( Pressgres_R003_Unsupported $e ) {
			return $this->pg_fail( 'delete', $original, null, array(), 'unsupported', $e->getMessage() );
		}
		$sql              = 'DELETE FROM ' . $this->pg_quote_ident( $table ) . ' WHERE ' . implode( ' AND ', $conds );
		$this->last_query = $sql;
		return $this->pg_execute( 'delete', $original, $sql, $params, $rules, false );
	}

	/**
	 * Converts a PHP value for a column into a bind value. uuid columns accept
	 * only canonical UUID strings; the legacy 0 / '' sentinel becomes NULL.
	 * Any other value for a uuid column (e.g. an int produced by an upstream
	 * (int) cast) is rejected so integer-ID assumptions surface loudly.
	 */
	private function pg_bind_value( $table, $col, $value, array &$rules ) {
		if ( ! isset( $this->pg_columns[ $table ][ $col ] ) ) {
			throw new Pressgres_R003_Unsupported( "unknown column {$table}.{$col}" );
		}
		if ( null === $value ) {
			return null;
		}
		if ( 'uuid' === $this->pg_columns[ $table ][ $col ] ) {
			if ( 0 === $value || '0' === $value || '' === $value ) {
				$rules[] = 'uuid-zero-sentinel-to-null';
				return null;
			}
			$str = is_string( $value ) ? strtolower( $value ) : null;
			if ( null === $str || ! preg_match( self::UUID_RE, $str ) ) {
				throw new Pressgres_R003_Unsupported( "non-UUID value for uuid column {$table}.{$col}: " . get_debug_type( $value ) . '(' . var_export( $value, true ) . ')' );
			}
			return $str;
		}
		if ( is_bool( $value ) ) {
			return $value ? '1' : '0';
		}
		return (string) $value;
	}

	private function pg_quote_ident( $name ) {
		return '"' . str_replace( '"', '""', $name ) . '"';
	}

	/* ------------------------------------------------------------------ */
	/* Execution + logging                                                 */
	/* ------------------------------------------------------------------ */

	private function pg_execute( $source, $original, $sql, array $params, array $rules, $calc_found_rows ) {
		if ( defined( 'SAVEQUERIES' ) && SAVEQUERIES ) {
			$this->timer_start();
		}
		++$this->num_queries;

		try {
			$stmt = $this->pdo->prepare( $sql );
			foreach ( array_values( $params ) as $idx => $p ) {
				$stmt->bindValue( $idx + 1, $p, null === $p ? PDO::PARAM_NULL : PDO::PARAM_STR );
			}
			$stmt->execute();
		} catch ( PDOException $e ) {
			return $this->pg_fail( $source, $original, $sql, $rules, 'error', $e->getMessage() );
		}

		$verb = strtoupper( strtok( ltrim( $sql ), " \n\t(" ) );
		if ( 'INSERT' === $verb || 'UPDATE' === $verb || 'DELETE' === $verb ) {
			$this->rows_affected = $stmt->rowCount();
			if ( 'INSERT' === $verb && $stmt->columnCount() > 0 ) {
				$returned = $stmt->fetchColumn();
				// The whole point of R-003: a UUID string, never an int.
				$this->insert_id = false === $returned ? 0 : (string) $returned;
			}
			$return = $this->rows_affected;
		} elseif ( 'SELECT' === $verb ) {
			$this->last_result = $stmt->fetchAll( PDO::FETCH_OBJ );
			$this->num_rows    = count( $this->last_result );
			$return            = $this->num_rows;
			if ( $calc_found_rows ) {
				$this->pg_found_rows = $this->pg_count_without_limit( $sql );
			}
		} else {
			$return = true;
		}

		if ( defined( 'SAVEQUERIES' ) && SAVEQUERIES ) {
			$this->log_query( $original, $this->timer_stop(), $this->get_caller(), $this->time_start, array( 'pg_sql' => $sql ) );
		}

		$this->pg_log(
			array(
				'source'    => $source,
				'original'  => $original,
				'sent'      => $sql,
				'rules'     => $rules,
				'status'    => 'ok',
				'rows'      => is_int( $return ) ? $return : null,
				'insert_id' => ( 'INSERT' === $verb ) ? $this->insert_id : null,
			)
		);
		return $return;
	}

	/** SQL_CALC_FOUND_ROWS emulation: count the same query without its LIMIT/OFFSET. */
	private function pg_count_without_limit( $sql ) {
		$inner = preg_replace( '/\s+LIMIT\s+\d+(\s+OFFSET\s+\d+)?\s*$/i', '', $sql );
		$count = 'SELECT COUNT(*) FROM (' . $inner . ') AS pressgres_found_rows';
		$value = (int) $this->pdo->query( $count )->fetchColumn();
		$this->pg_log( array( 'source' => 'adapter', 'original' => $count, 'sent' => $count, 'rules' => array( 'found-rows-count' ), 'status' => 'ok', 'rows' => 1 ) );
		return $value;
	}

	private function pg_fail( $source, $original, $sql, array $rules, $status, $message ) {
		$this->last_error = "Pressgres R-003 {$status}: {$message}";
		if ( preg_match( '/^\s*insert/i', (string) $original ) ) {
			$this->insert_id = 0;
		}
		$this->pg_log(
			array(
				'source'   => $source,
				'original' => $original,
				'sent'     => $sql,
				'rules'    => $rules,
				'status'   => $status,
				'error'    => $message,
			)
		);
		$this->print_error( $this->last_error );
		return false;
	}

	private function pg_log( array $entry ) {
		$entry = array_merge(
			array(
				'seq'    => ++$this->pg_seq,
				'pid'    => getmypid(),
				'phase'  => defined( 'PRESSGRES_PHASE' ) ? PRESSGRES_PHASE : ( getenv( 'PRESSGRES_PHASE' ) ?: 'unknown' ),
				'source'  => null,
				'request' => isset( $_SERVER['REQUEST_METHOD'], $_SERVER['REQUEST_URI'] ) ? $_SERVER['REQUEST_METHOD'] . ' ' . preg_replace( '/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/', '<uuid>', $_SERVER['REQUEST_URI'] ) : null,
			),
			$entry,
			array( 'caller' => function_exists( 'wp_debug_backtrace_summary' ) ? wp_debug_backtrace_summary( __CLASS__ ) : null )
		);
		@file_put_contents( $this->pg_log_file, json_encode( $entry, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE ) . "\n", FILE_APPEND | LOCK_EX );
	}

	/** Column metadata for get_col_info(); not needed on the happy path. */
	protected function load_col_info() {
		$this->col_info = array();
	}
}

// phpcs:ignore WordPress.WP.GlobalVariablesOverride.Prohibited
$wpdb = new Pressgres_R003_wpdb( DB_USER, DB_PASSWORD, DB_NAME, DB_HOST );
