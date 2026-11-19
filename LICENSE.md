# Licensing

OpenPatch is a **test project, not a medical device**. It must never be worn or used on a person (see [`DISCLAIMER.md`](DISCLAIMER.md)). The licences below grant rights to the design files; they grant **no** permission or fitness for medical use, and every licence excludes warranty and liability.

The project uses a **copyleft mix** (decision 2026-11-19): anyone who distributes modified versions, including companies, must publish their changes under the same terms.

| What | Paths | Licence (SPDX) | Full text |
|---|---|---|---|
| Hardware design: CAD, generators, PCB, Gerbers, BOMs, fab packages | `mechanical/`, `electronics/`, `spec/` | `CERN-OHL-S-2.0` | [`LICENSES/CERN-OHL-S-2.0.txt`](LICENSES/CERN-OHL-S-2.0.txt) |
| Software: firmware (Rust and C reference), iOS kit, website code, tools and scripts | `firmware-rs/`, `firmware/`, `ios/`, `site/` (code), `**/*.py`, `**/*.sh` | `GPL-3.0-or-later` | [`LICENSES/GPL-3.0-or-later.txt`](LICENSES/GPL-3.0-or-later.txt) |
| Documentation, images, renders, website text | `docs/`, `*.md`, `site/` (content and images) | `CC-BY-SA-4.0` | [`LICENSES/CC-BY-SA-4.0.txt`](LICENSES/CC-BY-SA-4.0.txt) |

Notes:
- GPL-3.0 for the firmware is also required by the planned DASH compatibility mode, which follows `nightscout/ESP-Sim` (GPL-3.0).
- Python generator scripts inside `mechanical/` and `electronics/` are software (GPL-3.0-or-later); the geometry and boards they produce are hardware (CERN-OHL-S-2.0).
- Third-party components keep their own licences: LoopKit (MIT), Embassy/trouble-host and other Rust crates (see `Cargo.lock`, mostly MIT/Apache-2.0), swift-crypto (Apache-2.0), KiCad vendor footprints/symbols (per library), vendor datasheets (not redistributed, excluded via `.gitignore`).
- "OpenPatch" is a project name, not a registered trademark. Products from other vendors (Accu-Chek, Insight Flex, Omnipod, Trio) are named only for compatibility; no affiliation.
- Copyright © 2026 the OpenPatch contributors.
