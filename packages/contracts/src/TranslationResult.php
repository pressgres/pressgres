<?php

declare(strict_types=1);

namespace Pressgres\Contracts;

/** Translated PostgreSQL text and its remapped bindings. */
final readonly class TranslationResult
{
    public function __construct(
        public SqlStatement $statement,
        public Bindings $bindings,
    ) {
    }
}
