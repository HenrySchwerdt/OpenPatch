"""Electronics placeholders (battery, PCB, coil, RF module, piezo, button, Hall, septum, needle)."""
from __future__ import annotations

from op_cmds import Script


def pcb_cut_rects(p: dict, L: dict) -> dict:
    rects = dict(L["pcb"]["cutouts"])
    nd = p["needle"]
    return rects


def build_electronics(s: Script, p: dict, L: dict) -> None:
    bt, pc, co, sp, nd, fit, hl, rf, bn = (p["battery"], p["pcb"], p["coil"], p["septum"], p["needle"], p["fit"],
                                           p["hall"], p["rf"], p["button"])
    wall, yi1 = L["wall"], L["yi1"]
    bz0 = wall + fit["bat_gap"]
    s.rrect("battery", (L["bat_x0"], L["bat_x0"] + L["bat_x"]), (L["bat_y0"], L["bat_y1"]),
            1.0, (bz0, bz0 + bt["t"]))
    pcbl = L["pcb"]
    px, py = tuple(pcbl["x"]), tuple(pcbl["y"])
    rr = p["shell"]["corner_r"] - wall - pc["margin"]
    rects = pcb_cut_rects(p, L)
    for name, z in (("pcb", (pc["z0"], pc["z0"] + pc["t"])),
                    ("pcb_keepout", (pc["z0"] + pc["t"], pc["z0"] + pc["t"] + pc["keepout"]))):
        s.rrect(name, px, py, rr, z)
        tools = [s.box(f"t_{name}_{k}", (r[0], r[1]), (r[2], r[3]), (z[0] - 0.1, z[1] + 0.1)) for k, r in rects.items()]
        s.cut(name, tools)
    s.cyl("qi_coil", "Z", (L["coil_cx"], L["coil_cy"], 0), co["d"], co["z0"], co["z0"] + co["t"])
    m = L["rf_module"]
    s.box("rf_module", tuple(m["x"]), tuple(m["y"]), tuple(m["z"]))
    b = L["buzzer"]
    s.box("buzzer", (b["x0"], b["x1"]), (b["y0"], b["y1"]), (b["z0"], b["z1"]))
    bx, by = L["button"]["x"], L["button"]["y"]
    s.box("switch", (bx - bn["sw_x"] / 2, bx + bn["sw_x"] / 2), (by - bn["sw_y"] / 2, by + bn["sw_y"] / 2),
          (pc["z0"] + pc["t"], pc["z0"] + pc["t"] + bn["sw_z"]))
    h = L["hall"]
    s.box("hall_tmag", (h["x"] - hl["pkg_x"] / 2, h["x"] + hl["pkg_x"] / 2), (h["y"] - hl["pkg_y"] / 2, h["y"] + hl["pkg_y"] / 2),
          (pc["z0"] - hl["pkg_z"], pc["z0"]))
    for i, d in enumerate(L["drv5032"]):
        s.box(f"hall_drv{i}", (d["x"] - hl["drv_x"] / 2, d["x"] + hl["drv_x"] / 2), (d["y"] - hl["drv_y"] / 2, d["y"] + hl["drv_y"] / 2),
              (pc["z0"] - hl["drv_z"], pc["z0"]))
    # Septum + needle + needle sleeve (horizontal needle of the slide-on dock)
    s.cyl("septum", "Y", (L["x_s"], 0, sp["z"]), sp["d"], sp["recess"], sp["recess"] + sp["len"])
    from op_dock import build_adapter, build_needle
    build_needle(s, p, L)
    build_adapter(s, p, L, name="cannula_head", lug=False)
