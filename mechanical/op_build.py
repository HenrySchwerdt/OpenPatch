"""Baut das OpenPatch-Modell (Rev A) als SolidCraft-Kommandoskript."""
from __future__ import annotations

from op_cmds import Script
from op_drive import build_carriage, build_drive, build_plunger, build_reservoir
from op_elec import build_electronics
from op_layout import compute_layout
from op_shell import build_bottom, build_gasket, build_top

# Teile zum Fertigen / Gießen (Export je Datei STEP+STL)
MFG_PARTS = {
    "bottom": ["bottom"], "top": ["top"], "carriage": ["carriage"], "reservoir": ["reservoir"],
    "plunger_core": ["plunger_core"], "plunger_seal": ["seal_a", "seal_b"], "gasket": ["gasket"],
}
PURCHASED = ["leadscrew", "nut", "motor", "gearhead", "gear_a", "gear_b", "bush_dry", "bush_far", "magnet",
             "battery", "pcb", "qi_coil", "rf_module", "buzzer", "switch", "hall_tmag", "hall_drv0", "hall_drv1",
             "septum", "needle", "needle_hub"]
PART_NAMES = [b for v in MFG_PARTS.values() for b in v] + PURCHASED + ["pcb_keepout"]

# Paare, die sich konstruktiv berühren/überlappen dürfen
EXCLUDE_PAIRS = [
    ["buzzer", "pcb_keepout"], ["rf_module", "pcb_keepout"], ["switch", "pcb_keepout"],
    ["top", "pcb_keepout"], ["bottom", "pcb_keepout"], ["qi_coil", "pcb_keepout"],
    ["needle_hub", "bottom"],      # Presssitz
    ["needle", "bottom"],
]


def _flatten(prefix: str, d: dict, out: list) -> None:
    for k, v in d.items():
        if k.startswith("_"):
            continue
        if isinstance(v, dict):
            _flatten(f"{prefix}{k}_", v, out)
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            out.append((f"{prefix}{k}", v))


def add_parameter_table(s: Script, p: dict, lay: dict) -> None:
    rows: list = []
    for key in ("shell", "fit", "velcro", "reservoir", "septum", "needle", "drive", "battery", "pcb", "coil",
                "buzzer", "cannula", "rf", "hall", "screws", "button", "port", "seal", "contacts"):
        _flatten(f"p_{key}_", p[key], rows)
    rows.append(("p_stroke", lay["stroke"]))
    rows.append(("p_length", lay["length"]))
    for name, val in rows:
        s.parameter(name, val, "Generator-Wert (Info). Änderungen: params.json + generate.py")


def build_model(p: dict, variant: str) -> tuple[Script, dict]:
    L = compute_layout(p, variant)
    s = Script()
    add_parameter_table(s, p, L)
    build_bottom(s, p, L)
    build_top(s, p, L)
    build_gasket(s, p, L)
    build_reservoir(s, p, L)
    build_plunger(s, p, L)
    build_carriage(s, p, L)
    build_drive(s, p, L)
    build_electronics(s, p, L)
    return s, L
