<?php

declare(strict_types=1);

namespace Pressgres\InstallerCli\Commands;

use Pressgres\Contracts\Exception\ErrorCode;
use Pressgres\Contracts\Exception\PressgresException;
use Pressgres\InstallerCli\Config\ConfigValidator;
use Pressgres\InstallerCli\Output\Result;

final readonly class ConfigValidateCommand
{
    public const string NAME = 'config validate';

    public function __construct(private ConfigValidator $validator = new ConfigValidator())
    {
    }

    public function run(string $path): Result
    {
        $localPath = str_contains($path, "\0") ? false : realpath($path);
        $yaml = $localPath !== false && is_file($localPath)
            ? @file_get_contents($localPath, length: ConfigValidator::MAX_BYTES + 1)
            : false;
        if ($yaml === false) {
            throw new PressgresException(
                ErrorCode::InvalidInput,
                'Unable to read the configuration file.',
                'Provide a readable local YAML file with --config.',
            );
        }

        $diagnostics = $this->validator->validate($yaml);
        if ($diagnostics !== []) {
            return Result::failure(self::NAME, $diagnostics);
        }

        return Result::success(self::NAME, ['schema_version' => '1.0'], 'Configuration is valid.');
    }
}
