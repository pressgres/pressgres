<?php

declare(strict_types=1);

namespace Pressgres\Release;

final readonly class Ed25519SignatureVerifier implements SignatureVerifier
{
    /** @param array<string, string> $trustedKeys Key IDs mapped to raw 32-byte public keys. */
    public function __construct(private array $trustedKeys)
    {
        foreach ($trustedKeys as $publicKey) {
            if (strlen($publicKey) !== SODIUM_CRYPTO_SIGN_PUBLICKEYBYTES) {
                throw new SecurityFailure('The release trust root contains an invalid Ed25519 public key.');
            }
        }
    }

    public function verify(string $bytes, string $signature, string $keyId): void
    {
        $publicKey = $this->trustedKeys[$keyId] ?? null;
        if ($publicKey === null || $publicKey === '') {
            throw new SecurityFailure('The release signing key is not trusted.');
        }

        if (
            strlen($signature) !== SODIUM_CRYPTO_SIGN_BYTES
            || !sodium_crypto_sign_verify_detached($signature, $bytes, $publicKey)
        ) {
            throw new SecurityFailure('The release signature is invalid.');
        }
    }
}
