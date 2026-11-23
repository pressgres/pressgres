<?php

declare(strict_types=1);

namespace Pressgres\Release;

final readonly class ReleaseLock
{
    /**
     * @param array{wordpress: array{series_sha256: string, upstream_lock_sha256: string},
     *     gutenberg: array{series_sha256: string, upstream_lock_sha256: string}} $patchSeries
     * @param array{php: string, postgresql: string, valkey: string} $runtime
     * @param list<Artifact> $artifacts
     */
    public function __construct(
        public string $pressgresVersion,
        public string $wordpressTag,
        public string $wordpressCommit,
        public string $gutenbergCommit,
        public array $patchSeries,
        public array $runtime,
        public array $artifacts,
    ) {
    }
}
