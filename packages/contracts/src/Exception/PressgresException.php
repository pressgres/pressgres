<?php

declare(strict_types=1);

namespace Pressgres\Contracts\Exception;

use RuntimeException;
use Throwable;

class PressgresException extends RuntimeException
{
    /** The message and remediation must be safe for operator output. */
    public function __construct(
        public readonly ErrorCode $errorCode,
        string $message,
        public readonly string $remediation,
        ?Throwable $previous = null,
    ) {
        parent::__construct($message, $errorCode->exitCode()->value, $previous);
    }

    /** @param array<string, bool|float|int|string|null> $context Redacted context only. */
    public function diagnostic(
        string $correlationId,
        ?string $origin = null,
        ?string $sqlClass = null,
        ?string $sourceLocation = null,
        array $context = [],
    ): Diagnostic {
        return new Diagnostic(
            $this->errorCode,
            $this->getMessage(),
            $this->remediation,
            $correlationId,
            $origin,
            $sqlClass,
            $sourceLocation,
            $context,
        );
    }
}
