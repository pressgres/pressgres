<?php

declare(strict_types=1);

namespace Pressgres\Contracts;

/** Observed database catalog metadata, keyed by qualified object name. */
final readonly class CatalogSnapshot
{
    /** @param array<string, array<string, mixed>> $objects */
    public function __construct(
        public array $objects,
    ) {
    }
}
