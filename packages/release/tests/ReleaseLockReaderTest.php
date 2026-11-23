<?php

declare(strict_types=1);

namespace Pressgres\Release\Tests;

use PHPUnit\Framework\Attributes\DataProvider;
use PHPUnit\Framework\TestCase;
use Pressgres\Contracts\ExitCode;
use Pressgres\Release\Ed25519SignatureVerifier;
use Pressgres\Release\ReleaseLock;
use Pressgres\Release\ReleaseLockReader;
use Pressgres\Release\SecurityFailure;
use Pressgres\Release\VerificationFailure;

final class ReleaseLockReaderTest extends TestCase
{
    public function testReadsSignedReleasePins(): void
    {
        $lock = self::readSigned(self::fixture());

        self::assertSame('0.1.0-preview.1', $lock->pressgresVersion);
        self::assertSame('7.1.5', $lock->wordpressTag);
        self::assertSame('984163c92ef66b6186538ecf01bacb97fc097541', $lock->wordpressCommit);
        self::assertSame('89408c2b9bd944575dfa9039bc6870da1c8f56cb', $lock->gutenbergCommit);
        self::assertSame(['php' => '8.4.27', 'postgresql' => '18.6', 'valkey' => '9.2.0'], $lock->runtime);
        foreach (['wordpress', 'gutenberg'] as $component) {
            self::assertSame(
                hash('sha256', "synthetic $component series\n"),
                $lock->patchSeries[$component]['series_sha256'],
            );
            self::assertSame(
                hash('sha256', "synthetic $component upstream_lock\n"),
                $lock->patchSeries[$component]['upstream_lock_sha256'],
            );
        }
        self::assertCount(1, $lock->artifacts);
        $artifact = $lock->artifacts[0];
        self::assertSame('core.tar.gz', $artifact->name);
        self::assertSame('https://releases.example.invalid/core.tar.gz', $artifact->url);
        self::assertSame(16, $artifact->size);
        self::assertSame(hash('sha256', "release fixture\n"), $artifact->sha256);
        self::assertSame(hash('sha512', "release fixture\n"), $artifact->sha512);
    }

    public function testRejectsChangedBytesEvenWhenJsonIsEquivalent(): void
    {
        $this->expectException(SecurityFailure::class);
        $this->expectExceptionCode(ExitCode::SecurityFailure->value);

        $json = self::fixture();
        $keys = sodium_crypto_sign_keypair();
        $reader = new ReleaseLockReader(
            new Ed25519SignatureVerifier(['preview' => sodium_crypto_sign_publickey($keys)]),
        );

        $signature = sodium_crypto_sign_detached($json, sodium_crypto_sign_secretkey($keys));
        $reader->readSigned($json . "\n", $signature, 'preview');
    }

    public function testRejectsSignedUnknownVersion(): void
    {
        $this->expectException(VerificationFailure::class);
        $this->expectExceptionCode(ExitCode::VerificationFailure->value);
        $this->expectExceptionMessage('version is missing or unsupported');

        self::readSigned(str_replace('"lockfile_version": 1', '"lockfile_version": 2', self::fixture()));
    }

    #[DataProvider('invalidFieldEdits')]
    public function testRejectsMalformedSignedMetadata(string $from, string $to): void
    {
        $this->expectException(VerificationFailure::class);
        $this->expectExceptionCode(ExitCode::VerificationFailure->value);

        $fixture = self::fixture();
        self::assertStringContainsString($from, $fixture);
        self::readSigned(str_replace($from, $to, $fixture));
    }

    /** @return iterable<string, array{string, string}> */
    public static function invalidFieldEdits(): iterable
    {
        yield 'duplicate escaped member' => ['"size": 16', '"s\u0069ze": 11, "size": 16'];
        yield 'unknown member' => ['"size": 16', '"size": 16, "unknown": true'];
        yield 'invalid hash' => ['"sha256": "', '"sha256": "x'];
        yield 'placeholder patch digest' => ['"series_sha256": "', '"series_sha256": "null'];
        yield 'non-exact Postgres pin' => ['"18.6"', '"18"'];
        yield 'non-exact PHP pin' => ['"8.4.27"', '"8.4.x"'];
        yield 'artifact traversal' => ['"core.tar.gz"', '"../core.tar.gz"'];
        yield 'trailing newline in name' => ['"core.tar.gz"', '"core.tar.gz\n"'];
        yield 'insecure URL' => ['https://', 'http://'];
        yield 'URL with userinfo' => ['https://', 'https://someone@'];
        yield 'fractional size' => ['"size": 16', '"size": 16.2'];
        yield 'size outside interoperable range' => ['"size": 16', '"size": 9007199254740992'];
    }

    public function testRejectsDuplicateArtifactNames(): void
    {
        $this->expectException(VerificationFailure::class);
        $this->expectExceptionMessage('duplicate artifact name');

        $json = self::fixture();
        $start = strpos($json, '[');
        $end = strpos($json, ']');
        self::assertIsInt($start);
        self::assertIsInt($end);
        $artifact = substr($json, $start + 1, $end - $start - 1);
        self::readSigned(substr_replace($json, $artifact . ',' . $artifact, $start + 1, $end - $start - 1));
    }

    private static function fixture(): string
    {
        $json = file_get_contents(__DIR__ . '/fixtures/release-lock-v1.json');
        self::assertIsString($json);

        return $json;
    }

    private static function readSigned(string $json): ReleaseLock
    {
        $keys = sodium_crypto_sign_keypair();
        $reader = new ReleaseLockReader(
            new Ed25519SignatureVerifier(['preview' => sodium_crypto_sign_publickey($keys)]),
        );

        return $reader->readSigned(
            $json,
            sodium_crypto_sign_detached($json, sodium_crypto_sign_secretkey($keys)),
            'preview',
        );
    }
}
