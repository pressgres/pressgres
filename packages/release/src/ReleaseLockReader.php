<?php

declare(strict_types=1);

namespace Pressgres\Release;

use JsonException;
use JsonSchema\Constraints\Constraint;
use JsonSchema\Validator;
use stdClass;

/**
 * @phpstan-type Series object{series_sha256: string, upstream_lock_sha256: string}
 * @phpstan-type LockDocument object{
 *     pressgres_version: string,
 *     wordpress_develop: object{tag: string, commit: string},
 *     gutenberg_commit: string,
 *     patch_series: object{wordpress: Series, gutenberg: Series},
 *     artifacts: list<object{name: string, url: string, size: mixed, sha256: string, sha512?: string}>,
 *     runtime: object{php: string, postgresql: string, valkey: string}
 * }
 */
final readonly class ReleaseLockReader
{
    private const MAX_LOCK_BYTES = 1_048_576;

    public function __construct(private SignatureVerifier $signatures)
    {
    }

    public function readSigned(string $json, string $signature, string $keyId): ReleaseLock
    {
        if (strlen($json) > self::MAX_LOCK_BYTES) {
            throw new VerificationFailure('The release lockfile exceeds its size limit.');
        }

        $this->signatures->verify($json, $signature, $keyId);

        try {
            $document = json_decode($json, false, 32, JSON_THROW_ON_ERROR);
            $this->rejectDuplicateMembers($json);
        } catch (JsonException) {
            throw new VerificationFailure('The release lockfile is not valid JSON.');
        }

        if (!$document instanceof stdClass || ($document->lockfile_version ?? null) !== 1) {
            throw new VerificationFailure('The release lockfile version is missing or unsupported.');
        }

        $schemaBytes = @file_get_contents(dirname(__DIR__) . '/schema/release-lock-v1.json');
        $schema = $schemaBytes === false ? null : json_decode($schemaBytes);
        if (!$schema instanceof stdClass) {
            throw new VerificationFailure('The bundled release lockfile schema is unavailable.');
        }
        $validator = new Validator();
        $validator->validate($document, $schema, Constraint::CHECK_MODE_STRICT);
        if (!$validator->isValid()) {
            throw new VerificationFailure('The release lockfile does not conform to its versioned schema.');
        }

        /** @var LockDocument $document Shape established by the bundled schema. */
        return $this->buildLock($document);
    }

    private function rejectDuplicateMembers(string $json): void
    {
        // The native decoder has already checked the grammar. Match entire strings to skip escaped syntax.
        $pattern = <<<'REGEX'
        ~("(?:[^"\\]++|\\.)*+")\s*(:)?|[{}]~s
        REGEX;
        $members = [];
        $offset = 0;
        while (($matched = preg_match($pattern, $json, $token, PREG_OFFSET_CAPTURE, $offset)) === 1) {
            [$value, $position] = $token[0];
            $offset = $position + strlen($value);
            if ($value === '{') {
                $members[] = [];
            } elseif ($value === '}') {
                array_pop($members);
            } elseif (isset($token[1], $token[2])) {
                /** @var string $name */
                $name = json_decode($token[1][0], false, 32, JSON_THROW_ON_ERROR);
                $index = count($members) - 1;
                if (isset($members[$index][$name])) {
                    throw new VerificationFailure('The release lockfile contains a duplicate member name.');
                }
                $members[$index][$name] = true;
            }
        }
        if ($matched === false) {
            throw new VerificationFailure('The release lockfile member names could not be checked.');
        }
    }

    /** @param LockDocument $document */
    private function buildLock(object $document): ReleaseLock
    {
        $artifacts = [];
        $names = [];
        foreach ($document->artifacts as $entry) {
            $url = filter_var($entry->url, FILTER_VALIDATE_URL);
            if ($url === false || !is_int($entry->size)) {
                throw new VerificationFailure('The release lockfile contains an invalid artifact URL or size.');
            }
            if (isset($names[$entry->name])) {
                throw new VerificationFailure('The release lockfile contains a duplicate artifact name.');
            }
            $names[$entry->name] = true;
            $artifacts[] = new Artifact($entry->name, $url, $entry->size, $entry->sha256, $entry->sha512 ?? null);
        }

        return new ReleaseLock(
            $document->pressgres_version,
            $document->wordpress_develop->tag,
            $document->wordpress_develop->commit,
            $document->gutenberg_commit,
            [
                'wordpress' => [
                    'series_sha256' => $document->patch_series->wordpress->series_sha256,
                    'upstream_lock_sha256' => $document->patch_series->wordpress->upstream_lock_sha256,
                ],
                'gutenberg' => [
                    'series_sha256' => $document->patch_series->gutenberg->series_sha256,
                    'upstream_lock_sha256' => $document->patch_series->gutenberg->upstream_lock_sha256,
                ],
            ],
            [
                'php' => $document->runtime->php,
                'postgresql' => $document->runtime->postgresql,
                'valkey' => $document->runtime->valkey,
            ],
            $artifacts,
        );
    }
}
