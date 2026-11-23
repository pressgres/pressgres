<?php

declare(strict_types=1);

namespace Pressgres\Contracts\Exception;

use JsonSerializable;

/** All fields must be safe for operator output. Use a correlation ID provided by the caller. */
final readonly class Diagnostic implements JsonSerializable
{
    /** @param array<string, bool|float|int|string|null> $context */
    public function __construct(
        public ErrorCode $code,
        public string $message,
        public string $remediation,
        public string $correlationId,
        public ?string $origin = null,
        public ?string $sqlClass = null,
        public ?string $sourceLocation = null,
        public array $context = [],
    ) {
    }

    /** @return array<string, int|string|null|array<string, bool|float|int|string|null>> */
    public function jsonSerialize(): array
    {
        return [
            'code' => $this->code->value,
            'exit_code' => $this->code->exitCode()->value,
            'message' => $this->message,
            'remediation' => $this->remediation,
            'correlation_id' => $this->correlationId,
            'origin' => $this->origin,
            'sql_class' => $this->sqlClass,
            'source_location' => $this->sourceLocation,
            'context' => $this->context,
        ];
    }
}
