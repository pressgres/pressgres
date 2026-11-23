<?php

declare(strict_types=1);

namespace Pressgres\Release;

final class TreeManifest
{
    public function digest(string $directory): string
    {
        $root = LocalFilesystem::root($directory);
        $records = [];
        $pending = [''];

        while ($pending !== []) {
            $prefix = array_pop($pending);
            $entries = @scandir($root . $prefix, SCANDIR_SORT_NONE);
            if ($entries === false) {
                throw new VerificationFailure('A staged directory could not be listed.');
            }

            foreach ($entries as $name) {
                if ($name === '.' || $name === '..') {
                    continue;
                }
                $relative = $prefix . $name;
                LocalFilesystem::pathSegments($relative);
                $mode = LocalFilesystem::stat($root . $relative)['mode'];
                $type = $mode & LocalFilesystem::TYPE_MASK;

                if (($mode & 07000) !== 0) {
                    throw new SecurityFailure('A staged tree contains a privileged permission bit.');
                }

                $records[$relative] = match ($type) {
                    LocalFilesystem::DIRECTORY => "040000\t-",
                    LocalFilesystem::FILE => (($mode & 0111) === 0 ? '100644' : '100755') . "\t"
                        . LocalFilesystem::hashFile($root . $relative)['sha256'],
                    LocalFilesystem::SYMLINK => "120000\t" . $this->linkTarget($root, $relative),
                    default => throw new SecurityFailure('A staged tree contains an unsafe filesystem entry.'),
                };
                if ($type === LocalFilesystem::DIRECTORY) {
                    $pending[] = $relative . '/';
                }
            }
        }

        ksort($records, SORT_STRING);
        $hash = hash_init('sha256');
        hash_update($hash, "pressgres-tree-v1\n");
        foreach ($records as $path => $record) {
            hash_update($hash, bin2hex((string) $path) . "\t" . $record . "\n");
        }

        return hash_final($hash);
    }

    public function verify(string $directory, string $sha256): void
    {
        if (!hash_equals($sha256, $this->digest($directory))) {
            throw new VerificationFailure('The staged tree digest differs from its expected SHA-256.');
        }
    }

    private function linkTarget(string $root, string $relative): string
    {
        $absolute = $root . $relative;
        $target = @readlink($absolute);
        if ($target === false) {
            throw new SecurityFailure('A staged symbolic link could not be inspected.');
        }
        LocalFilesystem::pathSegments($target);

        $resolved = realpath($absolute);
        if ($resolved === false || !str_starts_with($resolved, $root)) {
            throw new SecurityFailure('A staged symbolic link is broken or escapes the staging root.');
        }

        return bin2hex($target);
    }
}
