<?php

declare(strict_types=1);

namespace Pressgres\Contracts;

/** Versioned desired schema metadata, keyed by qualified object name. */
final readonly class DesiredSchema
{
    /** @param array<string, array<string, mixed>> $objects */
    public function __construct(
        public string $version,
        public array $objects,
    ) {
    }
}
