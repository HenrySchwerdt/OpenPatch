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
NFP_PARTS = []
PURCHASED = ["leadscrew", "nut", "motor", "gearhead", "gear_a", "gear_b", "bush_dry", "bush_far", "magnet",
             "battery", "pcb", "qi_coil", "rf_module", "buzzer", "switch", "hall_tmag", "hall_drv0", "hall_drv1",
             "septum", "needle", "needle_hub", "cannula_head"] + NFP_PARTS
PART_NAMES = [b for v in MFG_PARTS.values() for b in v] + PURCHASED + ["pcb_keepout"]

# ---- bench pod (spec 4a): no battery / coil / RF / main PCB; sensor board + FFC + cannula adapter -------------
BENCH_MFG_PARTS = {
    "bottom": ["bottom"], "top": ["top"], "carriage": ["carriage"], "reservoir": ["reservoir"],
    "cannula_adapter": ["cannula_adapter"], "dock_insert": ["dock_insert"], "plunger_core": ["plunger_core"], "plunger_nose": ["plunger_nose"], "thrust_sleeve": ["thrust_sleeve"], "thrust_collar": ["thrust_collar"], "end_cap_lid": ["end_cap_lid"], "coupler": ["coupler"], "end_cap": ["end_cap"],
    "plunger_seal": ["seal_a", "seal_b"], "gasket": ["gasket"],
}
COAX_PARTS = ["motor", "gearhead", "motor_boss", "motor_shaft", "motor_rear_boss", "motor_term", "motor_pins", "duckbill_valve", "gear_a", "gear_b", "bush_dry"]
BENCH_PURCHASED = ["cap_gasket", "cap_oring", "tongue_shim", "leadscrew", "nut", "bush_far", "magnet", "septum", "needle", "needle_hub", "pod_board",
                   "hall_tmag", "hall_drv0", "hall_drv1", "hall_dock", "ffc_conn", "ffc_cable", "dock_magnet"] + COAX_PARTS
BENCH_PART_NAMES = [b for v in BENCH_MFG_PARTS.values() for b in v] + BENCH_PURCHASED
BENCH_EXCLUDE_PAIRS = [["gear_a", "gear_b"],     # meshing teeth: both modelled as tip circles, overlap = tooth engagement
                       ["needle_hub", "end_cap"], ["needle", "end_cap"], ["duckbill_valve", "end_cap"],
                       ["septum", "end_cap"], ["septum", "end_cap_lid"], ["septum", "bottom"], ["cap_oring", "reservoir"], ["cap_oring", "end_cap"], ["cap_oring", "end_cap_lid"],
                       ["duckbill_valve", "end_cap_lid"], ["cap_gasket", "end_cap"], ["cap_gasket", "end_cap_lid"], ["end_cap", "end_cap_lid"], ["needle", "end_cap_lid"],
                       ["cap_gasket (1)", "end_cap_lid"], ["cap_gasket (2)", "end_cap_lid"], ["cap_gasket (1)", "end_cap"], ["cap_gasket (2)", "end_cap"],
                       ["cap_gasket (1)", "cap_oring"], ["cap_gasket (2)", "cap_oring"], ["cap_gasket", "cap_oring"]]


def part_sets(mode: str) -> tuple[dict, list, list]:
    """(manufactured parts, all part names, interference exclude pairs) for 'integrated' or 'bench'."""
    if mode == "bench":
        return BENCH_MFG_PARTS, BENCH_PART_NAMES, BENCH_EXCLUDE_PAIRS
    return MFG_PARTS, PART_NAMES, EXCLUDE_PAIRS

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


def build_septum_needle(s: Script, p: dict, L: dict) -> None:
    """Fill septum, horizontal needle and hub (bench variant; the rest of op_elec is the integrated electronics)."""
    from op_dock import build_needle
    from op_cap import build_cap, cap_geometry
    sp = p["septum"]
    G = build_cap(s, p, L)
    ysd = G["y_block"][0] + p["dock"]["cap"]["sandwich"]["septum"]["depth"]       # disc seated on the cavity end (no air pocket behind it), 0.2 proud of the cap face
    s.cyl("septum", "Y", (G["x_sept"], 0, L["dock"]["z_n"]), sp["d"], ysd - sp["len"], ysd)
    from op_cap import build_oring
    build_oring(s, p, L)
    D, dk = L["dock"], p["dock"]
    s.cyl("duckbill_valve", "X", (0, D["y_c"], D["z_n"]), p["coax"]["valve_d"], L["x_r1"] + dk["valve_x0"], L["x_r1"] + dk["valve_x0"] + p["coax"]["valve_len"])
    build_needle(s, p, L)


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
    if L["mode"] == "bench":
        from op_bench import build_bench_electronics
        build_bench_electronics(s, p, L)
        build_septum_needle(s, p, L)
        from op_dock import build_insert
        build_insert(s, p, L, "dock_insert")      # nominal insert (no ID digits)
    else:
        build_electronics(s, p, L)
    return s, L
