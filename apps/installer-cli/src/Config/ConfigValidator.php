<?php

declare(strict_types=1);

namespace Pressgres\InstallerCli\Config;

use JsonSchema\Constraints\Constraint;
use JsonSchema\Validator;
use Pressgres\Contracts\Exception\Diagnostic;
use Pressgres\Contracts\Exception\ErrorCode;
use RuntimeException;
use stdClass;
use Symfony\Component\Yaml\Exception\ParseException;
use Symfony\Component\Yaml\Yaml;

final class ConfigValidator
{
    public const int MAX_BYTES = 65_536;

    private const array SECRET_PATHS = ['/database/password', '/database/migrator_password', '/redis/password'];

    /** @return list<Diagnostic> */
    public function validate(string $yaml): array
    {
        $correlationId = bin2hex(random_bytes(16));
        if (strlen($yaml) > self::MAX_BYTES) {
            return [self::diagnostic(ErrorCode::InvalidInput, 'Configuration exceeds 64 KiB.', '', $correlationId)];
        }

        try {
            $document = Yaml::parse(
                $yaml,
                Yaml::PARSE_OBJECT_FOR_MAP | Yaml::PARSE_EXCEPTION_ON_INVALID_TYPE | Yaml::PARSE_EXCEPTION_ON_ALIAS,
            );
        } catch (ParseException) {
            return [self::diagnostic(ErrorCode::InvalidInput, 'Invalid YAML configuration.', '', $correlationId)];
        }

        $schema = @file_get_contents(__DIR__ . '/../../schemas/pressgres-v1.json');
        if ($schema === false) {
            throw new RuntimeException('Unable to read the packaged configuration schema.');
        }

        $validator = new Validator();
        $validator->validate(
            $document,
            json_decode($schema, false, 512, JSON_THROW_ON_ERROR),
            Constraint::CHECK_MODE_STRICT,
        );

        $diagnostics = [];
        foreach ($validator->getErrors() as $error) {
            // Validator messages and parameters can contain raw input. Only emit safe schema paths.
            $path = is_array($error) ? ($error['pointer'] ?? null) : null;
            $constraint = is_array($error) ? ($error['constraint'] ?? null) : null;
            if (!is_string($path) || !is_array($constraint)) {
                throw new RuntimeException('Configuration validation did not return a JSON pointer.');
            }
            if (($constraint['name'] ?? null) === 'additionalProp') {
                // Unknown key names are user input and could themselves contain a secret.
                $path = substr($path, 0, (int) strrpos($path, '/'));
                $diagnostics[$path] = self::diagnostic(ErrorCode::InvalidInput, 'Unknown key.', $path, $correlationId);
                continue;
            }
            $isSecret = in_array($path, self::SECRET_PATHS, true);
            $message = $isSecret ? 'Expected a valid secret reference.' : 'Value does not match the schema.';
            $diagnostics[$path] = self::diagnostic(
                $isSecret ? ErrorCode::SecurityFailure : ErrorCode::InvalidInput,
                $message,
                $path,
                $correlationId,
            );
        }

        $database = $document instanceof stdClass ? ($document->database ?? null) : null;
        if ($database instanceof stdClass) {
            $runtimeUser = $database->runtime_user ?? null;
            if (is_string($runtimeUser) && $runtimeUser !== '' && $runtimeUser === ($database->migrator_user ?? null)) {
                $diagnostics['/database/migrator_user'] = self::diagnostic(
                    ErrorCode::InvalidInput,
                    'The migrator must use a different database role.',
                    '/database/migrator_user',
                    $correlationId,
                );
            }
            $runtimePassword = $database->password ?? null;
            if (is_string($runtimePassword) && $runtimePassword === ($database->migrator_password ?? null)) {
                $diagnostics['/database/migrator_password'] ??= self::diagnostic(
                    ErrorCode::SecurityFailure,
                    'The migrator must use a different secret reference.',
                    '/database/migrator_password',
                    $correlationId,
                );
            }
        }

        return array_values($diagnostics);
    }

    private static function diagnostic(ErrorCode $code, string $message, string $path, string $id): Diagnostic
    {
        return new Diagnostic(
            $code,
            $message,
            $code === ErrorCode::SecurityFailure
                ? 'Use env:NAME or file:/absolute/path.'
                : 'Check the configuration against the v1.0 schema.',
            $id,
            context: ['path' => $path],
        );
    }
}
