<?php

declare(strict_types=1);

namespace Pressgres\InstallerCli\Commands;

use Pressgres\Contracts\Exception\ErrorCode;
use Pressgres\Contracts\Exception\PressgresException;
use Pressgres\InstallerCli\Config\ConfigValidator;
use Pressgres\InstallerCli\Output\Result;
use RuntimeException;

final readonly class InitCommand
{
    public const string NAME = 'init';
    public const string PROFILE = 'postgres-native-uuid';

    public function __construct(private ConfigValidator $validator = new ConfigValidator())
    {
    }

    public function run(string $profile, string $output, bool $force, bool $dryRun): Result
    {
        if ($profile !== self::PROFILE) {
            throw new PressgresException(
                ErrorCode::InvalidInput,
                'Unknown profile.',
                'Use --profile postgres-native-uuid.',
            );
        }

        $writer = new InitFiles($output);
        $yaml = @file_get_contents(__DIR__ . '/../../templates/pressgres.yaml');
        $env = @file_get_contents(__DIR__ . '/../../templates/env.example');
        if ($yaml === false || $env === false || $this->validator->validate($yaml) !== []) {
            throw new RuntimeException('Invalid packaged init templates.');
        }

        if ($dryRun) {
            $writer->checkDestinations($force);
        } else {
            $writer->write($yaml, $env, $force);
        }

        return Result::success(
            self::NAME,
            ['profile' => self::PROFILE, 'dry_run' => $dryRun],
            $dryRun ? 'Dry run complete. No files written.' : 'Wrote configuration and .env.example.',
        );
    }
}
