<?php

declare(strict_types=1);

namespace Pressgres\Contracts;

use Pressgres\Contracts\Exception\PressgresException;

/** @phpstan-type StepData array<string, mixed> */
interface InstallerStep
{
    /**
     * Compute a deterministic plan from resolved non-secret inputs without mutating the target.
     *
     * @param StepData $inputs
     * @throws PressgresException
     */
    public function plan(array $inputs): InstallerStepPlan;

    /**
     * Apply the recorded plan and return non-secret artifacts for the installer to checkpoint.
     *
     * @return StepData
     * @throws PressgresException
     */
    public function apply(InstallerStepPlan $plan): array;

    /**
     * Verify the applied plan using its checkpoint. Signal a failed verification with an exception.
     *
     * @param StepData $checkpoint
     * @throws PressgresException
     */
    public function verify(InstallerStepPlan $plan, array $checkpoint): void;

    /**
     * Attempt recorded compensating actions and signal failures that require recovery.
     *
     * @param StepData $checkpoint
     * @throws PressgresException
     */
    public function compensate(InstallerStepPlan $plan, array $checkpoint): void;
}
