<?php

declare(strict_types=1);

namespace Pressgres\Release\Tests;

use PHPUnit\Framework\Attributes\DataProvider;
use PHPUnit\Framework\TestCase;
use Pressgres\Contracts\ExitCode;
use Pressgres\Release\Ed25519SignatureVerifier;
use Pressgres\Release\SecurityFailure;

final class Ed25519SignatureVerifierTest extends TestCase
{
    #[DataProvider('publishedVectors')]
    public function testVerifiesRfc8032Vectors(string $key, string $message, string $signature): void
    {
        $verifier = new Ed25519SignatureVerifier(['rfc' => sodium_hex2bin($key)]);
        $verifier->verify($message, sodium_hex2bin($signature), 'rfc');
        $this->addToAssertionCount(1);
    }

    /** @return iterable<string, array{string, string, string}> */
    public static function publishedVectors(): iterable
    {
        // RFC 8032 section 7.1, tests 1 and 2. Only public test data is included.
        yield 'empty message' => [
            'd75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a',
            '',
            'e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e06522490155'
            . '5fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b',
        ];
        yield 'one byte' => [
            '3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c',
            "\x72",
            '92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da'
            . '085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00',
        ];
    }

    public function testRejectsUntrustedKeyEvenWithValidSignature(): void
    {
        $keys = sodium_crypto_sign_keypair();
        $verifier = new Ed25519SignatureVerifier(['current' => sodium_crypto_sign_publickey($keys)]);
        $this->expectException(SecurityFailure::class);
        $this->expectExceptionCode(ExitCode::SecurityFailure->value);
        $signature = sodium_crypto_sign_detached('release', sodium_crypto_sign_secretkey($keys));
        $verifier->verify('release', $signature, 'old');
    }

    public function testRejectsTruncatedSignature(): void
    {
        $keys = sodium_crypto_sign_keypair();
        $verifier = new Ed25519SignatureVerifier(['current' => sodium_crypto_sign_publickey($keys)]);
        $this->expectException(SecurityFailure::class);
        $verifier->verify('release', 'short', 'current');
    }

    public function testRejectsMalformedTrustRoot(): void
    {
        $this->expectException(SecurityFailure::class);
        new Ed25519SignatureVerifier(['current' => 'short']);
    }
}
