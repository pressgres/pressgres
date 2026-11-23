<?php

declare(strict_types=1);

namespace Pressgres\InstallerCli\Output;

use Pressgres\Contracts\Exception\Diagnostic;
use Pressgres\Contracts\ExitCode;

final readonly class Result
{
    /** @param array<string, mixed> $data */
    private function __construct(
        private ?string $command,
        public ExitCode $exitCode,
        private array $data,
        private string $humanOutput,
        private ?Diagnostic $diagnostic,
    ) {
    }

    /** @param array<string, mixed> $data */
    public static function success(string $command, array $data, string $humanOutput): self
    {
        return new self($command, ExitCode::Success, $data, $humanOutput, null);
    }

    public static function error(?string $command, Diagnostic $diagnostic): self
    {
        $humanOutput = sprintf(
            "[%s] %s\n%s\nCorrelation ID: %s",
            $diagnostic->code->value,
            $diagnostic->message,
            $diagnostic->remediation,
            $diagnostic->correlationId,
        );

        return new self($command, $diagnostic->code->exitCode(), [], $humanOutput, $diagnostic);
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
                'diagnostics' => $this->diagnostic === null ? [] : [$this->diagnostic],
                'correlation_id' => $this->diagnostic?->correlationId,
            ],
            JSON_THROW_ON_ERROR | JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES,
        ) . "\n";
    }
}
