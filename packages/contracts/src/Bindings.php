<?php

declare(strict_types=1);

namespace Pressgres\Contracts;

/** Bound values keyed by positional index or parameter name. Integers are for non-identity fields. */
final readonly class Bindings
{
    /** @param list<bool|float|int|string|Uuid|null>|array<string, bool|float|int|string|Uuid|null> $values */
    public function __construct(
        public array $values,
    ) {
    }
}
