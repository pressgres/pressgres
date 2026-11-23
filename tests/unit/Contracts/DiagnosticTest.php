<?php

declare(strict_types=1);

namespace Pressgres\Tests\Unit\Contracts;

use PHPUnit\Framework\TestCase;
use Pressgres\Contracts\Exception\ErrorCode;
use Pressgres\Contracts\Exception\PressgresException;
use Pressgres\Contracts\ExitCode;
use RuntimeException;

final class DiagnosticTest extends TestCase
{
    public function testStableCodesCoverAllCliStatuses(): void
    {
        $expected = [
            'INTERNAL_ERROR' => 1,
            'INVALID_INPUT' => 2,
            'INVALID_UUID' => 2,
            'UNSUPPORTED_VERSION' => 3,
            'UNREACHABLE_DEPENDENCY' => 4,
            'SECURITY_FAILURE' => 5,
            'INCOMPATIBLE_PLUGIN' => 6,
            'UNSUPPORTED_SQL' => 6,
            'MIGRATION_FAILURE' => 7,
            'VERIFICATION_FAILURE' => 8,
            'RECOVERY_REQUIRED' => 9,
            'LOCK_CONTENTION' => 10,
        ];
        $actual = [];
        foreach (ErrorCode::cases() as $code) {
            $exception = new PressgresException($code, 'Request failed.', 'Check the request.');
            $actual[$code->value] = $exception->getCode();
            self::assertSame($code->exitCode()->value, $exception->getCode());
        }

        self::assertSame($expected, $actual);
        self::assertSame(0, ExitCode::Success->value);
        self::assertSame(range(0, 10), array_column(ExitCode::cases(), 'value'));
    }

    public function testDiagnosticJsonOmitsTheUnderlyingException(): void
    {
        $error = new PressgresException(
            ErrorCode::UnsupportedSql,
            'SQL pattern unsupported.',
            'Use a reviewed adapter.',
            new RuntimeException('Raw private query parameters'),
        );
        $diagnostic = $error->diagnostic(
            correlationId: 'request-42',
            origin: 'example-plugin',
            sqlClass: 'SELECT',
            sourceLocation: 'src/reader.php:12',
            context: ['rule' => 'unknown-expression'],
        );

        $json = json_encode($diagnostic, JSON_THROW_ON_ERROR);
        self::assertSame([
            'code' => 'UNSUPPORTED_SQL',
            'exit_code' => 6,
            'message' => 'SQL pattern unsupported.',
            'remediation' => 'Use a reviewed adapter.',
            'correlation_id' => 'request-42',
            'origin' => 'example-plugin',
            'sql_class' => 'SELECT',
            'source_location' => 'src/reader.php:12',
            'context' => ['rule' => 'unknown-expression'],
        ], json_decode($json, true, flags: JSON_THROW_ON_ERROR));
    }
}
