<?php

declare(strict_types=1);

namespace Pressgres\Contracts;

interface SqlCompatibilityEngine
{
    /** Translate supported MySQL semantics and reject unknown semantics without execution. */
    public function translate(QueryContext $query): TranslationResult|UnsupportedQuery;
}
