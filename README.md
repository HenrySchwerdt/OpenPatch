# OpenPatch – offene, abnehmbare Patch-Insulinpumpe

> ⚠️ **Experimentelles DIY-Projekt und kein zugelassenes Medizinprodukt.** Fehlförderung von Insulin kann lebensgefährlich sein. Lies zuerst [docs/02-safety.md](docs/02-safety.md).

Ein wiederverwendbarer, sehr flacher Pod (Ziel ≤ 8,5 mm, Omnipod DASH: 14,5 mm). Er wird direkt auf eine **Accu-Chek Insight Flex**-Kanüle gesteckt und mit Klett am Pflaster befestigt. Befüllt wird er mit einer Spritze durch ein Septum, geladen per Qi. Es gibt ihn in drei Größen: **70 / 100 / 200 IE**. Gesteuert wird er aus **Trio**, entweder über ein eigenes PumpManager-Kit oder über die Omnipod-DASH-Emulation.

| Ordner | Inhalt |
|---|---|
| [spec/design-parameters.md](spec/design-parameters.md) | **Single Source of Truth**: alle Maße, Bauteile, Grenzwerte |
| [docs/](docs/) | Architektur, Sicherheit, Patente |
| [mechanical/](mechanical/) | 3D-Gehäuse (SolidCraft), STEP/STL, Messblatt für die Kanüle |
| [electronics/](electronics/) | Schaltung als Code, BOM, Platinenkontur (DXF → CADCraft), PCBWay-Kosten |
| [firmware/](firmware/) | C-Kern (Delivery, Safety, Protokoll) mit Host-Tests, Zephyr-Skelett, DASH-Kompatibilitätsplan |
| [ios/](ios/) | `OpenPatchKit` für Trio (LoopKit PumpManager) |

## Werkzeuge
- **SolidCraft** (3D, MCP-Server: `solidcraft-cli mcp`) für das Gehäuse
- **CADCraft** (2D DWG/DXF) für Zeichnungen und die Platinenkontur
