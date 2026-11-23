<?php

declare(strict_types=1);

namespace Pressgres\Release;

use Pressgres\Contracts\Exception\ErrorCode;
use Pressgres\Contracts\Exception\PressgresException;

final class VerificationFailure extends PressgresException
{
    public function __construct(string $message)
    {
        parent::__construct(
            ErrorCode::VerificationFailure,
            $message,
            'Check the release metadata and restage the expected artifacts.',
        );
    }
}
