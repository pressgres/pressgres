<?php

declare(strict_types=1);

namespace Pressgres\Release;

interface SignatureVerifier
{
    /**
     * Verify a detached signature over the exact supplied bytes using an independently configured trust root.
     *
     * @throws SecurityFailure If authenticity cannot be established.
     */
    public function verify(string $bytes, string $signature, string $keyId): void;
}
