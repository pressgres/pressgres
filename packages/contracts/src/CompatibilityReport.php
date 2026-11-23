<?php

declare(strict_types=1);

namespace Pressgres\Contracts;

/** Static scan findings for one exact artifact. */
final readonly class CompatibilityReport
{
    /** @param list<PluginFinding> $findings */
    public function __construct(
        public PluginPackage $package,
        public PluginClassification $classification,
        public array $findings,
    ) {
    }
}
