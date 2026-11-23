<?php

declare(strict_types=1);

namespace Pressgres\Contracts;

/** Rows preserve mapped column names. UUIDs in identity columns are canonical strings. */
final readonly class QueryResult
{
    /** @param list<array<string, mixed>> $rows */
    public function __construct(
        public array $rows,
        public int $affectedRows,
    ) {
    }
}
