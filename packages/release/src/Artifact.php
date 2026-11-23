<?php

declare(strict_types=1);

namespace Pressgres\Release;

final readonly class Artifact
{
    public function __construct(
        public string $name,
        public string $url,
        public int $size,
        public string $sha256,
        public ?string $sha512 = null,
    ) {
    }
}
