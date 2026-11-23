<?php

declare(strict_types=1);

namespace Pressgres\Contracts;

use Pressgres\Contracts\Exception\PressgresException;

interface SchemaMigrator
{
    /**
     * Compute a deterministic plan from schema metadata without writing to the database.
     *
     * @throws PressgresException
     */
    public function plan(DesiredSchema $desired, CatalogSnapshot $current): MigrationPlan;
}
