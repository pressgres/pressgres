<?php

declare(strict_types=1);

namespace Pressgres\InstallerCli\Commands;

use Pressgres\InstallerCli\Output\Result;
use RuntimeException;
use stdClass;

final readonly class VersionCommand
{
    private const string VERSION = '0.1.0';

    private const array DEFAULT_HASHES = [
        'wordpress_archive_sha256' => null,
        'patchset_sha256' => null,
        'gutenberg_archive_sha256' => null,
        'composer_lock_sha256' => null,
    ];

    public function __construct(private string $manifestPath)
    {
    }

    public function run(): Result
    {
        $contents = @file_get_contents($this->manifestPath);
        if ($contents === false) {
            throw new RuntimeException('Unable to read the release manifest.');
        }

        $manifest = json_decode($contents, false, 512, JSON_THROW_ON_ERROR);
        if (!$manifest instanceof stdClass) {
            throw new RuntimeException('The release manifest must be an object.');
        }

        $wordpress = self::stringPin($manifest, 'wordpress_version', '/\A\d+\.\d+\.\d+\z/');
        $develop = self::stringPin($manifest, 'wordpress_develop_commit', '/\A[a-f0-9]{40}\z/');
        $gutenberg = self::stringPin($manifest, 'gutenberg_commit', '/\A[a-f0-9]{40}\z/');
        $valkey = self::stringPin($manifest, 'valkey_default_version', '/\A\d+\.\d+\.\d+\z/');
        $postgresql = $manifest->postgresql_minimum_major ?? null;
        if (!is_int($postgresql) || $postgresql < 18) {
            throw new RuntimeException('Invalid PostgreSQL floor in the release manifest.');
        }

        $hashes = self::artifactHashes($manifest->artifact_hashes ?? null);
        $lines = [
            'Pressgres ' . self::VERSION,
            'PHP ' . PHP_VERSION,
            "WordPress $wordpress (wordpress-develop: $develop)",
            "Gutenberg $gutenberg",
            "PostgreSQL $postgresql (minimum major)",
            "Valkey $valkey (default)",
            'Artifact hashes',
        ];
        foreach ($hashes as $artifact => $hash) {
            $lines[] = '  ' . $artifact . ': ' . ($hash ?? 'unavailable');
        }

        return Result::success('version', [
            'pressgres_version' => self::VERSION,
            'php_version' => PHP_VERSION,
            'wordpress_version' => $wordpress,
            'wordpress_develop_commit' => $develop,
            'gutenberg_commit' => $gutenberg,
            'postgresql_minimum_major' => $postgresql,
            'valkey_default_version' => $valkey,
            'artifact_hashes' => (object) $hashes,
        ], implode("\n", $lines));
    }

    private static function stringPin(stdClass $manifest, string $key, string $pattern): string
    {
        $value = $manifest->{$key} ?? null;
        if (!is_string($value) || preg_match($pattern, $value) !== 1) {
            throw new RuntimeException('Invalid version pin in the release manifest.');
        }

        return $value;
    }

    /** @return array<string, string|null> */
    private static function artifactHashes(mixed $values): array
    {
        $hashes = self::DEFAULT_HASHES;
        if ($values === null) {
            return $hashes;
        }
        if (!$values instanceof stdClass) {
            throw new RuntimeException('Artifact hashes must be an object.');
        }

        foreach (get_object_vars($values) as $artifact => $hash) {
            if (
                !is_string($artifact)
                || preg_match('/\A[a-z][a-z0-9_]*_sha256\z/', $artifact) !== 1
                || ($hash !== null && (!is_string($hash) || preg_match('/\A[a-f0-9]{64}\z/', $hash) !== 1))
            ) {
                throw new RuntimeException('Invalid artifact hash in the release manifest.');
            }
            $hashes[$artifact] = $hash;
        }

        return $hashes;
    }
}
