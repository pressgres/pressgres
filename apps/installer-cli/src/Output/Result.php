<?php

declare(strict_types=1);

namespace Pressgres\InstallerCli\Output;

use Pressgres\Contracts\Exception\Diagnostic;
use Pressgres\Contracts\ExitCode;

final readonly class Result
{
    /**
     * @param array<string, mixed> $data
     * @param list<Diagnostic> $diagnostics
     */
    private function __construct(
        private ?string $command,
        public ExitCode $exitCode,
        private array $data,
        private string $humanOutput,
        private array $diagnostics,
    ) {
    }

    /** @param array<string, mixed> $data */
    public static function success(string $command, array $data, string $humanOutput): self
    {
        return new self($command, ExitCode::Success, $data, $humanOutput, []);
    }

    public static function error(?string $command, Diagnostic $diagnostic): self
    {
        return self::failure($command, [$diagnostic]);
    }

    /** @param non-empty-list<Diagnostic> $diagnostics */
    public static function failure(?string $command, array $diagnostics): self
    {
        $exitCode = $diagnostics[0]->code->exitCode();
        $lines = [];
        foreach ($diagnostics as $diagnostic) {
            if ($diagnostic->code->exitCode() === ExitCode::SecurityFailure) {
                $exitCode = ExitCode::SecurityFailure;
            }
            $path = $diagnostic->context['path'] ?? null;
            $location = is_string($path) ? ($path === '' ? '(root) ' : "$path ") : '';
            $lines[] = "[{$diagnostic->code->value}] {$location}{$diagnostic->message}";
            $lines[] = $diagnostic->remediation;
        }
        $lines[] = 'Correlation ID: ' . $diagnostics[0]->correlationId;

        return new self($command, $exitCode, [], implode("\n", $lines), $diagnostics);
    }

    public function render(bool $json): string
    {
        if (!$json) {
            return $this->humanOutput . "\n";
        }

        return json_encode(
            [
                'schema' => 'pressgres.cli/v1',
                'command' => $this->command,
                'status' => $this->exitCode === ExitCode::Success ? 'ok' : 'error',
                'exit_code' => $this->exitCode->value,
                'data' => (object) $this->data,
                'diagnostics' => $this->diagnostics,
                'correlation_id' => $this->diagnostics[0]->correlationId ?? null,
            ],
            JSON_THROW_ON_ERROR | JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES,
        ) . "\n";
    }
}
