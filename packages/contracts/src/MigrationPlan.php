<?php

declare(strict_types=1);

namespace Pressgres\Contracts;

/** Ordered statements for a staged schema migration. */
final readonly class MigrationPlan
{
    /** @param list<SqlStatement> $statements */
    public function __construct(
        public string $targetVersion,
        public array $statements,
    ) {
    }
}
