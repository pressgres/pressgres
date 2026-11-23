<?php

declare(strict_types=1);

namespace Pressgres\Contracts;

use Pressgres\Contracts\Exception\PressgresException;

interface PluginAnalyzer
{
    /**
     * Statically inspect a specific plugin artifact.
     *
     * @throws PressgresException
     */
    public function analyze(PluginPackage $package): CompatibilityReport;
}
