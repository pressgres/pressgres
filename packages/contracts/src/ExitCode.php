<?php

declare(strict_types=1);

namespace Pressgres\Contracts;

enum ExitCode: int
{
    case Success = 0;
    case InternalError = 1;
    case InvalidInput = 2;
    case UnsupportedVersion = 3;
    case UnreachableDependency = 4;
    case SecurityFailure = 5;
    case Incompatible = 6;
    case MigrationFailure = 7;
    case VerificationFailure = 8;
    case RecoveryRequired = 9;
    case LockContention = 10;
}
