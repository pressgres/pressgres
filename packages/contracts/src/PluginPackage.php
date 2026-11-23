<?php

declare(strict_types=1);

namespace Pressgres\Contracts;

/** A local plugin artifact and its expected identity. */
final readonly class PluginPackage
{
    public function __construct(
        public string $path,
        public string $slug,
        public string $version,
        public string $sha256,
    ) {
    }
}
