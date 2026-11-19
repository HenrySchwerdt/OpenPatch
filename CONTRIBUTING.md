# Contributing to OpenPatch

OpenPatch is a **test project, not a medical device**; it must never be worn or used on a person (see [`DISCLAIMER.md`](DISCLAIMER.md)). Contributions that describe on-body use or use with insulin on a human are not accepted.

## Before you start

1. Read [`docs/STATUS.md`](docs/STATUS.md) and [`spec/design-parameters.md`](spec/design-parameters.md) (single source of truth; change it first, then propagate).
2. Read [`docs/02-safety.md`](docs/02-safety.md). Safety limits are never relaxed silently, and the hardware interlock stays in every revision.

## Licensing and CLA

The project is dual licensed (see [`LICENSE.md`](LICENSE.md)): a free community licence for non-commercial use, and a commercial "Fair-Price" licence ([`COMMERCIAL-LICENSE.md`](COMMERCIAL-LICENSE.md), draft). To make that possible, every contributor agrees to [`CLA.md`](CLA.md): you keep your copyright, grant the maintainer the right to relicense your contribution (including commercially), and the maintainer commits to keep it available under the community licence.

**Sign-off is required on every commit and PR:** use `git commit -s`, and write "I have read and agree to CLA.md" in the first PR description. PRs without sign-off are not merged.

Do not copy code from sources with incompatible licences (in particular no GPL code, e.g. nightscout/ESP-Sim, into non-`ios/` paths; the DASH mode must be a clean-room implementation).

## Rules

- English for all documentation, code comments and UI text.
- Firmware core: Rust, `no_std`, `forbid(unsafe_code)`; developed test-first; all tests green before a PR.
- Mechanics: run `mechanical/check.py` after every change (height ≤ 8.5 mm); assembly without soldering (spec §1a).
- Do not commit manufacturer datasheets (PDF).
- Conventional Commits for messages.
