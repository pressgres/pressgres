<?php

declare(strict_types=1);

namespace Pressgres\Contracts;

use JsonSerializable;
use Pressgres\Contracts\Exception\InvalidUuid;
use SensitiveParameter;
use Stringable;

final readonly class Uuid implements JsonSerializable, Stringable
{
    private string $value;

    private function __construct(string $value)
    {
        $this->value = $value;
    }

    /** @throws InvalidUuid */
    public static function fromString(#[SensitiveParameter] mixed $value): self
    {
        if (
            !is_string($value)
            || preg_match('/\A[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\z/', $value) !== 1
        ) {
            throw new InvalidUuid();
        }

        return new self($value);
    }

    public function equals(self $other): bool
    {
        return $this->value === $other->value;
    }

    public function __toString(): string
    {
        return $this->value;
    }

    public function jsonSerialize(): string
    {
        return $this->value;
    }

    /** @return array{value: string} */
    public function __serialize(): array
    {
        return ['value' => $this->value];
    }

    /** @param array<array-key, mixed> $data */
    public function __unserialize(#[SensitiveParameter] array $data): void
    {
        $this->value = self::fromString($data['value'] ?? null)->value;
    }
}
