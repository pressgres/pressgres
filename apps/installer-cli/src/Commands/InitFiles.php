<?php

declare(strict_types=1);

namespace Pressgres\InstallerCli\Commands;

use Pressgres\Contracts\Exception\ErrorCode;
use Pressgres\Contracts\Exception\PressgresException;

final readonly class InitFiles
{
    private const string ENV_FILE = '.env.example';

    private string $directory;
    private string $configPath;
    private string $envPath;

    public function __construct(string $output)
    {
        $directory = str_contains($output, "\0") ? false : realpath(dirname($output));
        $name = basename($output);
        if (
            $directory === false || !is_dir($directory) || str_ends_with($output, '/')
            || in_array(strtolower($name), ['', '.', '..', self::ENV_FILE], true)
        ) {
            throw new PressgresException(
                ErrorCode::InvalidInput,
                'Invalid configuration output path.',
                'Choose a file in an existing directory, distinct from .env.example.',
            );
        }

        $this->directory = $directory;
        $this->configPath = $directory . '/' . $name;
        $this->envPath = $directory . '/' . self::ENV_FILE;
    }

    public function checkDestinations(bool $force): void
    {
        foreach ([$this->configPath, $this->envPath] as $path) {
            clearstatcache(true, $path);
            if (is_link($path) || (file_exists($path) && !is_file($path))) {
                throw new PressgresException(
                    ErrorCode::InvalidInput,
                    'An output path is a symlink or is not a regular file.',
                    'Choose another output directory or filename.',
                );
            }
            if (!$force && file_exists($path)) {
                throw new PressgresException(
                    ErrorCode::InvalidInput,
                    'An output file already exists.',
                    'Choose another output directory or pass --force to replace existing output files.',
                );
            }
        }
    }

    public function write(string $yaml, string $env, bool $force): void
    {
        // Serialize wps writers in the same directory without leaving a lock file behind.
        $directoryHandle = @fopen($this->directory, 'r');
        if ($directoryHandle === false) {
            throw self::writeFailed();
        }

        $temporary = [];
        try {
            if (!@flock($directoryHandle, LOCK_EX)) {
                throw self::writeFailed();
            }
            $this->checkDestinations($force);

            $config = $this->stage($yaml, 0600, $temporary);
            $environment = $this->stage($env, 0644, $temporary);
            $backup = null;
            if ($force && is_file($this->configPath)) {
                $backup = $this->temporaryPath($temporary);
                if (!@unlink($backup) || !@link($this->configPath, $backup)) {
                    throw self::writeFailed();
                }
            }

            $this->publish($config, $this->configPath, $force);
            try {
                $this->publish($environment, $this->envPath, $force);
            } catch (PressgresException $exception) {
                $restored = $backup === null
                    ? @unlink($this->configPath)
                    : @rename($backup, $this->configPath);
                if (!$restored) {
                    // Preserve the original inode for manual recovery if rollback fails.
                    $temporary = array_diff($temporary, [$backup]);
                    throw new PressgresException(
                        ErrorCode::RecoveryRequired,
                        'Could not restore the configuration after an output write failed.',
                        'Recover the original from the .wps-init-* backup in the output directory if present.',
                    );
                }
                throw $exception;
            }
        } finally {
            foreach ($temporary as $path) {
                if (file_exists($path)) {
                    @unlink($path);
                }
            }
            fclose($directoryHandle);
        }
    }

    /** @param array<string> $temporary */
    private function stage(string $contents, int $mode, array &$temporary): string
    {
        $path = $this->temporaryPath($temporary);
        if (@file_put_contents($path, $contents) !== strlen($contents) || !@chmod($path, $mode)) {
            throw self::writeFailed();
        }

        return $path;
    }

    /** @param array<string> $temporary */
    private function temporaryPath(array &$temporary): string
    {
        $path = @tempnam($this->directory, '.wps-init-');
        if ($path === false) {
            throw self::writeFailed();
        }
        $temporary[] = $path;
        if (dirname($path) !== $this->directory) {
            throw self::writeFailed();
        }

        return $path;
    }

    private function publish(string $temporary, string $destination, bool $force): void
    {
        // link() publishes an already complete inode and refuses a destination created by another process.
        if ($force ? @rename($temporary, $destination) : @link($temporary, $destination)) {
            return;
        }

        $this->checkDestinations($force);
        throw self::writeFailed();
    }

    private static function writeFailed(): PressgresException
    {
        return new PressgresException(
            ErrorCode::InvalidInput,
            'Unable to write the configuration output files.',
            'Check directory permissions and available space.',
        );
    }
}
