<?php

declare(strict_types=1);

namespace Pressgres\Contracts;

/** SQL text with placeholders for bound values. */
final readonly class SqlStatement
{
    public function __construct(
        public string $sql,
    ) {
    }
}
