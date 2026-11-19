# Proposal 04: Anti-rollback monotonic counter, signed manifest metadata, secure update path

Status: proposed, **not implemented**. Priority **P1** (P0 before any DFU transport is written: the transport does not exist yet, so the window to design this correctly is now).
Evidence: `firmware-rs/openpatch-bootloader/src/main.rs` (`check_pending`), `firmware-rs/docs/bootloader.md`, fuzz target `dfu_manifest` (FINDING-006), `firmware-rs/docs/stubs.md` (DFU transport, "verified only on the host").

## 1. What the current scheme does and does not give
Signature: Ed25519 over the **SHA-512 of the image bytes only**. The 76-byte manifest (`magic | format u16 | reserved u16 | image_len u32 | signature`) is checked for magic and `0 < len <= APP_SIZE`; `format` and `reserved` are **ignored and not signed**. A pending update is verified before the swap; a trial boot reverts if not confirmed within 30 good ticks.

Gaps (all demonstrated or derived from the code, FINDING-006):
1. **No version in the signature, no rollback protection.** Any previously valid signed image (for instance the build before a security fix) installs and confirms. For a pod whose security depends on patches this makes every fixed vulnerability permanently re-exploitable by whoever can deliver an image (DFU transport, or a physical attacker with the update path).
2. **No binding to hardware target/board/feature set.** A signed `board-nrf52840-dk` build (no hardware interlock: `interlock: None`) or a `dev-plaintext` build (fixed public key, plaintext accepted) signed by the same key installs on a bench-e73 pod. The signature authenticates *a* build, not *this product configuration*.
3. **Unsigned manifest fields** (`format`, `reserved`) are attacker-modifiable without invalidating the signature; today harmless, but any future semantic (version, flags) added there would be unauthenticated.
4. **No signature over `image_len` in the signed message** (the digest covers exactly `image[..len]`, so truncation changes the digest: ok), but extension past `len` is not covered (trailing bytes ignored, by design of embassy-boot).
5. **Single signing key, no rotation, no revocation, key on a developer machine** (`scripts/gen-signing-key.sh` writes `keys/ed25519-secret.bin` 0600). Rotating needs re-flashing the bootloader.
6. **The active image is never re-verified after the swap** (no secure boot of ACTIVE at each reset): a physical attacker with flash write (APPROTECT off, or glitched) runs unsigned code. Acceptable *only* with APPROTECT (proposal 03) and documented as such.
7. **The manifest parser is a mirror in the fuzz crate**, not the real code: `check_pending` is inside a `no_std` binary and cannot be fuzzed directly.

## 2. Signed manifest v2
```
manifest v2 (little endian, signed fields in bold):
  magic "OPFW"                u32
  format = 2                  u16     (checked, must be exactly the supported value)
  flags                       u16     (checked: reserved bits must be 0)
  image_len                   u32
  **security_version**        u32     monotonic counter, 1 per security-relevant release
  **min_bootloader_version**  u16
  **product_id**              u16     bench-e73 = 0x0101, dk = 0x0102 ... compiled into bootloader and app
  **build_profile**           u8      0 = production, 1 = dev (dev refuses to install on a pod whose profile is production)
  **drive_preset_id**         u16     must equal the pod's stored drive calibration id (prevents a 25 % dosing-error image)
  **fw_version**              u32
  reserved                    zero
  signature                   64      Ed25519 over  SHA-512( "OPENPATCH/FW/2" || all **signed fields** || SHA-512(image[..len]) )
```
Everything the bootloader acts on is inside the signature, labelled (`OPENPATCH/FW/2` domain separation: the old image-digest-only signature can never be replayed as a v2 signature).

## 3. Anti-rollback counter
- The bootloader keeps `min_security_version` in a **write-once-style monotonic structure in UICR/flash** (nRF52840 has no OTP counters: use a *thermometer code* in a dedicated flash page: n erased-to-0 bits per increment, 128 increments per page, two pages for 256 + wear; an attacker with flash write can reset it, so this protects against *transport-level* downgrade and accidents, not against a physical attacker; Rev B uses the nRF54L15 KMU/NVM counters (`NRF_NVMC` + OTP-like UICR words) and then it is hardware enforced).
- Update accepted iff `manifest.security_version >= min_security_version` **and** `fw_version` is not lower than the installed one unless `flags.allow_downgrade` is signed *and* delivery is suspended *and* the user pressed the button (service downgrade for bench debugging only, never in `production`).
- After a successful **confirm** (`mark_booted` of the new image) the app raises `min_security_version` to the image's `security_version` (never before: a bad image must remain revertable).
- The same counter feeds `MIN_SUITE` for protocol version negotiation (proposal 01) and the CRL version floor (proposal 02): one monotonic store, one rule.

## 4. Move the parser into a library (testable, fuzzable, Kani-provable)
Create `firmware-rs/openpatch-fw-manifest` (`no_std`, `forbid(unsafe_code)`, deps: `ed25519-dalek` or `salty`, `sha2`): `Manifest::parse(&[u8]) -> Result<Manifest, ManifestError>` and `Manifest::verify(&self, pubkey, image_reader) -> Result<(), VerifyError>` with a streaming reader trait so the bootloader reads the DFU flash in chunks. The bootloader, `dfu::finalize`, `tools/sigtool` and the fuzz target all call the same crate. Delete the mirror in `firmware-rs/fuzz/src/lib.rs`. The Kani proofs then cover `parse` (no panic for any 76 bytes; accepted => `0 < len <= APP_SIZE`, reserved/format valid).

## 5. Signing key management and rotation
1. **Offline root signing key** on a hardware token (YubiKey PIV/OpenPGP or an HSM; Ed25519 where the token supports it, otherwise a P-256 variant of the manifest signature, decision recorded). The developer machine never holds the release key.
2. **Two keys in the bootloader**: `K_release` and `K_next` (hash or public key of the next key). A manifest signed by `K_next` is accepted only if it is *also* an image that sets `K_release := K_next` (key rotation through the update path, signed by the old key first). Revoking a compromised release key: ship an update signed by the *other* key slot; the compromised slot is overwritten.
3. **Two-person rule** for release signing (second maintainer signs the release tag, CI verifies both: `git tag -v`, minisign/sigstore: see proposal 08).
4. Never sign in CI with a long-lived key: CI builds and attests (SLSA provenance, `actions/attest-build-provenance`), a human signs the *hash* on the token.

## 6. DFU transport requirements (to write before the transport)
- Transport is an untrusted pipe: no parsing of attacker data before the signature check except the 76/80-byte manifest and fixed-size chunks written *verbatim* to the DFU partition.
- Delivery suspended + docked-state check + **user confirmation on the pod (button)** to *start* a swap; the phone cannot force a swap alone (an authenticated-but-compromised phone must not be able to push firmware; the signature still protects, but a second factor removes a whole class of "stolen signing key + compromised phone" combinations).
- Chunk integrity is end-to-end via the signature, not per chunk.
- DFU commands are **dangerous commands** under proposal 07 (fresh confirmation).
- Bandwidth/time-out limits, partial-image garbage collection, and a *hard cap on consecutive failed DFU attempts* (rate limit).

## 7. Test plan
1. `security/verify`: proptest on the new parser (round trip, every single-bit flip of any signed field invalidates, unknown format/flags rejected, version comparison total order, rollback table-driven tests).
2. `firmware-rs/fuzz/fuzz_targets/dfu_manifest.rs` retargeted to the real crate; the FINDING-006 branch (format/reserved ignored) is inverted: changing those bytes must now fail.
3. Kani: `parse` panic-freedom + `accept => bounds`.
4. Host integration test with `tools/sigtool` signing v2 manifests and the bootloader *logic* (the verify function is host-callable) rejecting: old `security_version`, wrong `product_id`, dev-profile on production, wrong `drive_preset_id`, truncated/extended image, wrong key.
5. Hardware (when a probe exists): power-fail at every flash write of a swap (fault injection by the TPL5010 reset), counter increment only after confirm.
6. Release checklist: reproducible build hash equals the signed hash (`security/supply-chain/repro-build.sh`).
