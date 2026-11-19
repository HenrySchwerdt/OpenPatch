# Bootloader, DFU and signing

> TEST PROJECT. The signature protects the bench firmware against accidents and tampering; the device is never worn.

## Layout (`layout/layout.rs`, one source for both crates, generates `memory.x`)

```
0x000000 BOOTLOADER        32 KB   openpatch-bootloader (embassy-boot-nrf 0.12.0, about 13 KB with the verifier)
0x008000 BOOTLOADER_STATE   4 KB   embassy-boot state (magic + swap/revert progress)
0x009000 ACTIVE           476 KB   application (linked at 0x9000, vector table first); the last page is the MANIFEST page
0x080000 DFU              480 KB   ACTIVE + one spare page (embassy-boot swap scratch page)
0x0F8000 STORAGE           32 KB   settings (sequential-storage map), written by the persistence task
RAM 0x20000000, 256 KB     shared; flip-link puts the stack below the statics
```

The application linker region is `ACTIVE - 1 page` (472 KB; the current build uses about 262 KB). The manifest page (last page of the
ACTIVE window, same relative offset in DFU) holds: `magic "OPFW" u32 | format u16 | reserved u16 | image_len u32 | ed25519 signature [64]`.
Per-board differences exist only in the app (pin maps); the bootloader only knows the board feature for the TPL5010 DONE pin (below).
Settings are in the same flash, outside every swap range.

## Signing scheme

Identical to `embassy_boot::FirmwareUpdater::verify_and_mark_updated`: **Ed25519 over the 64 byte SHA-512 digest of the image bytes**.

* `scripts/gen-signing-key.sh` builds `tools/sigtool` (host tool, ed25519-dalek 2.2.0) and writes `firmware-rs/keys/ed25519-secret.bin` (32 byte
  seed, mode 0600) and `ed25519-public.bin` (32 bytes). It refuses to overwrite. `keys/`, `*.pem`, `*.key` and `**/ed25519-secret*` are git-ignored.
  **Never commit the private key; back it up offline; rotating it means re-flashing the bootloader.**
* `scripts/sign-image.sh <app.elf|app.bin> [prefix]` converts to a raw binary (`rust-objcopy`), signs, verifies, and writes
  `<prefix>.manifest.bin` (76 bytes) and `<prefix>.dfu.hex` (image at the DFU address + manifest at the manifest page, for `probe-rs download --format hex`).
* The public key is compiled into **both** the bootloader and the application's updater by `build.rs` (`OPENPATCH_SIGNING_PUBKEY=<path>` or
  `keys/ed25519-public.bin`). **Without a key both are built fail-closed** (the build prints a warning): the bootloader cancels every pending update,
  `dfu::finalize` refuses. Rebuild both after generating a key (`scripts/build.sh`).
* The sigtool signature was cross-checked with the `salty` verifier that runs in the bootloader (same digest, same message).

## Update flow

1. The DFU transport (out of scope: BLE or file) writes the image to DFU offset 0 and the manifest to DFU offset `MANIFEST_OFFSET`, only while delivery is
   suspended (protocol section 1).
2. `dfu::finalize(updater, signature, len)` = `FirmwareUpdater::verify_and_mark_updated(public_key, signature, len)`: verifies and arms the swap.
3. Reset. The bootloader checks (defense in depth): state says swap **and no swap progress exists yet** (= pending update, not a trial boot) -> verifies the
   manifest and signature in DFU with the compiled-in key, else cancels the swap (`mark_booted`). Then `BootLoader::prepare` does the power-fail-safe swap.
4. The new image runs on trial. `dfu::confirm_task` waits for the safety task to report **30 good ticks** (`BOOT_OK_TICKS`: ticks in time, interlock verified) and calls
   `mark_booted`. If the image crashes / hangs earlier, the reset (TPL5010 on the bench board) makes the bootloader **revert** to the previous image.
5. On the next boot after a revert the app logs `DFU: the previous update was REVERTED`.

Limits (docs/stubs.md): the transport and the manifest writer are not implemented; the pending-vs-trial check reads the documented progress word of the
embassy-boot state partition (a future embassy-boot layout change would need a re-check); the bootloader services the TPL5010 DONE pin before every flash
erase/write because a swap takes several seconds (timing against the TPL5010 WAKE not verified on hardware).

## Building

`scripts/build.sh` builds the bootloader and both app configurations and prints text/data/bss. Flash on the bench board:

```sh
cd openpatch-bootloader && cargo run --release        # bootloader (probe-rs)
cd ../openpatch-bench && cargo run --release --features dev-plaintext
```
