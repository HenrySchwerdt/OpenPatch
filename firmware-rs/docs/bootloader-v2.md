# Bootloader v2: manifest format 2, rollback protection, USB DFU rules (cup v4)

> Supplements `bootloader.md`. `openpatch-boot-policy` (host tested, real Ed25519 / SHA-512) holds every rule; the bootloader only supplies flash reads, salty and the UICR words.

* **Manifest (84 bytes):** `magic | format 2 | reserved | image_len | security version | hw_id | signature`. The signature is Ed25519 over `SHA-512("OPFW2" || 20 header bytes || image)`: version, hardware id and length are signed. Format 1 is refused. `scripts/sign-image.sh` needs `SECURITY_VERSION`; `sigtool sign <keys> <image> <prefix> <version>`.
* **Verify before swap:** manifest, key present, size, hardware id, rollback version, then the signature (cheap checks first). Without a compiled-in key everything is refused. An invalid pending update is cancelled.
* **Rollback:** the minimum security version lives in `UICR.CUSTOMER[0..32]` (one word per raise, 32 raises in the life of the chip, bits only 1 -> 0). It is raised only at a boot whose state is confirmed (`mark_booted` done, no swap or revert pending), so a reverted trial image never raises it. A damaged counter refuses updates (fail closed) and still boots the active image. Use a security version per release that must not be downgraded, not per build.
* **Application:** `dfu::finalize` only arms the swap (`mark_updated`); the bootloader verifies.
* **USB DFU transport:** `openpatch_boot_policy::dfu::DfuReceiver` (sequential blocks, bounded size, manifest last, never arms) is host tested. The USB class glue (embassy-usb + DFU class, the reserved `usb-dfu` feature of `openpatch-bootloader`) is NOT written: it cannot be built or tested here. The bootloader never enables the motor supply, so DFU mode cannot move the motor.
