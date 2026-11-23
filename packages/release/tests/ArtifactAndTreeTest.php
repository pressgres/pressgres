<?php

declare(strict_types=1);

namespace Pressgres\Release\Tests;

use FilesystemIterator;
use PHPUnit\Framework\Attributes\DataProvider;
use PHPUnit\Framework\TestCase;
use Pressgres\Contracts\ExitCode;
use Pressgres\Release\Artifact;
use Pressgres\Release\ArtifactVerifier;
use Pressgres\Release\SecurityFailure;
use Pressgres\Release\TreeManifest;
use Pressgres\Release\VerificationFailure;
use RecursiveDirectoryIterator;
use RecursiveIteratorIterator;
use SplFileInfo;

final class ArtifactAndTreeTest extends TestCase
{
    private string $root;

    protected function setUp(): void
    {
        $this->root = sys_get_temp_dir() . '/pressgres-release-' . bin2hex(random_bytes(12));
        self::assertTrue(mkdir($this->root, 0700));
    }

    protected function tearDown(): void
    {
        $entries = new RecursiveIteratorIterator(
            new RecursiveDirectoryIterator($this->root, FilesystemIterator::SKIP_DOTS),
            RecursiveIteratorIterator::CHILD_FIRST,
        );
        /** @var SplFileInfo $entry */
        foreach ($entries as $entry) {
            $entry->isDir() && !$entry->isLink() ? rmdir($entry->getPathname()) : unlink($entry->getPathname());
        }
        rmdir($this->root);
    }

    public function testVerifiesAFileAcrossStreamingChunks(): void
    {
        $contents = str_repeat("chunk\x00", 400_000);
        $this->write('core.tar.gz', $contents);
        $verifier = new ArtifactVerifier();
        $verifier->verifyArtifact($this->root, self::artifact($contents));
        $verifier->verifyFile($this->root, 'core.tar.gz', hash('sha256', $contents));
    }

    public function testRejectsTamperedArtifactOfTheSameSize(): void
    {
        $this->write('core.tar.gz', 'tampered');
        $this->expectException(VerificationFailure::class);
        $this->expectExceptionCode(ExitCode::VerificationFailure->value);
        $this->expectExceptionMessage('digest differs');
        new ArtifactVerifier()->verifyArtifact($this->root, self::artifact('expected'));
    }

    public function testRejectsWrongSizeBeforeAcceptingMatchingDigest(): void
    {
        $this->write('core.tar.gz', 'expected');
        $this->expectException(VerificationFailure::class);
        $this->expectExceptionMessage('size differs');
        new ArtifactVerifier()->verifyArtifact($this->root, self::artifact('expected', size: 99));
    }

    public function testRejectsWrongOptionalSha512(): void
    {
        $this->write('core.tar.gz', 'expected');
        $this->expectException(VerificationFailure::class);
        $this->expectExceptionMessage('digest differs');
        new ArtifactVerifier()->verifyArtifact($this->root, self::artifact('expected', sha512: str_repeat('a', 128)));
    }

    public function testVerifiesAnEmptyFileWithoutSha512(): void
    {
        $this->write('core.tar.gz', '');
        new ArtifactVerifier()->verifyArtifact(
            $this->root,
            new Artifact('core.tar.gz', 'https://example.invalid/core.tar.gz', 0, hash('sha256', '')),
        );
    }

    #[DataProvider('unsafePaths')]
    public function testRejectsUnsafeArtifactPaths(string $path): void
    {
        $this->expectException(SecurityFailure::class);
        $this->expectExceptionCode(ExitCode::SecurityFailure->value);
        new ArtifactVerifier()->verifyFile($this->root, $path, hash('sha256', ''));
    }

    /** @return iterable<string, array{string}> */
    public static function unsafePaths(): iterable
    {
        yield 'parent segment' => ['a/../core.tar.gz'];
        yield 'absolute path' => ['/core.tar.gz'];
        yield 'Windows separator' => ['a\\..\\core.tar.gz'];
        yield 'stream wrapper' => ['file://core.tar.gz'];
        yield 'NUL byte' => ["core\0.tar.gz"];
    }

    public function testRejectsSymlinkInArtifactParentPath(): void
    {
        self::assertTrue(mkdir($this->root . '/real'));
        self::assertTrue(symlink('real', $this->root . '/alias'));
        $this->write('real/core.tar.gz', '');
        $this->expectException(SecurityFailure::class);
        new ArtifactVerifier()->verifyFile($this->root, 'alias/core.tar.gz', hash('sha256', ''));
    }

    public function testTreeManifestHasStablePathsModesAndLinkRecords(): void
    {
        $this->write('z', 'file');
        self::assertTrue(mkdir($this->root . '/a', 0755));
        $this->write('a/x', 'tool');
        self::assertTrue(chmod($this->root . '/a/x', 0700));
        self::assertTrue(symlink('z', $this->root . '/alias'));

        $expected = hash(
            'sha256',
            "pressgres-tree-v1\n61\t040000\t-\n"
            . "612f78\t100755\t" . hash('sha256', 'tool') . "\n"
            . "616c696173\t120000\t7a\n"
            . "7a\t100644\t" . hash('sha256', 'file') . "\n",
        );
        $manifest = new TreeManifest();
        self::assertSame($expected, $manifest->digest($this->root));
        self::assertTrue(chmod($this->root . '/a/x', 0755));
        $manifest->verify($this->root, $expected);

        self::assertTrue(chmod($this->root . '/a/x', 0644));
        $this->expectException(VerificationFailure::class);
        $manifest->verify($this->root, $expected);
    }

    public function testRejectsSymlinkEscape(): void
    {
        self::assertTrue(symlink(dirname($this->root), $this->root . '/escape'));
        $this->expectException(SecurityFailure::class);
        $this->expectExceptionCode(ExitCode::SecurityFailure->value);
        new TreeManifest()->digest($this->root);
    }

    public function testRejectsParentTraversalInSymlinkEvenWhenItResolvesInside(): void
    {
        $this->write('file', 'safe');
        self::assertTrue(mkdir($this->root . '/nested'));
        self::assertTrue(symlink('../file', $this->root . '/nested/alias'));
        $this->expectException(SecurityFailure::class);
        new TreeManifest()->digest($this->root);
    }

    public function testRejectsDanglingSymlink(): void
    {
        self::assertTrue(symlink('missing', $this->root . '/dangling'));
        $this->expectException(SecurityFailure::class);
        new TreeManifest()->digest($this->root);
    }

    private function write(string $name, string $contents): void
    {
        self::assertSame(strlen($contents), file_put_contents($this->root . '/' . $name, $contents));
    }

    private static function artifact(string $contents, ?int $size = null, ?string $sha512 = null): Artifact
    {
        return new Artifact(
            'core.tar.gz',
            'https://example.invalid/core.tar.gz',
            $size ?? strlen($contents),
            hash('sha256', $contents),
            $sha512 ?? hash('sha512', $contents),
        );
    }
}
