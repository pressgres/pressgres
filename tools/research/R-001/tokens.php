<?php
// Lex source without loading or executing it. Keep each interpolated string intact.
while ( false !== ( $path = fgets( STDIN ) ) ) {
    $path = rtrim( $path, "\r\n" );
    $source = file_get_contents( $path );
    if ( false === $source ) {
        exit( 1 );
    }

    $records = array();
    $line = 1;
    $string = '';
    $string_line = 0;
    $delimiter = '';
    $depth = 0;
    foreach ( token_get_all( $source ) as $token ) {
        [ $kind, $value ] = is_array( $token ) ? $token : array( 0, $token );
        if ( '' !== $delimiter ) {
            $string .= $value;
            if ( T_CURLY_OPEN === $kind || T_DOLLAR_OPEN_CURLY_BRACES === $kind || ( ! $kind && '{' === $value ) ) {
                ++$depth;
            } elseif ( ! $kind && '}' === $value ) {
                --$depth;
            } elseif ( 0 === $depth && ( $delimiter === $token || ( 'heredoc' === $delimiter && T_END_HEREDOC === $kind ) ) ) {
                $records[] = array( 'string', $string, $string_line );
                $delimiter = '';
            }
        } elseif ( '"' === $token || '`' === $token || T_START_HEREDOC === $kind ) {
            $string = $value;
            $string_line = $line;
            $delimiter = T_START_HEREDOC === $kind ? 'heredoc' : $value;
        } elseif ( ! in_array( $kind, array( T_WHITESPACE, T_COMMENT, T_DOC_COMMENT, T_INLINE_HTML, T_OPEN_TAG, T_CLOSE_TAG ), true ) ) {
            $records[] = array( $kind ? token_name( $kind ) : '', $value, $line );
        }

        $line += substr_count( $value, "\n" );
    }

    echo json_encode( $records, JSON_INVALID_UTF8_SUBSTITUTE | JSON_THROW_ON_ERROR ), "\n";
}
