<?php

declare(strict_types=1);

namespace Pressgres\Contracts;

/** Legacy SQL and its metadata before translation. */
final readonly class QueryContext
{
    public function __construct(
        public SqlStatement $statement,
        public Bindings $bindings,
        public CatalogSnapshot $catalog,
        public ?string $origin = null,
        public ?string $sourceLocation = null,
    ) {
    }
}
