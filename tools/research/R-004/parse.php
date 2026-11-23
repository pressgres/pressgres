<?php

declare(strict_types=1);

if (
    !in_array($argc, [4, 5], true)
    || !in_array($argv[3], ['driver', 'standalone'], true)
    || ($argc === 5 && $argv[4] !== '--no-header')
) {
    fprintf(STDERR, "Usage: php %s SQLITE_REFERENCE_ROOT CORPUS.json driver|standalone [--no-header]\n", $argv[0]);
    exit(2);
}

[, $root, $corpusPath, $engine] = $argv;
$root = rtrim($root, '/');
$driver = $engine === 'driver';
$package = $root . '/packages/' . ($driver ? 'mysql-on-sqlite' : 'mysql-parser') . '/src';
if (!is_dir($package)) {
    throw new RuntimeException("Parser directory missing: $package");
}

// The two packages declare the same global class names, so run them in separate processes.
spl_autoload_register(static function (string $class) use ($driver, $package): void {
    $filename = 'class-' . strtolower(str_replace('_', '-', $class)) . '.php';
    $directory = match (true) {
        str_starts_with($class, 'WP_Parser') => '/parser',
        str_starts_with($class, 'WP_MySQL_') => $driver ? '/mysql' : '',
        default => null,
    };
    if ($directory !== null) {
        require_once $package . $directory . '/' . $filename;
    }
});

set_error_handler(static function (int $severity, string $message, string $file, int $line): never {
    throw new ErrorException($message, 0, $severity, $file, $line);
});

function parseStatement(string $sql, bool $driver, WP_Parser $parser): array
{
    try {
        $tokens = (new WP_MySQL_Lexer($sql))->remaining_tokens();
        $last = end($tokens);
        $eof = $driver ? WP_MySQL_Lexer::EOF : WP_MySQL_Lexer::YYEOF;
        if ($last === false || $last->id !== $eof) {
            $lastToken = $last ? $last->get_name() . ' ending at byte ' . ($last->start + $last->length) : 'none';
            return ['lexical_reject', "Missing EOF marker; last valid token: $lastToken", ''];
        }

        if ($driver) {
            $parser->reset_tokens($tokens);
            $parser->next_query();
            $ast = $parser->get_query_ast();
            if ($ast !== null && $parser->next_query()) {
                return ['trailing_tokens', 'Second next_query() found remaining tokens', $ast->rule_name];
            }
        } else {
            $ast = $parser->parse($tokens);
        }

        if (!$ast instanceof WP_Parser_Node) {
            return ['grammar_reject', 'Parser returned no AST or error position', ''];
        }
        return ['ok', '', $ast->get_first_child_node()?->rule_name ?? $ast->rule_name];
    } catch (Throwable $error) {
        return ['runtime_error', get_class($error) . ': ' . $error->getMessage(), ''];
    }
}

$records = json_decode(file_get_contents($corpusPath), true, flags: JSON_THROW_ON_ERROR);
gc_collect_cycles();
memory_reset_peak_usage();
$baselineBytes = memory_get_usage();
$start = hrtime(true);
$parser = $driver
    ? new WP_MySQL_Parser(new WP_Parser_Grammar(require $package . '/mysql/mysql-grammar.php'), [])
    : WP_MySQL_Parser_Factory::create_parser();
$initNs = hrtime(true) - $start;
$initializedBytes = memory_get_usage();

if ($argc === 4) {
    fputcsv(STDOUT, ['id', 'source', 'kind', 'engine', 'status', 'reason', 'ast_first_rule'], escape: '');
}

$counts = [];
$timings = [];
$loopStart = hrtime(true);
foreach ($records as $record) {
    $sql = isset($record['sql_base64']) ? base64_decode($record['sql_base64'], true) : $record['sql'];
    if ($sql === null) {
        continue;
    }
    $start = hrtime(true);
    [$status, $reason, $rule] = parseStatement($sql, $driver, $parser);
    $timings[] = hrtime(true) - $start;
    $counts[$status] = ($counts[$status] ?? 0) + 1;
    fputcsv(STDOUT, [$record['id'], $record['source'], $record['kind'], $engine, $status, $reason, $rule], escape: '');
}
$loopNs = hrtime(true) - $loopStart;
$peakBytes = memory_get_peak_usage();
$reservedPeakBytes = memory_get_peak_usage(true);
if ($timings === []) {
    throw new RuntimeException('Corpus contains no SQL inputs');
}

// Smoke-test full-input and lexical guards separately from the measured corpus.
foreach ([
    'SELECT 1' => ['ok'],
    'SELECT 1;' => ['ok'],
    "SELECT 'unclosed" => ['lexical_reject'],
    "SELECT 1; 'unclosed" => ['lexical_reject'],
    'SELECT FROM' => ['grammar_reject'],
    'SELECT 1; SELECT 2' => ['trailing_tokens', 'grammar_reject'],
] as $sql => $expected) {
    [$actual, $reason] = parseStatement($sql, $driver, $parser);
    if (!in_array($actual, $expected, true)) {
        throw new RuntimeException("Unexpected status $actual for smoke test $sql ($reason)");
    }
}

sort($timings, SORT_NUMERIC);
$count = count($timings);
$lowerMiddle = intdiv($count - 1, 2);
$upperMiddle = intdiv($count, 2);
fwrite(STDERR, json_encode([
    'engine' => $engine,
    'php' => PHP_VERSION,
    'os' => php_uname('s') . ' ' . php_uname('r') . ' ' . php_uname('m'),
    'opcache_cli' => ini_get('opcache.enable_cli'),
    'counts' => $counts,
    'min_us' => $timings[0] / 1_000,
    'median_us' => ($timings[$lowerMiddle] + $timings[$upperMiddle]) / 2_000,
    'p95_us' => $timings[(int) ceil(0.95 * $count) - 1] / 1_000,
    'total_parse_ms' => array_sum($timings) / 1_000_000,
    'loop_wall_ms' => $loopNs / 1_000_000,
    'init_ms' => $initNs / 1_000_000,
    'pre_init_heap_bytes' => $baselineBytes,
    'post_init_heap_bytes' => $initializedBytes,
    'peak_heap_bytes' => $peakBytes,
    'peak_reserved_heap_bytes' => $reservedPeakBytes,
], JSON_PRETTY_PRINT | JSON_THROW_ON_ERROR) . "\n");
if (isset($counts['runtime_error'])) {
    exit(1);
}
