<?php

declare(strict_types=1);

namespace Pressgres\Contracts\Exception;

final class InvalidUuid extends PressgresException
{
    public function __construct()
    {
        parent::__construct(
            ErrorCode::InvalidUuid,
            'Invalid UUIDv7.',
            'Provide a canonical lowercase, hyphenated UUIDv7.',
        );
    }
}
