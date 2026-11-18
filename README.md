# OpenPatch – open, detachable patch insulin pump

> ⚠️ **Test project only — NOT a medical device. Never wear it, never connect it to a person, never use it with insulin on a human.** All tests are bench tests with water. Read [DISCLAIMER.md](DISCLAIMER.md).

A reusable, very flat pod (target ≤ 8.5 mm, Omnipod DASH: 14.5 mm). It plugs directly onto an **Accu-Chek Insight Flex** cannula and is attached to the adhesive patch with Velcro. It is filled with a syringe through a septum and charged via Qi. It comes in three sizes: **70 / 100 / 200 U**. It is controlled from **Trio**, either through a dedicated PumpManager kit or through the Omnipod DASH emulation.

| Folder | Contents |
|---|---|
| [spec/design-parameters.md](spec/design-parameters.md) | **Single source of truth**: all dimensions, components, limits |
| [docs/](docs/) | Architecture, safety, patents |
| [mechanical/](mechanical/) | 3D housing (SolidCraft), STEP/STL, measurement sheet for the cannula |
| [electronics/](electronics/) | Circuit as code, BOM, board outline (DXF → CADCraft), PCBWay costs |
| [firmware/](firmware/) | C core (delivery, safety, protocol) with host tests, Zephyr skeleton, DASH compatibility plan |
| [ios/](ios/) | `OpenPatchKit` for Trio (LoopKit PumpManager) |

## Tools
- **SolidCraft** (3D, MCP server: `solidcraft-cli mcp`) for the housing
- **CADCraft** (2D DWG/DXF) for drawings and the board outline
