<?php

declare(strict_types=1);

namespace Pressgres\Contracts;

/** Non-secret data the installer records for a versioned step. */
final readonly class InstallerStepPlan
{
    /** @param array<string, mixed> $inputs */
    public function __construct(
        public string $stepId,
        public string $version,
        public array $inputs,
    ) {
    }
}
