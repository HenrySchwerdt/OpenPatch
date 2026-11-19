# CLAUDE.md – Instructions for AI assistants in this repo

**Project:** OpenPatch, an open-source patch insulin pump **test project**. **Not a medical device; it must never be worn or used on a person** (see `DISCLAIMER.md`). Never write instructions for on-body use or for use with insulin on a human. Safety takes priority over everything else (see `docs/02-safety.md`).

## Getting started
1. `docs/STATUS.md`: current state, decisions, next steps
2. `spec/design-parameters.md`: single source of truth for all dimensions, components and limits. Make changes there first, then propagate them to the subprojects.

## Rules
- All documentation, code comments and UI text in English.
- Safety limits (spec §7) must never be relaxed silently.
- The hardware interlock (motor only with MCU enable **and** watchdog) is kept in every revision.
- Firmware is written in **Rust** (`firmware-rs/`, Embassy, `no_std` core with `forbid(unsafe_code)`); `firmware/` (C/Zephyr) is the frozen reference for differential tests only.
- The firmware core and the Swift core are developed test-first. All tests must be green before committing.
- Mechanics: run `mechanical/check.py` after every change. Height ≤ 8.5 mm.
- Assembly without a soldering iron (spec §1a).
- Do not commit manufacturer datasheets (PDF); they are excluded via `.gitignore`.
- After every unit of work, update `docs/STATUS.md`, commit (Conventional Commits) and push.

## Tools on the developer Mac
- SolidCraft (3D): `/Applications/SolidCraft.app/Contents/MacOS/solidcraft-cli`. MCP server: `solidcraft-cli mcp`
- CADCraft (2D, DXF/DWG): `/Applications/CADCraft.app`, control server: `--control <PORT>`
- KiCad 10: `/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli`
- nRF Connect SDK: `nrfutil` (Homebrew), SDK in `~/ncs`
