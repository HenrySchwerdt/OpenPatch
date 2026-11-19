# OpenPatch – open, detachable patch insulin pump

> ⚠️ **Test project only — NOT a medical device. Never wear it, never connect it to a person, never fill it with insulin or any other drug.** Not approved by any authority. All tests are bench tests with water only. Read [DISCLAIMER.md](DISCLAIMER.md).

A reusable, very flat pod (target ≤ 8.5 mm, Omnipod DASH: 14.5 mm). It plugs directly onto an **Accu-Chek Insight Flex** cannula and is attached to the adhesive patch with Velcro. It is filled with a syringe through a septum and charged via Qi. It comes in three sizes: **70 / 100 / 200 U**. It is controlled from **Trio**, either through a dedicated PumpManager kit or through the Omnipod DASH emulation.

| Folder | Contents |
|---|---|
| [spec/design-parameters.md](spec/design-parameters.md) | **Single source of truth**: all dimensions, components, limits |
| [docs/](docs/) | Architecture, safety, patents |
| [docs/build-guide/](docs/build-guide/) | Step-by-step **bench build guide** for the OP-100 pod (water-only tests, never worn): parts, prints, assembly images, flashing, bench tests, troubleshooting |
| [mechanical/](mechanical/) | 3D housing (SolidCraft), STEP/STL, measurement sheet for the cannula |
| [electronics/](electronics/) | Circuit as code, BOM, board outline (DXF → CADCraft), PCBWay costs |
| [firmware/](firmware/) | C core (delivery, safety, protocol) with host tests, Zephyr skeleton, DASH compatibility plan |
| [ios/](ios/) | `OpenPatchKit` for Trio (LoopKit PumpManager) |
| [regulatory/](regulatory/) | Regulatory roadmap, standards matrix, technical-file skeleton, risk/software/usability/clinical structure, traceability tools (evidence for a future legal manufacturer; no IFU, no medical claim) |

## Tools
- **SolidCraft** (3D, MCP server: `solidcraft-cli mcp`) for the housing
- **CADCraft** (2D DWG/DXF) for drawings and the board outline

## License

Dual licensing, source-available (not OSI "open source"):
- **Community licence (free, non-commercial, research, education, bench self-build):** hardware and documentation CC-BY-NC-SA-4.0; software PolyForm-Noncommercial-1.0.0; `ios/` (OpenPatchKit, compiled into Trio/AGPL) stays GPL-3.0-or-later.
- **Commercial "Fair-Price" licence (draft):** required for any commercial manufacture, sale or service; price cap cost + 30 %, 5 % clinical-trial levy, safety obligations — see [COMMERCIAL-LICENSE.md](COMMERCIAL-LICENSE.md).
- Contributing: [CONTRIBUTING.md](CONTRIBUTING.md), [CLA.md](CLA.md).

Details: [LICENSE.md](LICENSE.md). Not a medical device; see [DISCLAIMER.md](DISCLAIMER.md).
