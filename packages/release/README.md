# Pressgres Release

`pressgres/release` verifies signed release metadata, staged artifacts and extracted trees on PHP 8.4 with Sodium. The [v1 JSON Schema](schema/release-lock-v1.json) defines the wire format. The [test fixture](tests/fixtures/release-lock-v1.json) has synthetic artifact and patch digests and an example URL. Its baseline pins are WordPress 7.1.5, Gutenberg `89408c2b9bd944575dfa9039bc6870da1c8f56cb`, PHP 8.4.27, PostgreSQL 18.6 and Valkey 9.2.0.

## Lockfile and verification order

- `lockfile_version` is the integer `1`. `pressgres_version` is a semantic version. `wordpress_develop` records an exact tag and full commit, and `gutenberg_commit` records a full commit. Runtime pins are exact versions such as `8.4.27`, `18.6` and `9.2.0`.
- Each WordPress and Gutenberg patch series records the SHA-256 of the exact bytes of its `series` and `upstream.lock` files. This binds those files to the signed release while preserving the ordered per-patch checks and strict application in [ADR-0001](../../docs/adr/0001-wordpress-change-strategy.md).
- Each artifact has a unique portable basename, an HTTPS URL without user info or a fragment, a byte size, a lowercase SHA-256 and an optional lowercase SHA-512. The reader rejects missing pins, unknown fields, duplicate JSON member names and unknown format versions. Input is limited to 1 MiB.
- Authenticate the exact JSON bytes before using any pins. Verify every staged artifact before extraction. Verify both series files against their signed digests before reading or applying them. Release tooling must still verify the per-patch hashes and the upstream and patched trees during strict apply.

```php
use Pressgres\Release\ArtifactVerifier;
use Pressgres\Release\Ed25519SignatureVerifier;
use Pressgres\Release\ReleaseLockReader;

$reader = new ReleaseLockReader(new Ed25519SignatureVerifier($trustedPublicKeys));
$lock = $reader->readSigned($lockfileBytes, $detachedSignatureBytes, $keyId);

$verifier = new ArtifactVerifier();
foreach ($lock->artifacts as $artifact) {
    $verifier->verifyArtifact($stagingDirectory, $artifact);
}
```

Use a private, caller-controlled POSIX staging directory. Keep it quiescent through verification and subsequent use. The library rejects symbolic links in artifact paths and checks that file metadata is stable during hashing. The caller owns downloading, redirect policy, safe extraction and publication. Tree verification runs after extraction and requires an independently obtained expected digest.

## Tree manifest v1

The digest is SHA-256 over the ASCII header `pressgres-tree-v1` followed by LF, then one record per entry. Paths use slash-separated components relative to the root and sort by raw bytes. The root itself is omitted. Each record is `hex(path) TAB mode TAB value LF`, with lowercase hex and literal tab and LF separators.

| Entry | Mode | Value |
|---|---|---|
| Directory, including an empty directory | `040000` | `-` |
| Regular file with no executable bit | `100644` | SHA-256 of its bytes |
| Regular file with any executable bit | `100755` | SHA-256 of its bytes |
| Symbolic link | `120000` | Hex of the literal relative target |

The mode encoding ignores ownership, timestamps and ordinary permission bits other than executable bits. Special permission bits and special files are rejected. Relative paths and link targets reject absolute paths, empty segments, `.`, `..`, backslashes, colons and ASCII control characters. Links must resolve within the root and are recorded without traversing them. The proof of concept in [tools/patchset](../../tools/patchset/README.md) also hashes sorted file paths. Its file-only format produces different digests. Release tooling using tree manifest v1 must generate fresh upstream and patched-tree pins.

## Signatures and trusted keys

`SignatureVerifier` verifies the exact byte string against a detached signature and a key ID. The Sodium implementation takes a raw 64-byte Ed25519 signature and raw 32-byte public keys. The caller decodes any transport encoding before invoking it. Provision public keys and their IDs independently through a reviewed installer build or operator configuration. A key ID supplied alongside the signature selects a key from this trust root.

Keep signing keys offline or in controlled signing infrastructure and reserve them for release signing. For planned rotation, add the new public key to the trust root through a reviewed update, distribute the update before publishing signatures under the new ID, then remove the retiring key after the overlap window. On suspected compromise, remove that key through a trusted update and re-sign approved releases with a new key. The caller enforces release selection, rollback policy and trust-root updates. The interface leaves room for a future verifier such as Sigstore. Ed25519 verification is tested using public vectors and keys generated at test time. [RFC 8032 §7.1](https://www.rfc-editor.org/rfc/rfc8032.html#section-7.1)

## Failure handling and installer adoption

Both exceptions derive from the shared `PressgresException`.

| Exception | Exit code | Examples |
|---|---|---|
| `SecurityFailure` | 5 | Invalid signature, unknown key, unsafe path, escaping link or unsafe entry type |
| `VerificationFailure` | 8 | Invalid or unsupported lockfile, missing or unreadable entry, size or digest mismatch |

The [installer manifest](../../apps/installer-cli/release/manifest.json) remains the source of preview metadata for `wps version` and can have null digests. In a follow-up, release tooling should generate and sign the lockfile from built artifacts and the exact runtime pins. The installer can then derive display metadata from that verified lockfile and use it as the authority for release selection and staging. The fixture verifies the contract in PHP and establishes no new runtime compatibility evidence.
