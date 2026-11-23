<?php

declare(strict_types=1);

const SCHEMA = 'src/wp-admin/includes/schema.php';
const WPDB = 'src/wp-includes/class-wpdb.php';
const SQL_METHODS = ['query', 'get_results', 'get_var', 'get_row', 'get_col', 'prepare'];
const TABLE_METHODS = ['insert', 'update', 'delete', 'replace'];
const TABLES = [
    'termmeta', 'terms', 'term_taxonomy', 'term_relationships', 'commentmeta', 'comments',
    'links', 'options', 'postmeta', 'posts', 'users', 'usermeta', 'blogs', 'blogmeta',
    'registration_log', 'site', 'sitemeta', 'signups', 'sitecategories',
];

if ($argc !== 2 || !is_file($argv[1] . '/' . SCHEMA)) {
    fprintf(STDERR, "Usage: php %s WORDPRESS_REFERENCE_ROOT > corpus.json\n", $argv[0]);
    exit(2);
}

function decodeString(string $contents, bool $singleQuoted): string
{
    $escapes = [
        'n' => "\n", 'r' => "\r", 't' => "\t", 'v' => "\v", 'e' => "\e", 'f' => "\f",
        '\\' => '\\', '$' => '$', '"' => '"',
    ];
    if ($singleQuoted) {
        return strtr($contents, ["\\'" => "'", '\\\\' => '\\']);
    }
    return preg_replace_callback(
        '~\\\\(u\{[0-9a-fA-F]+\}|x[0-9a-fA-F]{1,2}|[0-7]{1,3}|.)~s',
        static function (array $match) use ($escapes): string {
            $code = $match[1];
            return match (true) {
                str_starts_with($code, 'u{') => html_entity_decode('&#x' . substr($code, 2, -1) . ';', ENT_QUOTES, 'UTF-8'),
                strlen($code) > 1 && $code[0] === 'x' => chr(hexdec(substr($code, 1))),
                strspn($code, '01234567') === strlen($code) => chr(octdec($code)),
                default => $escapes[$code] ?? $match[0],
            };
        },
        $contents
    );
}

function tokensText(array $tokens): string
{
    return implode('', array_column($tokens, 'text'));
}

function groupEnd(array $tokens, int $start): int
{
    $first = $tokens[$start];
    $close = match ($first->id) {
        T_START_HEREDOC => T_END_HEREDOC,
        T_CURLY_OPEN, T_DOLLAR_OPEN_CURLY_BRACES => ord('}'),
        T_ATTRIBUTE => ord(']'),
        default => match ($first->id) {
            ord('(') => ord(')'),
            ord('[') => ord(']'),
            ord('{') => ord('}'),
            ord('"') => ord('"'),
            ord('`') => ord('`'),
            default => null,
        },
    };
    if ($close === null) {
        return $start;
    }

    for ($index = $start + 1; isset($tokens[$index]); ++$index) {
        if ($tokens[$index]->id === $close) {
            return $index;
        }
        $index = groupEnd($tokens, $index);
    }
    throw new RuntimeException("Unclosed PHP group at line {$first->line}");
}

function splitTopLevel(array $tokens, string $separator): array
{
    $parts = [];
    $start = 0;
    for ($index = 0; $index < count($tokens); ++$index) {
        $token = $tokens[$index];
        if ($token->is($separator)) {
            $parts[] = array_slice($tokens, $start, $index - $start);
            $start = $index + 1;
        } else {
            $index = groupEnd($tokens, $index);
        }
    }
    return [...$parts, array_slice($tokens, $start)];
}

function interpolationValue(string $expression): ?string
{
    $expression = trim($expression, '{}');
    if (preg_match('/^\$(?:wpdb|this)->(\w+)$/D', $expression, $match)) {
        return match (true) {
            in_array($match[1], TABLES, true) => 'wp_' . $match[1],
            in_array($match[1], ['prefix', 'base_prefix'], true) => 'wp_',
            default => null,
        };
    }
    return match ($expression) {
        '$max_index_length' => '191',
        '$charset_collate' => 'DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_520_ci',
        default => null,
    };
}

// Return the SQL-like template and any PHP expressions whose values remain unknown.
function renderPart(array $tokens, bool $schema = false): array
{
    $first = $tokens[0] ?? null;
    if (!$first) {
        return [null, []];
    }
    if ($first->is('(') && groupEnd($tokens, 0) === count($tokens) - 1) {
        return renderExpression(array_slice($tokens, 1, -1), $schema);
    }
    if (count($tokens) === 1 && $first->is(T_CONSTANT_ENCAPSED_STRING)) {
        $literal = preg_replace('/^[bB](?=[\x27"])/', '', $first->text);
        return [decodeString(substr($literal, 1, -1), $literal[0] === "'"), []];
    }
    if (!$first->is(['"', T_START_HEREDOC]) || groupEnd($tokens, 0) !== count($tokens) - 1) {
        $expression = tokensText($tokens);
        return [null, [$expression]];
    }
    $heredoc = $first->is(T_START_HEREDOC);
    $nowdoc = $heredoc && str_contains($first->text, "'");
    $end = count($tokens) - 1;
    if ($heredoc && preg_match('/^\s/', $tokens[$end]->text)) {
        return [null, ['indented heredoc/nowdoc']];
    }

    $result = '';
    $unknown = [];
    for ($index = 1; $index < $end; ++$index) {
        $token = $tokens[$index];
        if ($token->is(T_ENCAPSED_AND_WHITESPACE)) {
            $result .= $nowdoc ? $token->text : decodeString($token->text, false);
            continue;
        }
        $start = $index;
        $index = groupEnd($tokens, $index);
        if ($token->is(T_VARIABLE) && $tokens[$index + 1]->is(T_OBJECT_OPERATOR)) {
            $index += 2;
        }
        if ($token->is(T_VARIABLE) && $tokens[$index + 1]->is('[')) {
            $index = groupEnd($tokens, $index + 1);
        }
        $expression = tokensText(array_slice($tokens, $start, $index - $start + 1));
        $value = interpolationValue($expression);
        if ($value === null || (!$schema && in_array(trim($expression, '{}'), ['$max_index_length', '$charset_collate'], true))) {
            $unknown[] = $expression;
        }
        $result .= $value !== null && !in_array($expression, $unknown, true) ? $value : '{{' . $expression . '}}';
    }
    if ($heredoc) {
        $result = preg_replace('/\r?\n$/D', '', $result);
    }
    return [$result, $unknown];
}

function renderExpression(array $tokens, bool $schema = false): array
{
    $result = '';
    $unknown = [];
    $hasLiteral = false;
    foreach (splitTopLevel($tokens, '.') as $part) {
        [$value, $unresolved] = renderPart($part, $schema);
        $unknown = [...$unknown, ...$unresolved];
        $hasLiteral = $hasLiteral || $value !== null;
        $result .= $value ?? '{{' . tokensText($part) . '}}';
    }
    return [$hasLiteral ? $result : null, $unknown];
}

function collectLiterals(array $tokens): array
{
    $literals = [];
    for ($index = 0; $index < count($tokens); ++$index) {
        $token = $tokens[$index];
        if (!$token->is([T_CONSTANT_ENCAPSED_STRING, '"', T_START_HEREDOC])) {
            continue;
        }
        $end = groupEnd($tokens, $index);
        $literals[] = tokensText(array_slice($tokens, $index, $end - $index + 1));
        $index = $end;
    }
    return $literals;
}

function samplePrepare(string $template): string
{
    // Materialize the format for a grammar run, using one synthetic value per type.
    $template = str_replace(["'%s'", '"%s"'], '%s', $template);
    $format = '(?:[1-9][0-9]*\$)?[-+0-9]*(?: |\x27.)?[-+0-9]*(?:\.[0-9]+)?';
    $placeholder = "%($format)([sdfFi])";
    return preg_replace_callback(
        "~%%|'(?:\\\\.|''|[^'\\\\])*'|\"(?:\\\\.|\"\"|[^\"\\\\])*\"|`(?:``|[^`])*`|$placeholder~s",
        static function (array $entry) use ($placeholder): string {
            if ($entry[0] === '%%') {
                return '%';
            }
            if (isset($entry[2])) {
                return match ($entry[2]) {
                    's' => $entry[1] === '' ? "'r004'" : 'r004',
                    'i' => '`wp_r004`',
                    'd' => '7',
                    default => '1.25',
                };
            }
            return preg_replace_callback(
                "~%%|$placeholder~",
                static fn (array $match): string => match ($match[2] ?? '%') {
                    '%' => '%', 'd' => '7', 'f', 'F' => '1.25', default => 'r004',
                },
                $entry[0]
            );
        },
        $template
    );
}

function sourceFiles(string $root): iterable
{
    foreach (['src', 'tests/phpunit'] as $scope) {
        $files = [];
        foreach (new RecursiveIteratorIterator(new RecursiveDirectoryIterator("$root/$scope")) as $entry) {
            if ($entry->isFile() && $entry->getExtension() === 'php') {
                $files[] = substr($entry->getPathname(), strlen($root) + 1);
            }
        }
        sort($files, SORT_STRING);
        yield from $files;
    }
}

function callRecords(array $tokens, string $path, string $contents): iterable
{
    $methods = [...SQL_METHODS, ...TABLE_METHODS];
    for ($index = 0; $index + 3 < count($tokens); ++$index) {
        [$receiver, $operator, $name, $open] = array_slice($tokens, $index, 4);
        if (
            !$receiver->is(T_VARIABLE)
            || ($receiver->text !== '$wpdb' && !($path === WPDB && $receiver->text === '$this'))
            || !$operator->is(T_OBJECT_OPERATOR)
            || !$name->is(T_STRING)
            || !in_array(strtolower($name->text), $methods, true)
            || !$open->is('(')
        ) {
            continue;
        }
        $method = strtolower($name->text);
        $close = groupEnd($tokens, $index + 3);
        [$argument] = splitTopLevel(array_slice($tokens, $index + 4, $close - $index - 4), ',');
        if (isset($argument[1]) && $argument[0]->is(T_STRING) && $argument[1]->is(':')) {
            $argument = array_slice($argument, 2);
        }
        if (!$argument) {
            continue;
        }
        [$template, $unknown] = renderExpression($argument);
        $literals = collectLiterals($argument);
        $kind = match (true) {
            in_array($method, TABLE_METHODS, true) => 'table_argument',
            $template === null && $literals === [] => 'indirect',
            $unknown !== [] => 'dynamic',
            preg_match('/^(?:\s|\/\*.*?\*\/)*(?:\(\s*)*(?:SELECT|INSERT|UPDATE|DELETE|REPLACE|WITH|CREATE|ALTER|DROP|TRUNCATE|SHOW|DESCRIBE|DESC|EXPLAIN|SET|START|BEGIN|COMMIT|ROLLBACK|SAVEPOINT|RELEASE|LOCK|UNLOCK|USE|CHECK|ANALYZE|OPTIMIZE|REPAIR|RENAME|FLUSH|GRANT|REVOKE|DO|CALL|HANDLER|LOAD|KILL|RESET)\b/is', $template ?? '') === 1 => 'statement',
            default => 'fragment_or_non_sql',
        };
        $sql = $kind === 'statement' ? trim($template) : null;
        if ($sql !== null && $method === 'prepare') {
            $sql = samplePrepare($sql);
        }
        yield [
            'source' => "$path:{$argument[0]->line}",
            'call_line' => $receiver->line,
            'method' => $receiver->text . '->' . $method,
            'kind' => $kind,
            'confidence' => match ($kind) {
                'statement' => $method === 'prepare' ? 'medium' : 'high',
                'fragment_or_non_sql', 'dynamic' => 'medium',
                default => 'high',
            },
            'php_argument' => substr($contents, $argument[0]->pos, end($argument)->pos + strlen(end($argument)->text) - $argument[0]->pos),
            'php_literals' => $literals,
            'template' => $template,
            'unresolved' => $unknown,
            'sql' => $sql,
        ];
    }
}

function schemaRecords(array $tokens, string $path): iterable
{
    for ($index = 0; $index < count($tokens); ++$index) {
        if (!$tokens[$index]->is('"') || !($tokens[$index + 1] ?? null)?->is(T_ENCAPSED_AND_WHITESPACE)
            || !preg_match('/^\s*CREATE TABLE\b/i', $tokens[$index + 1]->text)) {
            continue;
        }
        $end = groupEnd($tokens, $index);
        $literal = array_slice($tokens, $index, $end - $index + 1);
        [$sql, $unknown] = renderPart($literal, true);
        if ($unknown !== []) {
            throw new RuntimeException('Unresolved schema interpolation: ' . implode(', ', $unknown));
        }
        $raw = tokensText($literal);
        preg_match_all('/^\s*CREATE TABLE\b/im', substr($raw, 1), $matches, PREG_OFFSET_CAPTURE);
        $tables = array_values(array_filter(array_map('trim', explode(';', $sql)), 'strlen'));
        if (count($matches[0]) !== count($tables)) {
            throw new RuntimeException('Schema source and rendered table count differ');
        }
        foreach ($tables as $tableIndex => $table) {
            $offset = $matches[0][$tableIndex][1] + strlen($matches[0][$tableIndex][0]);
            $line = $tokens[$index]->line + substr_count(substr($raw, 1, $offset), "\n");
            yield [
                'source' => "$path:$line",
                'method' => 'wp_get_db_schema',
                'kind' => 'schema',
                'confidence' => 'high',
                'sql' => $table . ';',
            ];
        }
        $index = $end;
    }
}

function supplementalRecords(): iterable
{
    // Fixed inputs for SQL assembled outside a literal call. These are illustrative branches,
    // with values chosen for lexing and parsing without bootstrapping WordPress.
    $materialized = [
        ['src/wp-includes/class-wp-query.php:3193', 'wp_query_with_found_rows',
            "SELECT SQL_CALC_FOUND_ROWS ID FROM wp_posts WHERE 1=1 ORDER BY ID LIMIT 2,3"],
        ['src/wp-includes/class-wp-query.php:3722', 'wp_query_found_rows',
            "SELECT FOUND_ROWS()"],
        ['src/wp-includes/class-wp-term-query.php:932', 'term_include_order',
            "SELECT t.term_id FROM wp_terms t ORDER BY FIELD(t.term_id, 7, 8)"],
        ['src/wp-includes/class-wpdb.php:2613', 'wpdb_insert',
            "INSERT INTO `wp_posts` (`post_title`, `post_parent`) VALUES ('r004', NULL)"],
        ['tests/phpunit/tests/db.php:684', 'wpdb_replace',
            "REPLACE INTO `wp_users` (`ID`, `display_name`) VALUES (7, 'r004')"],
        ['src/wp-includes/class-wpdb.php:2719', 'wpdb_update',
            "UPDATE `wp_posts` SET `post_title` = 'r004' WHERE `ID` = 7"],
        ['src/wp-includes/class-wpdb.php:2789', 'wpdb_delete',
            "DELETE FROM `wp_posts` WHERE `post_parent` IS NULL"],
        ['src/wp-admin/includes/upgrade.php:2799', 'show_full_columns',
            "SHOW FULL COLUMNS FROM `wp_posts`"],
        ['src/wp-admin/includes/upgrade.php:3270', 'show_index',
            "SHOW INDEX FROM wp_posts;"],
        ['src/wp-includes/comment.php:759', 'completed_comment_duplicate_check',
            "SELECT comment_ID FROM wp_comments WHERE comment_post_ID = 7 AND comment_parent = '0'"
                . " AND comment_approved != 'trash' AND (comment_author = 'r004') AND comment_content = 'r004' LIMIT 1"],
    ];
    foreach ($materialized as [$source, $example, $sql]) {
        yield [
            'source' => $source,
            'method' => $example,
            'kind' => 'materialized_example',
            'confidence' => 'medium',
            'sql' => $sql,
        ];
    }
    // Task-requested dialect probes whose exact SQL need not occur in a core call.
    $probes = [
        ['src/wp-includes/class-wpdb.php:2613', 'synthetic_ifnull', "SELECT IFNULL(NULL, 'r004')"],
        ['src/wp-includes/class-wpdb.php:2313', 'synthetic_last_insert_id', "SELECT LAST_INSERT_ID()"],
        ['src/wp-includes/class-wpdb.php:2313', 'synthetic_last_insert_id_argument', "SELECT LAST_INSERT_ID(7)"],
        ['src/wp-includes/class-wpdb.php:1763', 'synthetic_explicit_collation',
            "SELECT option_name FROM wp_options WHERE option_name COLLATE utf8mb4_unicode_520_ci LIKE 'R004%'"],
    ];
    foreach ($probes as [$source, $example, $sql]) {
        yield [
            'source' => $source,
            'source_role' => 'related_wordpress_context',
            'method' => $example,
            'kind' => 'synthetic_probe',
            'confidence' => 'high',
            'sql' => $sql,
        ];
    }
}

$root = rtrim($argv[1], '/');
$prefix = basename($root);
$records = [];
foreach (sourceFiles($root) as $path) {
    $contents = file_get_contents("$root/$path");
    if ($contents === false) {
        throw new RuntimeException("Cannot read $path");
    }
    if ($path !== SCHEMA && $path !== WPDB && !str_contains($contents, '$wpdb')) {
        continue;
    }
    $tokens = array_values(array_filter(
        PhpToken::tokenize($contents),
        static fn (PhpToken $token): bool => !$token->is([T_WHITESPACE, T_COMMENT, T_DOC_COMMENT])
    ));
    foreach (callRecords($tokens, $path, $contents) as $record) {
        $records[] = $record;
    }
    if ($path === SCHEMA) {
        foreach (schemaRecords($tokens, $path) as $record) {
            $records[] = $record;
        }
    }
}

$records = [...$records, ...supplementalRecords()];
foreach ($records as $index => &$record) {
    $record = ['id' => sprintf('R004-%04d', $index + 1)] + $record;
    $record['source'] = $prefix . '/' . $record['source'];
    foreach (['sql', 'template', 'php_argument'] as $field) {
        if (isset($record[$field]) && preg_match('//u', $record[$field]) !== 1) {
            $record[$field . '_base64'] = base64_encode($record[$field]);
            $record[$field] = null;
        }
    }
}
unset($record);
echo json_encode($records, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR), "\n";
