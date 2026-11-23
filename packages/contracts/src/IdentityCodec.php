<?php

declare(strict_types=1);

namespace Pressgres\Contracts;

use Pressgres\Contracts\Exception\InvalidUuid;

interface IdentityCodec
{
    /**
     * Accept only canonical lowercase UUIDv7 text.
     *
     * @throws InvalidUuid
     */
    public function decode(mixed $value): Uuid;

    public function encode(Uuid $uuid): string;
}
