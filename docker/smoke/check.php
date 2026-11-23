<?php
/**
 * Pressgres local-stack smoke checks (I-006). Run inside the php service by
 * docker/smoke.sh. Prints one line per check and exits non-zero on failure.
 *
 * Environment: PG_HOST, PG_PORT, PG_DATABASE, PG_RUNTIME_USER,
 * PG_RUNTIME_PASSWORD, VALKEY_HOST, VALKEY_PORT, VALKEY_PASSWORD (compose),
 * PG_MIGRATOR_USER and PG_MIGRATOR_PASSWORD (passed only for this command).
 */

declare(strict_types=1);

$failures = 0;

function check(string $name, bool $ok, string $detail = ''): void
{
    global $failures;
    if (!$ok) {
        $failures++;
    }
    printf("%s %s%s\n", $ok ? 'PASS' : 'FAIL', $name, $detail === '' ? '' : " ($detail)");
}

function env(string $key): string
{
    $value = getenv($key);
    if ($value === false || $value === '') {
        fwrite(STDERR, "missing environment variable $key\n");
        exit(2);
    }
    return $value;
}

function pg(string $user, string $password): PDO
{
    $dsn = sprintf('pgsql:host=%s;port=%s;dbname=%s;sslmode=disable', env('PG_HOST'), env('PG_PORT'), env('PG_DATABASE'));
    return new PDO($dsn, $user, $password, [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]);
}

/** Run $sql and return the SQLSTATE it fails with, or 'OK'. */
function sqlstate(PDO $db, string $sql): string
{
    try {
        $db->exec($sql);
        return 'OK';
    } catch (PDOException $e) {
        return (string) $e->getCode();
    }
}

// PHP runtime and extensions (docs/03 preflight list).
check('php 8.4', PHP_MAJOR_VERSION === 8 && PHP_MINOR_VERSION === 4, PHP_VERSION);
$required = ['pdo_pgsql', 'pgsql', 'redis', 'json', 'mbstring', 'curl', 'openssl', 'dom', 'xml', 'zip', 'intl', 'fileinfo', 'sodium', 'Zend OPcache'];
$missing = array_values(array_filter($required, static fn (string $e): bool => !extension_loaded($e)));
check('php extensions', $missing === [], $missing === [] ? 'redis ' . phpversion('redis') : 'missing: ' . implode(', ', $missing));

// PostgreSQL as the runtime role.
$runtime = pg(env('PG_RUNTIME_USER'), env('PG_RUNTIME_PASSWORD'));
$version = (int) $runtime->query('SHOW server_version_num')->fetchColumn();
check('server_version_num >= 180000', $version >= 180000, (string) $version);
$uuidVersion = (int) $runtime->query('SELECT uuid_extract_version(uuidv7())')->fetchColumn();
check('uuid_extract_version(uuidv7()) = 7', $uuidVersion === 7, (string) $uuidVersion);
$state = sqlstate($runtime, 'CREATE TABLE smoke_runtime_ddl (id uuid)');
check('runtime CREATE TABLE denied', $state === '42501', "SQLSTATE $state");
$state = sqlstate($runtime, 'CREATE TEMPORARY TABLE smoke_runtime_tmp (id uuid)');
check('runtime CREATE TEMPORARY TABLE denied', $state === '42501', "SQLSTATE $state");

// Migrator creates a table as the NOLOGIN owner; runtime gets DML only.
$migrator = pg(env('PG_MIGRATOR_USER'), env('PG_MIGRATOR_PASSWORD'));
$migrator->exec('SET ROLE wps_owner');
$migrator->exec('CREATE TABLE smoke_probe (id uuid PRIMARY KEY DEFAULT uuidv7(), note text NOT NULL)');
$owner = $migrator->query("SELECT tableowner FROM pg_tables WHERE tablename = 'smoke_probe'")->fetchColumn();
check('migrator creates table owned by wps_owner', $owner === 'wps_owner', (string) $owner);

$id = $runtime->query("INSERT INTO smoke_probe (note) VALUES ('smoke') RETURNING id::text")->fetchColumn();
$isV7 = is_string($id) && preg_match('/^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/', $id) === 1;
check('runtime INSERT returns full UUIDv7 string', $isV7, (string) $id);
$stmt = $runtime->prepare('SELECT note FROM smoke_probe WHERE id = ?');
$stmt->execute([$id]);
check('runtime SELECT by UUID', $stmt->fetchColumn() === 'smoke');
foreach ([
    'ALTER TABLE smoke_probe ADD COLUMN extra text',
    'DROP TABLE smoke_probe',
    'TRUNCATE smoke_probe',
] as $ddl) {
    $state = sqlstate($runtime, $ddl);
    check('runtime ' . strtok($ddl, ' ') . ' denied', $state === '42501', "SQLSTATE $state");
}
$migrator->exec('DROP TABLE smoke_probe');

// Valkey via PhpRedis.
$host = env('VALKEY_HOST');
$port = (int) env('VALKEY_PORT');
$anon = new Redis();
$anon->connect($host, $port, 2.0);
try {
    $anon->ping();
    check('valkey rejects unauthenticated client', false);
} catch (RedisException $e) {
    check('valkey rejects unauthenticated client', str_contains($e->getMessage(), 'NOAUTH'), $e->getMessage());
}
$anon->close();

$redis = new Redis();
$redis->connect($host, $port, 2.0);
$redis->auth(env('VALKEY_PASSWORD'));
$info = $redis->info('server');
$valkeyVersion = (string) ($info['valkey_version'] ?? '');
check('INFO valkey_version is 9.2.x', str_starts_with($valkeyVersion, '9.2.'), $valkeyVersion === '' ? 'field missing' : $valkeyVersion);
$key = 'pressgres-smoke:' . $id;
$redis->set($key, $id, ['EX' => 60]);
check('valkey round-trips UUID key and value', $redis->get($key) === $id);
$redis->del($key);

exit($failures === 0 ? 0 : 1);
