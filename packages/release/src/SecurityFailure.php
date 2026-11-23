<?php

declare(strict_types=1);

namespace Pressgres\Release;

use Pressgres\Contracts\Exception\ErrorCode;
use Pressgres\Contracts\Exception\PressgresException;

final class SecurityFailure extends PressgresException
{
    public function __construct(string $message)
    {
        parent::__construct(
            ErrorCode::SecurityFailure,
            $message,
            'Obtain a trusted release and stage it in a private directory.',
        );
    }
}
