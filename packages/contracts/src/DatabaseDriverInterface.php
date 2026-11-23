<?php

declare(strict_types=1);

namespace Pressgres\Contracts;

use Pressgres\Contracts\Exception\PressgresException;

interface DatabaseDriverInterface
{
    /**
     * Execute a PostgreSQL statement with separately bound values.
     *
     * @throws PressgresException
     */
    public function execute(SqlStatement $statement, Bindings $bindings): QueryResult;
}
