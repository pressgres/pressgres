<?php

declare(strict_types=1);

namespace Pressgres\Release;

final class ArtifactVerifier
{
    public function verifyArtifact(string $stagingRoot, Artifact $artifact): void
    {
        $absolute = $this->filePath($stagingRoot, $artifact->name);
        $digests = LocalFilesystem::hashFile($absolute, $artifact->size, $artifact->sha512 !== null);

        if (
            !hash_equals($artifact->sha256, $digests['sha256'])
            || ($artifact->sha512 !== null && !hash_equals($artifact->sha512, $digests['sha512'] ?? ''))
        ) {
            throw new VerificationFailure('A staged artifact digest differs from the release lockfile.');
        }
    }

    /** Verify a local file with a pinned SHA-256, for example a series or upstream.lock file. */
    public function verifyFile(string $stagingRoot, string $relativePath, string $sha256): void
    {
        $absolute = $this->filePath($stagingRoot, $relativePath);
        if (!hash_equals($sha256, LocalFilesystem::hashFile($absolute)['sha256'])) {
            throw new VerificationFailure('A staged file digest differs from its expected SHA-256.');
        }
    }

    private function filePath(string $stagingRoot, string $relativePath): string
    {
        $segments = LocalFilesystem::pathSegments($relativePath);
        $absolute = LocalFilesystem::root($stagingRoot) . array_shift($segments);
        foreach ($segments as $segment) {
            $type = LocalFilesystem::stat($absolute)['mode'] & LocalFilesystem::TYPE_MASK;
            if ($type !== LocalFilesystem::DIRECTORY) {
                throw new SecurityFailure('A staged release file has an unsafe parent path.');
            }
            $absolute .= '/' . $segment;
        }

        return $absolute;
    }
}
