<?php

declare(strict_types=1);

namespace Pressgres\Release;

/** @internal Filesystem operations for a caller-owned, quiescent staging directory. */
final class LocalFilesystem
{
    public const TYPE_MASK = 0170000;
    public const DIRECTORY = 0040000;
    public const FILE = 0100000;
    public const SYMLINK = 0120000;

    /** Return the canonical local root with a trailing slash. */
    public static function root(string $directory): string
    {
        if ($directory === '' || str_contains($directory, "\0") || str_contains($directory, '://')) {
            throw new SecurityFailure('The release staging root must be a local directory.');
        }

        clearstatcache(true);
        $path = rtrim($directory, '/');
        $path = $path === '' ? '/' : $path;
        if (is_link($path)) {
            throw new SecurityFailure('The release staging root is a symbolic link.');
        }

        $root = realpath($path);
        if ($root === false || !is_dir($root)) {
            throw new VerificationFailure('The release staging directory is unavailable.');
        }

        return rtrim($root, '/') . '/';
    }

    /** @return non-empty-list<string> */
    public static function pathSegments(string $relative): array
    {
        if (str_contains($relative, '\\') || preg_match('~[\\x00-\\x1f\\x7f:]~', $relative) !== 0) {
            throw new SecurityFailure('A release path contains forbidden characters.');
        }

        $segments = explode('/', $relative);
        foreach ($segments as $segment) {
            if ($segment === '' || $segment === '.' || $segment === '..') {
                throw new SecurityFailure('A release path must use clean relative segments.');
            }
        }

        return $segments;
    }

    /** @return array{dev: int, ino: int, mode: int, size: int, mtime: int, ctime: int} */
    public static function stat(string $absolute): array
    {
        $stat = @lstat($absolute);
        if ($stat === false) {
            throw new VerificationFailure('A staged release entry is unavailable.');
        }

        return self::fileMetadata($stat);
    }

    /**
     * @param array{dev: int, ino: int, mode: int, size: int, mtime: int, ctime: int} $stat
     * @return array{dev: int, ino: int, mode: int, size: int, mtime: int, ctime: int}
     */
    private static function fileMetadata(array $stat): array
    {
        return [
            'dev' => $stat['dev'],
            'ino' => $stat['ino'],
            'mode' => $stat['mode'],
            'size' => $stat['size'],
            'mtime' => $stat['mtime'],
            'ctime' => $stat['ctime'],
        ];
    }

    /** @return array{sha256: string, sha512: ?string} */
    public static function hashFile(
        string $absolute,
        ?int $expectedSize = null,
        bool $includeSha512 = false,
    ): array {
        $entry = self::stat($absolute);
        if (($entry['mode'] & self::TYPE_MASK) !== self::FILE || ($entry['mode'] & 07000) !== 0) {
            throw new SecurityFailure('A staged release file has an unsafe type or mode.');
        }

        $stream = @fopen($absolute, 'rb');
        if ($stream === false) {
            throw new VerificationFailure('A staged release file could not be opened.');
        }

        try {
            $before = fstat($stream);
            if ($before === false || self::fileMetadata($before) !== $entry) {
                throw new VerificationFailure('A staged release file changed while being opened.');
            }
            if ($expectedSize !== null && $before['size'] !== $expectedSize) {
                throw new VerificationFailure('The staged artifact size differs from the release lockfile.');
            }

            $sha256 = hash_init('sha256');
            $sha512 = $includeSha512 ? hash_init('sha512') : null;
            $size = 0;
            while (!feof($stream)) {
                $chunk = @fread($stream, 1_048_576);
                if ($chunk === false || ($chunk === '' && !feof($stream))) {
                    throw new VerificationFailure('A staged release file could not be read completely.');
                }
                $size += strlen($chunk);
                if ($size > $before['size']) {
                    throw new VerificationFailure('A staged release file grew during verification.');
                }
                hash_update($sha256, $chunk);
                if ($sha512 !== null) {
                    hash_update($sha512, $chunk);
                }
            }

            $after = fstat($stream);
            if ($size !== $before['size'] || $after === false || self::fileMetadata($after) !== $entry) {
                throw new VerificationFailure('A staged release file changed during verification.');
            }

            return [
                'sha256' => hash_final($sha256),
                'sha512' => $sha512 === null ? null : hash_final($sha512),
            ];
        } finally {
            fclose($stream);
        }
    }
}
