<?php

declare(strict_types=1);

namespace Pressgres\InstallerCli;

use Pressgres\Contracts\Exception\Diagnostic;
use Pressgres\Contracts\Exception\ErrorCode;
use Pressgres\Contracts\Exception\PressgresException;
use Pressgres\Contracts\ExitCode;
use Pressgres\InstallerCli\Commands\ConfigValidateCommand;
use Pressgres\InstallerCli\Commands\InitCommand;
use Pressgres\InstallerCli\Commands\VersionCommand;
use Pressgres\InstallerCli\Output\Result;
use Throwable;

final readonly class Application
{
    private const string USAGE = 'Usage: wps version | init --profile postgres-native-uuid '
        . '[--output pressgres.yaml] [--force] [--dry-run] | config validate --config <file>'
        . ' [--format=human|json] [--no-interaction]';

    public function __construct(
        private VersionCommand $version,
        private InitCommand $init = new InitCommand(),
        private ConfigValidateCommand $config = new ConfigValidateCommand(),
    ) {
    }

    /**
     * @param list<string> $arguments
     * @param resource $stdout
     * @param resource $stderr
     */
    public function run(array $arguments, $stdout, $stderr): ExitCode
    {
        $json = in_array('--format=json', $arguments, true);
        $tokens = [];
        $formatCount = 0;
        foreach ($arguments as $argument) {
            match ($argument) {
                '--no-interaction' => null,
                '--format=human', '--format=json' => ++$formatCount,
                default => $tokens[] = $argument,
            };
        }

        $positionals = array_values(array_filter($tokens, static fn(string $arg): bool => !str_starts_with($arg, '-')));
        $command = match ($positionals[0] ?? null) {
            'version' => 'version',
            InitCommand::NAME => InitCommand::NAME,
            'config' => ($positionals[1] ?? null) === 'validate' ? ConfigValidateCommand::NAME : null,
            default => null,
        };

        try {
            if ($formatCount > 1) {
                throw self::usage('Invalid option.');
            }

            $result = $this->execute($command, $tokens, $positionals);
            $output = $result->render($json);
        } catch (PressgresException $exception) {
            $result = Result::error($command, $exception->diagnostic(bin2hex(random_bytes(16))));
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

    /**
     * @param list<string> $tokens
     * @param list<string> $positionals
     */
    private function execute(?string $command, array $tokens, array $positionals): Result
    {
        if ($command === InitCommand::NAME && ($tokens[0] ?? null) === InitCommand::NAME) {
            $options = self::options(array_slice($tokens, 1), ['profile', 'output'], ['force', 'dry-run']);

            return $this->init->run(
                $options['profile'] ?? throw self::usage('The --profile option is required.'),
                $options['output'] ?? 'pressgres.yaml',
                isset($options['force']),
                isset($options['dry-run']),
            );
        }

        if ($command === ConfigValidateCommand::NAME && array_slice($tokens, 0, 2) === ['config', 'validate']) {
            $options = self::options(array_slice($tokens, 2), ['config'], []);

            return $this->config->run($options['config'] ?? throw self::usage('The --config option is required.'));
        }

        $message = match (true) {
            count($tokens) !== count($positionals) => 'Invalid option.',
            $positionals === [] => 'A command is required.',
            $command === null => 'Unknown command.',
            count($positionals) > 1 => 'Unexpected argument.',
            default => null,
        };
        if ($message !== null) {
            throw self::usage($message);
        }

        return $this->version->run();
    }

    /**
     * @param list<string> $tokens
     * @param list<string> $valueOptions
     * @param list<string> $flags
     * @return array<string, string>
     */
    private static function options(array $tokens, array $valueOptions, array $flags): array
    {
        $options = [];
        for ($index = 0; $index < count($tokens); ++$index) {
            $token = $tokens[$index];
            if (!str_starts_with($token, '--')) {
                throw self::usage(str_starts_with($token, '-') ? 'Invalid option.' : 'Unexpected argument.');
            }
            [$name, $value] = array_pad(explode('=', substr($token, 2), 2), 2, null);
            if (isset($options[$name])) {
                throw self::usage('Duplicate option.');
            }
            if (in_array($name, $flags, true) && $value === null) {
                $options[$name] = '';
                continue;
            }
            if (!in_array($name, $valueOptions, true)) {
                throw self::usage('Invalid option.');
            }
            $value ??= $tokens[++$index] ?? '';
            if ($value === '' || str_starts_with($value, '-')) {
                throw self::usage('An option value is missing or invalid.');
            }
            $options[$name] = $value;
        }

        return $options;
    }

    private static function usage(string $message): PressgresException
    {
        return new PressgresException(ErrorCode::InvalidInput, $message, self::USAGE);
    }
}
