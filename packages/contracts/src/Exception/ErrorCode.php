<?php

declare(strict_types=1);

namespace Pressgres\Contracts\Exception;

use Pressgres\Contracts\ExitCode;

enum ErrorCode: string
{
    case InternalError = 'INTERNAL_ERROR';
    case InvalidInput = 'INVALID_INPUT';
    case InvalidUuid = 'INVALID_UUID';
    case UnsupportedVersion = 'UNSUPPORTED_VERSION';
    case UnreachableDependency = 'UNREACHABLE_DEPENDENCY';
    case SecurityFailure = 'SECURITY_FAILURE';
    case IncompatiblePlugin = 'INCOMPATIBLE_PLUGIN';
    case UnsupportedSql = 'UNSUPPORTED_SQL';
    case MigrationFailure = 'MIGRATION_FAILURE';
    case VerificationFailure = 'VERIFICATION_FAILURE';
    case RecoveryRequired = 'RECOVERY_REQUIRED';
    case LockContention = 'LOCK_CONTENTION';

    public function exitCode(): ExitCode
    {
        return match ($this) {
            self::InternalError => ExitCode::InternalError,
            self::InvalidInput, self::InvalidUuid => ExitCode::InvalidInput,
            self::UnsupportedVersion => ExitCode::UnsupportedVersion,
            self::UnreachableDependency => ExitCode::UnreachableDependency,
            self::SecurityFailure => ExitCode::SecurityFailure,
            self::IncompatiblePlugin, self::UnsupportedSql => ExitCode::Incompatible,
            self::MigrationFailure => ExitCode::MigrationFailure,
            self::VerificationFailure => ExitCode::VerificationFailure,
            self::RecoveryRequired => ExitCode::RecoveryRequired,
            self::LockContention => ExitCode::LockContention,
        };
    }
}
