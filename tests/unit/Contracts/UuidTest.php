<?php

declare(strict_types=1);

namespace Pressgres\Tests\Unit\Contracts;

use PHPUnit\Framework\Attributes\DataProvider;
use PHPUnit\Framework\TestCase;
use Pressgres\Contracts\Exception\ErrorCode;
use Pressgres\Contracts\Exception\InvalidUuid;
use Pressgres\Contracts\IdentityCodec;
use Pressgres\Contracts\Uuid;
use Pressgres\Contracts\UuidCodec;
use Stringable;

final class UuidTest extends TestCase
{
    public function testRoundTripPreservesBothSamePrefixCanaries(): void
    {
        $codec = $this->codec();
        $firstText = '019abcde-f0ab-7abc-8abc-123456789abc';
        $secondText = '019abcde-f0ab-7abc-8abc-123456789abd';
        $first = $codec->decode($firstText);
        $second = $codec->decode($secondText);

        self::assertSame($firstText, $codec->encode($first));
        self::assertSame($secondText, $codec->encode($second));
        self::assertSame($firstText, (string) $first);
        self::assertSame('"' . $firstText . '"', json_encode($first, JSON_THROW_ON_ERROR));
        self::assertSame('"' . $secondText . '"', json_encode($second, JSON_THROW_ON_ERROR));
        self::assertTrue($first->equals($codec->decode($firstText)));
        self::assertFalse($first->equals($second));
        self::assertEquals($first, unserialize(serialize($first), ['allowed_classes' => [Uuid::class]]));
    }

    #[DataProvider('invalidValues')]
    public function testDecodeRejectsInvalidInput(mixed $value): void
    {
        $this->expectException(InvalidUuid::class);
        $this->expectExceptionCode(ErrorCode::InvalidUuid->exitCode()->value);
        $this->expectExceptionMessage('Invalid UUIDv7.');

        $this->codec()->decode($value);
    }

    /** @return iterable<string, array{mixed}> */
    public static function invalidValues(): iterable
    {
        yield 'integer zero' => [0];
        yield 'string zero' => ['0'];
        yield 'empty string' => [''];
        yield 'null' => [null];
        yield 'false' => [false];
        yield 'nonzero truncated integer' => [19];
        yield 'truncated numeric string' => ['019'];
        yield 'array' => [['019abcde-f0ab-7abc-8abc-123456789abc']];
        yield 'stringable object' => [new class implements Stringable {
            public function __toString(): string
            {
                return '019abcde-f0ab-7abc-8abc-123456789abc';
            }
        }];
        yield 'uppercase' => ['019ABCDE-F0AB-7ABC-8ABC-123456789ABC'];
        yield 'nonhyphenated' => ['019abcdef0ab7abc8abc123456789abc'];
        yield 'nonhex' => ['019abcde-f0ab-7abc-8abc-123456789abg'];
        yield 'v4' => ['019abcde-f0ab-4abc-8abc-123456789abc'];
        yield 'non-RFC variant' => ['019abcde-f0ab-7abc-cabc-123456789abc'];
        yield 'nil UUID' => ['00000000-0000-0000-0000-000000000000'];
        yield 'leading space' => [' 019abcde-f0ab-7abc-8abc-123456789abc'];
        yield 'trailing newline' => ["019abcde-f0ab-7abc-8abc-123456789abc\n"];
    }

    public function testUnserializeRejectsAnInvalidStoredValue(): void
    {
        $this->expectException(InvalidUuid::class);

        $payload = sprintf('O:%d:"%s":1:{s:5:"value";i:0;}', strlen(Uuid::class), Uuid::class);
        unserialize($payload, ['allowed_classes' => [Uuid::class]]);
    }

    private function codec(): IdentityCodec
    {
        return new UuidCodec();
    }
}
