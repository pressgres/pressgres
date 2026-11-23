<?php

declare(strict_types=1);

namespace Pressgres\Contracts;

use Pressgres\Contracts\Exception\Diagnostic;

/** A terminal compatibility failure with a redacted UNSUPPORTED_SQL diagnostic. */
final readonly class UnsupportedQuery
{
    public function __construct(
        public Diagnostic $diagnostic,
    ) {
    }
}
