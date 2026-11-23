<?php

declare(strict_types=1);

namespace Pressgres\Contracts;

enum PluginClassification: string
{
    case UuidSafe = 'UUID_SAFE';
    case SqlAdaptable = 'SQL_ADAPTABLE';
    case NeedsAdapter = 'NEEDS_ADAPTER';
    case Unsupported = 'UNSUPPORTED';
    case Unknown = 'UNKNOWN';
}
