# Developer setup (tools and installation)

> Test project, not a medical device (see `DISCLAIMER.md`). This page lists every tool used in this repo, what it is for, and how to install it on macOS, Linux (Debian/Ubuntu) and Windows. Versions in brackets are the ones used on the original dev machine (2026-11).

## Quick matrix

| Tool | Used for | Needed? |
|---|---|---|
| Git + GitHub CLI (`gh`) | version control, PRs, Pages | always |
| Python 3.12+ + `uv` | mechanical generator scripts, SKiDL netlist, helper scripts | mechanics, electronics |
| **SolidCraft** (0.44, includes `solidcraft-cli` + MCP server) | 3D CAD: parametric pod generator, STEP/STL export, renders | mechanics, website renders |
| CADCraft (0.20, optional) | 2D DXF/DWG viewing/editing (board outlines, drawings) | optional |
| **KiCad 10** (10.0.8, includes `kicad-cli` + pcbnew Python) | PCB design, DRC, Gerber/CPL/BOM export | electronics |
| Java (OpenJDK 21+) + Freerouting 2.2.4 jar | autorouter for KiCad | electronics |
| **Rust** (rustup, rustc 1.99) + `thumbv7em-none-eabihf` + `probe-rs` | firmware (`firmware-rs/`, Embassy on nRF52840), flashing | firmware |
| CMake + Clang/GCC | C reference core + its 173 host tests (`firmware/`, frozen) | differential tests |
| nRF Connect SDK v3.4.2 + Zephyr SDK (optional) | building the legacy C/Zephyr firmware | legacy only |
| Node.js 22 LTS + npm | website (`site/`, Vite + three.js) | website |
| Xcode 26 + Swift 6 (macOS only) | iOS `OpenPatchKit` for Trio, `swift test` | iOS |
| A debug probe (nRF52840-DK, J-Link or CMSIS-DAP clone) | flashing the bench controller over SWD | hardware |

## macOS (Apple Silicon or Intel)

```bash
xcode-select --install                      # clang, git, make
brew install gh uv cmake node@22 openjdk
brew install --cask kicad                   # asks for your admin password
sudo ln -sfn /opt/homebrew/opt/openjdk/libexec/openjdk.jdk /Library/Java/JavaVirtualMachines/openjdk.jdk
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
rustup target add thumbv7em-none-eabihf
cargo install probe-rs-tools --locked
```
- **SolidCraft / CADCraft:** download the macOS installers from their vendors (Tangency Labs / Storyteller) and move them to `/Applications`. CLI: `/Applications/SolidCraft.app/Contents/MacOS/solidcraft-cli`. Optional MCP for Claude Code: `claude mcp add solidcraft -- /Applications/SolidCraft.app/Contents/MacOS/solidcraft-cli mcp`.
- **Xcode:** from the App Store (needed for the iOS kit only).
- **Freerouting:** download `freerouting-2.2.4.jar` from github.com/freerouting/freerouting/releases into `electronics/tools/` (git-ignored).

## Linux (Debian/Ubuntu)

```bash
sudo apt update && sudo apt install -y git cmake clang build-essential python3 python3-venv openjdk-21-jre curl
curl -LsSf https://astral.sh/uv/install.sh | sh
# GitHub CLI: see https://cli.github.com (apt repo)
# Node 22: https://github.com/nodesource/distributions or `nvm install 22`
sudo add-apt-repository ppa:kicad/kicad-10.0-releases && sudo apt install -y kicad
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
rustup target add thumbv7em-none-eabihf
cargo install probe-rs-tools --locked     # then install the probe-rs udev rules (see probe.rs docs)
```
- SolidCraft: download the AppImage (`https://github.com/tangency-labs/solidcraft/releases/latest/download/solidcraft-linux-x86_64.AppImage`), `chmod +x` it, and either run it or (containers without FUSE) `--appimage-extract` and link `squashfs-root/usr/bin/solidcraft-cli` into `PATH`; `sudo snap install solidcraft` also works where snapd runs. Scripts find the CLI via `SOLIDCRAFT_CLI`, then `PATH`, then the macOS path. CADCraft is optional (any DXF viewer works).
- iOS kit: not buildable on Linux (needs Xcode); the pure-Swift core `OpenPatchCore` can be tested with the Swift toolchain for Linux (`swift test`).

## Windows 10/11

```powershell
winget install Git.Git GitHub.cli astral-sh.uv Kitware.CMake LLVM.LLVM OpenJS.NodeJS.LTS EclipseAdoptium.Temurin.21.JRE KiCad.KiCad Rustlang.Rustup
rustup target add thumbv7em-none-eabihf
cargo install probe-rs-tools --locked
```
- SolidCraft: Windows installer from the vendor (`C:\Program Files\SolidCraft\solidcraft-cli.exe`). Mechanical scripts expect the CLI path in `mechanical/op_cmds.py` → adjust or set it on `PATH`.
- iOS kit: not buildable on Windows.
- Shell scripts (`*.sh`): use Git Bash or WSL2 (recommended: do everything except KiCad/SolidCraft GUIs inside WSL2 Ubuntu).

## Verify your setup

```bash
git clone git@github.com:HenrySchwerdt/ai-insulin-pump.git && cd ai-insulin-pump
cd mechanical && python3 generate.py --variant bench && python3 check.py --variant bench && cd ..
cmake -S firmware -B /tmp/fw && cmake --build /tmp/fw && /tmp/fw/op_tests        # 173 C reference tests
cd firmware-rs && cargo test --workspace && cd ..                                  # Rust firmware tests
cd ios/OpenPatchKit/OpenPatchCore && swift test && cd ../../..                     # macOS/Linux
cd site && npm ci && npm run build && cd ..
/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli version                    # or `kicad-cli version`
```

## Working with Claude Code

- Start every session by reading `CLAUDE.md`, then `docs/STATUS.md`, then `spec/design-parameters.md`.
- Long-running work was done with parallel sub-agents (one per area: mechanical, electronics, firmware-rs, ios, site); keep that split to avoid edit conflicts.
