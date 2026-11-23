<?php

declare(strict_types=1);

namespace Pressgres\Contracts;

use SensitiveParameter;

final class UuidCodec implements IdentityCodec
{
    public function decode(#[SensitiveParameter] mixed $value): Uuid
    {
        return Uuid::fromString($value);
    }

    public function encode(Uuid $uuid): string
    {
        return (string) $uuid;
    }
}
