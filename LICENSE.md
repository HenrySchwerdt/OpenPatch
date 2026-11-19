# Licensing

OpenPatch is a **test project, not a medical device**. It must never be worn or used on a person (see [`DISCLAIMER.md`](DISCLAIMER.md)). The licences below grant rights to the design files; they grant **no** permission or fitness for medical use, and every licence excludes warranty and liability.

Licensor: the OpenPatch maintainer (owner of the GitHub repository `HenrySchwerdt/ai-insulin-pump`).

## The dual model in plain language (decision 2026-11-19)

1. **Community licence (free).** Non-commercial use, research, education and self-build for **bench testing** are free, under established licence texts (CC BY-NC-SA 4.0 for hardware and documentation, PolyForm Noncommercial 1.0.0 for software). Share-alike applies to hardware and documentation.
2. **Commercial "Fair-Price" licence.** Any commercial manufacture, sale, rental or service based on OpenPatch needs a separate licence: [`COMMERCIAL-LICENSE.md`](COMMERCIAL-LICENSE.md). In short: capped end-customer price (cost + 30 %), a 5 % levy into an open clinical-study fund, unweakened safety obligations, and share-back. It is currently a **draft term sheet**, not yet an offer.

Contributors grant the maintainer the right to offer their contributions under the commercial licence as well ([`CLA.md`](CLA.md), [`CONTRIBUTING.md`](CONTRIBUTING.md)); the maintainer commits to keep all contributions available under the community licence too.

## Overview per path

| What | Paths | Licence (SPDX) | Full text |
|---|---|---|---|
| Hardware design: CAD, generators' output, PCB, Gerbers, BOMs, fab packages, specification | `mechanical/`, `electronics/`, `spec/` | `CC-BY-NC-SA-4.0` | [`LICENSES/CC-BY-NC-SA-4.0.txt`](LICENSES/CC-BY-NC-SA-4.0.txt) |
| Documentation, images, renders, website text | `docs/`, `*.md`, `site/` (content and images) | `CC-BY-NC-SA-4.0` | same |
| Software: firmware (Rust and C reference), tools and scripts, website code | `firmware-rs/`, `firmware/`, `tools/`, `**/*.py`, `**/*.sh`, `site/` (code) | `PolyForm-Noncommercial-1.0.0` | [`LICENSES/PolyForm-Noncommercial-1.0.0.txt`](LICENSES/PolyForm-Noncommercial-1.0.0.txt) |
| **Exception:** dock insert / cannula adapter and the dock interface spec (free for everyone, also commercially; each manufacturer approves its own adapter) | `mechanical/op_dock.py`, `mechanical/op_coupon.py`, `mechanical/out/**/dock-inserts/`, `mechanical/out/**/dock-coupon/`, `mechanical/cannula-measurement.md`, spec §8a | `CERN-OHL-P-2.0` | [`LICENSES/CERN-OHL-P-2.0.txt`](LICENSES/CERN-OHL-P-2.0.txt) |
| **Exception:** iOS kit (OpenPatchKit) | `ios/` | `GPL-3.0-or-later` | [`LICENSES/GPL-3.0-or-later.txt`](LICENSES/GPL-3.0-or-later.txt) |

Python generator scripts inside `mechanical/` and `electronics/` are software (PolyForm Noncommercial); the geometry and boards they produce are hardware (CC BY-NC-SA 4.0).

### Why `ios/` stays GPL-3.0-or-later

OpenPatchKit is compiled into **Trio**, which is licensed AGPL-3.0. A non-commercial restriction is an "additional restriction" that GPL/AGPL does not allow, so a PolyForm-licensed kit could not be combined with Trio. `ios/` therefore keeps a GPL-compatible licence. Consequence: the iOS kit is free software for everyone, including commercial users, under GPL terms; the commercial licence does not apply to it (but applies to everything else in a commercial product).

## Please note

- This is **source-available**, not OSI "open source": both CC BY-NC-SA and PolyForm Noncommercial restrict commercial use, which the Open Source Definition does not allow. Do not call the project "open source" in a strict sense.
- **History:** commits before 2026-11-19 contained no licence file (all rights reserved by default); a copyleft mix (cbf9309) was committed on the same day and is replaced by this model. There is no relicensing issue, since no third party received rights under earlier terms.
- Safety-relevant limits in the commercial licence do not change the disclaimer: nothing here permits use on a person.

## Third-party components (keep their own licences)

- LoopKit: MIT.
- Trio: AGPL-3.0. OpenPatchKit is linked into Trio, hence the GPL exception above; OpenPatch's non-`ios/` files are not part of Trio.
- Embassy, trouble-host and other Rust crates: mostly MIT / Apache-2.0 (see `Cargo.lock`).
- swift-crypto: Apache-2.0.
- KiCad vendor footprints/symbols: per library. Vendor datasheets are not redistributed (excluded via `.gitignore`).
- The DASH compatibility mode must be a clean-room implementation (see `spec/design-parameters.md` §6); no GPL code from nightscout/ESP-Sim is copied.
- "OpenPatch" is a project name, not a registered trademark. Products from other vendors (Accu-Chek, Insight Flex, Omnipod, Trio) are named only for compatibility; no affiliation.

Copyright © 2026 the OpenPatch contributors, licensed to the public as described above.
