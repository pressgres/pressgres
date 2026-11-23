<?php

declare(strict_types=1);

namespace Pressgres\InstallerCli;

use Pressgres\Contracts\Exception\Diagnostic;
use Pressgres\Contracts\Exception\ErrorCode;
use Pressgres\Contracts\Exception\PressgresException;
use Pressgres\Contracts\ExitCode;
use Pressgres\InstallerCli\Commands\VersionCommand;
use Pressgres\InstallerCli\Output\Result;
use Throwable;

final readonly class Application
{
    private const string USAGE = 'Usage: wps version [--format=human|json] [--no-interaction]';

    public function __construct(private VersionCommand $version)
    {
    }

    /**
     * @param list<string> $arguments
     * @param resource $stdout
     * @param resource $stderr
     */
    public function run(array $arguments, $stdout, $stderr): ExitCode
    {
        $json = in_array('--format=json', $arguments, true);
        $positionals = [];
        $formatCount = 0;
        $invalidOption = false;
        foreach ($arguments as $argument) {
            match (true) {
                $argument === '--no-interaction' => null,
                $argument === '--format=human', $argument === '--format=json' => ++$formatCount,
                str_starts_with($argument, '-') => $invalidOption = true,
                default => $positionals[] = $argument,
            };
        }
        $command = ($positionals[0] ?? null) === 'version' ? 'version' : null;

        try {
            $result = $this->execute($command, count($positionals), $invalidOption || $formatCount > 1);
            $output = $result->render($json);
        } catch (Throwable) {
            $result = Result::error($command, new Diagnostic(
                ErrorCode::InternalError,
                'An unexpected CLI error occurred.',
                'Check the installer files and include the correlation ID when reporting the error.',
                bin2hex(random_bytes(16)),
            ));
            $output = $result->render($json);
        }

        fwrite($json || $result->exitCode === ExitCode::Success ? $stdout : $stderr, $output);

        return $result->exitCode;
    }

    private function execute(?string $command, int $positionalCount, bool $invalidOption): Result
    {
        $message = match (true) {
            $invalidOption => 'Invalid option.',
            $positionalCount === 0 => 'A command is required.',
            $command === null => 'Unknown command.',
            $positionalCount > 1 => 'Unexpected argument.',
            default => null,
        };

        try {
            if ($message !== null) {
                throw new PressgresException(ErrorCode::InvalidInput, $message, self::USAGE);
            }

            return $this->version->run();
        } catch (PressgresException $exception) {
            return Result::error($command, $exception->diagnostic(bin2hex(random_bytes(16))));
        }
    }
}
