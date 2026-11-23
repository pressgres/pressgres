<?php

declare(strict_types=1);

namespace Pressgres\Contracts;

final readonly class PluginFinding
{
    public function __construct(
        public string $message,
        public string $relativePath,
        public int $line,
    ) {
    }
}
