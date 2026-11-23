<?php

declare(strict_types=1);

namespace Pressgres\InstallerCli\Tests;

use JsonSchema\Constraints\Constraint;
use JsonSchema\Validator;
use PHPUnit\Framework\Attributes\DataProvider;
use PHPUnit\Framework\TestCase;
use Pressgres\InstallerCli\Application;
use Pressgres\InstallerCli\Commands\VersionCommand;
use stdClass;

final class VersionTest extends TestCase
{
    private const string MANIFEST = __DIR__ . '/../release/manifest.json';

    public function testHumanSnapshot(): void
    {
        [$code, $stdout, $stderr] = self::runBinary(['version']);

        self::assertSame(0, $code);
        self::assertSame('', $stderr);
        self::assertSnapshot('version.txt', $stdout);
    }

    public function testJsonSnapshotAndSchema(): void
    {
        [$code, $stdout, $stderr] = self::runBinary(['--format=json', 'version', '--no-interaction']);

        self::assertSame(0, $code);
        self::assertSame('', $stderr);
        self::assertSnapshot('version.json', $stdout);
        self::assertValidEnvelope($stdout);
    }

    /** @param list<string> $arguments */
    #[DataProvider('invalidInvocations')]
    public function testInvalidUsage(array $arguments, ?string $command, string $message): void
    {
        [$code, $stdout, $stderr] = self::runBinary([...$arguments, '--format=json']);

        self::assertSame(2, $code);
        self::assertSame('', $stderr);
        $result = self::assertValidEnvelope($stdout);
        self::assertSame($command, $result->command);
        self::assertError($result, 2, 'INVALID_INPUT', $message);
        self::assertStringNotContainsString('secret-value', $stdout);
    }

    /** @return iterable<string, array{list<string>, ?string, string}> */
    public static function invalidInvocations(): iterable
    {
        yield 'missing command' => [[], null, 'A command is required.'];
        yield 'unknown command' => [['secret-value'], null, 'Unknown command.'];
        yield 'bad option' => [['version', '--secret=secret-value'], 'version', 'Invalid option.'];
        yield 'bad format' => [['version', '--format=yaml'], 'version', 'Invalid option.'];
        yield 'conflicting format' => [['--format=human', 'version'], 'version', 'Invalid option.'];
        yield 'unexpected argument' => [['version', 'secret-value'], 'version', 'Unexpected argument.'];
    }

    public function testHumanUsageErrorUsesStderr(): void
    {
        [$code, $stdout, $stderr] = self::runBinary(['version', '--format=yaml']);

        self::assertSame(2, $code);
        self::assertSame('', $stdout);
        self::assertStringStartsWith("[INVALID_INPUT] Invalid option.\n", $stderr);
    }

    public function testMissingManifestProducesCorrelatedInternalError(): void
    {
        [$code, $stdout, $stderr] = self::runWithManifest(self::MANIFEST . '.missing', ['--format=json']);

        self::assertSame(1, $code);
        self::assertSame('', $stderr);
        $result = self::assertValidEnvelope($stdout);
        self::assertError($result, 1, 'INTERNAL_ERROR', 'An unexpected CLI error occurred.');
        self::assertStringNotContainsString(self::MANIFEST, $stdout);
    }

    public function testMalformedManifestProducesCorrelatedHumanError(): void
    {
        [$code, $stdout, $stderr] = self::runWithManifest('data:application/json,{secret-value', []);

        self::assertSame(1, $code);
        self::assertSame('', $stdout);
        self::assertMatchesRegularExpression('/Correlation ID: [a-f0-9]{32}\n\z/', $stderr);
        self::assertStringNotContainsString('secret-value', $stderr);
    }

    public function testPresentHashesAreReportedAndOmittedHashesFallBackToNull(): void
    {
        $contents = file_get_contents(self::MANIFEST);
        self::assertIsString($contents);
        $manifest = json_decode($contents, false, 512, JSON_THROW_ON_ERROR);
        self::assertInstanceOf(stdClass::class, $manifest);
        $hash = hash('sha256', 'test artifact');
        $manifest->artifact_hashes = (object) ['wordpress_archive_sha256' => $hash];
        $fixture = 'data:application/json;base64,' . base64_encode(json_encode($manifest, JSON_THROW_ON_ERROR));
        [$code, $stdout, $stderr] = self::runWithManifest($fixture, ['--format=json']);

        self::assertSame(0, $code);
        self::assertSame('', $stderr);
        $result = self::assertValidEnvelope($stdout);
        self::assertInstanceOf(stdClass::class, $result->data);
        self::assertInstanceOf(stdClass::class, $result->data->artifact_hashes);
        self::assertSame($hash, $result->data->artifact_hashes->wordpress_archive_sha256);
        self::assertNull($result->data->artifact_hashes->patchset_sha256);
    }

    private static function assertSnapshot(string $name, string $output): void
    {
        $snapshot = file_get_contents(__DIR__ . '/snapshots/' . $name);
        self::assertIsString($snapshot);
        self::assertSame(str_replace('{{PHP_VERSION}}', PHP_VERSION, $snapshot), $output);
    }

    private static function assertValidEnvelope(string $output): stdClass
    {
        $document = json_decode($output, false, 512, JSON_THROW_ON_ERROR);
        $schema = file_get_contents(__DIR__ . '/../schemas/cli-v1.json');
        self::assertIsString($schema);

        $validator = new Validator();
        $validator->validate(
            $document,
            json_decode($schema, false, 512, JSON_THROW_ON_ERROR),
            Constraint::CHECK_MODE_STRICT,
        );
        self::assertTrue($validator->isValid(), var_export($validator->getErrors(), true));
        self::assertInstanceOf(stdClass::class, $document);

        return $document;
    }

    private static function assertError(stdClass $result, int $exitCode, string $code, string $message): void
    {
        self::assertSame('error', $result->status);
        self::assertSame($exitCode, $result->exit_code);
        self::assertIsString($result->correlation_id);
        self::assertMatchesRegularExpression('/\A[a-f0-9]{32}\z/', $result->correlation_id);
        self::assertIsArray($result->diagnostics);
        self::assertCount(1, $result->diagnostics);
        $diagnostic = $result->diagnostics[0];
        self::assertInstanceOf(stdClass::class, $diagnostic);
        self::assertSame($code, $diagnostic->code);
        self::assertSame($exitCode, $diagnostic->exit_code);
        self::assertSame($message, $diagnostic->message);
        self::assertSame($result->correlation_id, $diagnostic->correlation_id);
    }

    /**
     * @param list<string> $arguments
     * @return array{int, string, string}
     */
    private static function runBinary(array $arguments): array
    {
        $process = proc_open(
            [PHP_BINARY, dirname(__DIR__, 3) . '/vendor/bin/wps', ...$arguments],
            [1 => ['pipe', 'w'], 2 => ['pipe', 'w']],
            $pipes,
        );
        self::assertIsResource($process);
        $stdout = stream_get_contents($pipes[1]);
        $stderr = stream_get_contents($pipes[2]);
        fclose($pipes[1]);
        fclose($pipes[2]);
        $code = proc_close($process);
        self::assertIsString($stdout);
        self::assertIsString($stderr);

        return [$code, $stdout, $stderr];
    }

    /**
     * @param list<string> $arguments
     * @return array{int, string, string}
     */
    private static function runWithManifest(string $manifestPath, array $arguments): array
    {
        $stdout = fopen('php://memory', 'w+');
        $stderr = fopen('php://memory', 'w+');
        self::assertIsResource($stdout);
        self::assertIsResource($stderr);

        try {
            $application = new Application(new VersionCommand($manifestPath));
            $code = $application->run(['version', ...$arguments], $stdout, $stderr);
            rewind($stdout);
            rewind($stderr);
            $output = stream_get_contents($stdout);
            $error = stream_get_contents($stderr);
            self::assertIsString($output);
            self::assertIsString($error);

            return [$code->value, $output, $error];
        } finally {
            fclose($stdout);
            fclose($stderr);
        }
    }
}
