<?php

declare(strict_types=1);

namespace Pressgres\InstallerCli\Tests;

use JsonSchema\Constraints\Constraint;
use JsonSchema\Validator;
use PHPUnit\Framework\Attributes\DataProvider;
use PHPUnit\Framework\TestCase;
use stdClass;

final class InitTest extends TestCase
{
    private const array INIT = ['init', '--profile', 'postgres-native-uuid'];

    private string $directory;

    protected function setUp(): void
    {
        $this->directory = sys_get_temp_dir() . '/wps-init-test-' . bin2hex(random_bytes(8));
        self::assertTrue(mkdir($this->directory, 0700));
    }

    protected function tearDown(): void
    {
        $entries = scandir($this->directory);
        self::assertIsArray($entries);
        foreach (array_diff($entries, ['.', '..']) as $entry) {
            unlink($this->directory . '/' . $entry);
        }
        rmdir($this->directory);
    }

    public function testDefaultsMatchSnapshotsAndCheckedInSample(): void
    {
        self::assertFalse(self::data($this->runBinary(self::INIT, 0, 'init'))->dry_run);
        $config = $this->directory . '/pressgres.yaml';
        $env = $this->directory . '/.env.example';
        self::assertFileEquals(__DIR__ . '/snapshots/init.yaml', $config);
        self::assertFileEquals(__DIR__ . '/snapshots/init.env', $env);
        self::assertFileEquals(dirname(__DIR__, 3) . '/examples/config/pressgres.yaml', $config);

        $configMode = fileperms($config);
        $envMode = fileperms($env);
        self::assertIsInt($configMode);
        self::assertIsInt($envMode);
        self::assertSame(0600, $configMode & 0777);
        self::assertSame(0644, $envMode & 0777);
        $validated = $this->runBinary(['config', 'validate', '--config', 'pressgres.yaml'], 0, 'config validate');
        self::assertSame('1.0', self::data($validated)->schema_version);
    }

    public function testDryRunAndOverwritePolicyForEitherFile(): void
    {
        $config = $this->directory . '/custom.yaml';
        $env = $this->directory . '/.env.example';
        $arguments = [...self::INIT, '--output=custom.yaml'];
        $preview = $this->runBinary([...$arguments, '--dry-run'], 0, 'init');
        self::assertTrue(self::data($preview)->dry_run);
        self::assertFileDoesNotExist($config);
        self::assertFileDoesNotExist($env);

        file_put_contents($env, 'existing example');
        $this->runBinary($arguments, 2, 'init');
        self::assertFileDoesNotExist($config);
        self::assertSame('existing example', file_get_contents($env));
        unlink($env);

        file_put_contents($config, 'existing config');
        $this->runBinary($arguments, 2, 'init');
        self::assertSame('existing config', file_get_contents($config));
        self::assertFileDoesNotExist($env);

        file_put_contents($env, 'existing example');
        $this->runBinary([...$arguments, '--dry-run', '--force'], 0, 'init');
        self::assertSame('existing config', file_get_contents($config));
        self::assertSame('existing example', file_get_contents($env));
        $this->runBinary([...$arguments, '--force'], 0, 'init');
        self::assertFileEquals(__DIR__ . '/snapshots/init.yaml', $config);
        self::assertFileEquals(__DIR__ . '/snapshots/init.env', $env);
        self::assertSame(2, iterator_count(new \FilesystemIterator($this->directory)));
    }

    public function testForceRefusesSymlinkAndOutputCollision(): void
    {
        $file = $this->directory . '/original';
        file_put_contents($file, 'untouched');
        self::assertTrue(symlink($file, $this->directory . '/.env.example'));
        $this->runBinary([...self::INIT, '--force'], 2, 'init');
        self::assertFileDoesNotExist($this->directory . '/pressgres.yaml');
        self::assertSame('untouched', file_get_contents($file));
        $this->runBinary([...self::INIT, '--force', '--output=.ENV.EXAMPLE'], 2, 'init');
    }

    public function testValidReferencesAreAcceptedWithoutResolution(): void
    {
        $this->validateYaml(
            "database:\n  password: env:WPS_UNSET_TEST_VAR\n"
            . "  migrator_password: 'file:/nonexistent/secret directory/password'\n"
            . "redis:\n  password: 'file:/nonexistent/cache-password'\n",
            0,
            [],
        );
    }

    /** @param list<string> $paths */
    #[DataProvider('invalidConfigurations')]
    public function testInvalidConfigIsRedacted(string $fragment, int $exitCode, array $paths): void
    {
        $this->validateYaml($fragment, $exitCode, $paths);
    }

    /** @return iterable<string, array{string, int, list<string>}> */
    public static function invalidConfigurations(): iterable
    {
        yield 'unknown root key' => ["private-marker: private-marker\n", 2, ['']];
        yield 'unknown nested key' => ["database:\n  'private-marker/a~b': value\n", 2, ['/database']];
        yield 'inline schema' => ["database:\n  \$schema: private-marker\n", 2, ['/database']];
        yield 'closed identity contract' => ["identity:\n  allow_integer_fallback: true\n", 2, [
            '/identity/allow_integer_fallback',
        ]];
        yield 'wrong section shape' => ["project: []\n", 2, ['/project']];
        yield 'plaintext runtime credential' => ["database:\n  password: private-marker\n", 5, ['/database/password']];
        yield 'plaintext migrator credential' => [
            "database:\n  migrator_password: private-marker\n", 5, ['/database/migrator_password'],
        ];
        yield 'malformed environment ref' => ["redis:\n  password: env:1private-marker\n", 5, ['/redis/password']];
        yield 'relative file ref' => ["redis:\n  password: file:private-marker\n", 5, ['/redis/password']];
        yield 'newline in file ref' => ["redis:\n  password: |\n    file:/private-marker\n", 5, ['/redis/password']];
        yield 'YAML object instead of secret' => ["database:\n  password: {private-marker: value}\n", 5, [
            '/database/password',
        ]];
        yield 'shared database credentials' => [
            "database:\n  runtime_user: db\n  migrator_user: db\n"
            . "  password: env:PRIVATE_MARKER\n  migrator_password: env:PRIVATE_MARKER\n",
            5,
            ['/database/migrator_user', '/database/migrator_password'],
        ];
        yield 'mixed errors prioritize security' => [
            "database:\n  password: private-marker\n  extra-key: value\n",
            5,
            ['/database/password', '/database'],
        ];
        yield 'duplicate map key' => [
            "database:\n  password: private-marker\n  password: env:WPS_UNSET_TEST_VAR\n", 2, [''],
        ];
        yield 'malformed YAML' => ["database: [private-marker\n", 2, ['']];
    }

    public function testMissingSchemaVersion(): void
    {
        file_put_contents($this->directory . '/fixture.yaml', "project: {}\n");
        $result = $this->runBinary(['config', 'validate', '--config=fixture.yaml'], 2, 'config validate');
        self::assertSame(['/schema_version'], self::paths($result));
    }

    /** @param list<string> $paths */
    private function validateYaml(string $fragment, int $exitCode, array $paths): void
    {
        file_put_contents($this->directory . '/fixture.yaml', "schema_version: '1.0'\n" . $fragment);
        $result = $this->runBinary(['config', 'validate', '--config=fixture.yaml'], $exitCode, 'config validate');
        self::assertSame($paths, self::paths($result));
    }

    private static function data(stdClass $result): stdClass
    {
        self::assertInstanceOf(stdClass::class, $result->data);

        return $result->data;
    }

    /** @return list<string> */
    private static function paths(stdClass $result): array
    {
        self::assertIsArray($result->diagnostics);
        $paths = [];
        foreach ($result->diagnostics as $diagnostic) {
            self::assertInstanceOf(stdClass::class, $diagnostic);
            self::assertInstanceOf(stdClass::class, $diagnostic->context);
            self::assertIsString($diagnostic->context->path);
            self::assertSame($result->correlation_id, $diagnostic->correlation_id);
            $paths[] = $diagnostic->context->path;
        }

        return $paths;
    }

    /** @param list<string> $arguments */
    private function runBinary(array $arguments, int $exitCode, string $command): stdClass
    {
        $binary = dirname(__DIR__, 3) . '/vendor/bin/wps';
        $process = proc_open(
            [PHP_BINARY, $binary, ...$arguments, '--format=json'],
            [1 => ['pipe', 'w'], 2 => ['pipe', 'w']],
            $pipes,
            $this->directory,
        );
        self::assertIsResource($process);
        $stdout = stream_get_contents($pipes[1]);
        $stderr = stream_get_contents($pipes[2]);
        fclose($pipes[1]);
        fclose($pipes[2]);

        self::assertSame($exitCode, proc_close($process), (string) $stdout . $stderr);
        self::assertSame('', $stderr);
        self::assertIsString($stdout);
        $redacted = [
            'private-marker', 'PRIVATE_MARKER', 'WPS_UNSET_TEST_VAR', 'nonexistent', 'env:WPS_RUNTIME_PASSWORD',
        ];
        foreach ($redacted as $value) {
            self::assertStringNotContainsString($value, $stdout);
        }
        $result = json_decode($stdout, false, 512, JSON_THROW_ON_ERROR);
        $schema = file_get_contents(__DIR__ . '/../schemas/cli-v1.json');
        self::assertIsString($schema);
        $validator = new Validator();
        $validator->validate(
            $result,
            json_decode($schema, false, 512, JSON_THROW_ON_ERROR),
            Constraint::CHECK_MODE_STRICT,
        );
        self::assertTrue($validator->isValid(), var_export($validator->getErrors(), true));
        self::assertInstanceOf(stdClass::class, $result);
        self::assertSame($exitCode, $result->exit_code);
        self::assertSame($command, $result->command);

        return $result;
    }
}
